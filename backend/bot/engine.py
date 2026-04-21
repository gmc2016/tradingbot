import logging, threading
from bot.exchange import fetch_ohlcv, fetch_ticker, place_market_order, calculate_quantity, get_balance
from bot.strategy import generate_signal, set_cooldown, is_in_cooldown, is_liquid_coin
from ai.sentiment import get_pair_sentiment, fetch_and_analyze, llm_trade_decision
from db.database import (get_setting, set_setting, insert_trade, close_trade,
                          partial_close_trade, update_trailing_stop, update_trailing_tp,
                          get_open_trades, get_recent_trades, get_stats, get_news)
from db.activitylog import log as alog
from bot.watchlist import check_watchlist_promotions, get_watchlist_data

logger       = logging.getLogger(__name__)

# Backward-compat shim — old cached container versions may call get_macro_data()
def get_macro_data(*a, **kw):
    try:
        from bot.macro import fetch_all_macro, get_macro_risk_level
        m = fetch_all_macro()
        m['signals'] = get_macro_risk_level(m)
        return m
    except: return {'signals': {}}
_demo        = {'balance':1000.0,'init':False}
_cache       = {'pairs':[],'sentiments':{},'last_update':None}
_loss_streak = {}
_llm_calls_today = {'count':0,'date':None}

def set_cooldown_scalp(pair, minutes=10):
    from bot.strategy import set_cooldown
    set_cooldown(pair, minutes)

def increment_llm_counter():
    from datetime import date
    today = date.today().isoformat()
    if _llm_calls_today['date'] != today:
        _llm_calls_today['count'] = 0
        _llm_calls_today['date']  = today
    _llm_calls_today['count'] += 1

def get_llm_today_count():
    from datetime import date
    today = date.today().isoformat()
    return _llm_calls_today['count'] if _llm_calls_today['date']==today else 0

def _s(key, default):
    try:
        val = get_setting(key)
        if val is None or val=='' or val=='None': return str(default)
        return val
    except: return str(default)

def get_demo_balance():
    if not _demo['init']:
        try: _demo['balance'] = float(_s('starting_balance',1000))
        except: _demo['balance'] = 1000.0
        _demo['init'] = True
    return _demo['balance']

def adj_demo(d): _demo['balance'] += d

def get_config():
    return {
        'max_positions':        int(_s('max_positions',5)),
        'stop_loss_pct':        float(_s('stop_loss_pct',1.5))/100,
        'take_profit_pct':      float(_s('take_profit_pct',3.0))/100,
        'position_size_usdt':   float(_s('position_size_usdt',100)),
        'mode':                 _s('trading_mode','demo'),
        'trailing_stop':        _s('trailing_stop_enabled','true')=='true',
        'trailing_stop_pct':    float(_s('trailing_stop_pct',0.8))/100,
        'partial_close':        _s('partial_close_enabled','true')=='true',
        'partial_close_at_pct': float(_s('partial_close_at_pct',1.5))/100,
        'partial_close_size':   float(_s('partial_close_size_pct',50))/100,
        'strategy':             _s('strategy_mode','combined'),
        'max_loss_streak':      int(_s('max_loss_streak',3)),
        'cooldown_minutes':     int(_s('cooldown_minutes',60)),
        'use_llm':              _s('use_llm_filter','false')=='true',
        'mtf_enabled':          _s('mtf_enabled','false')=='true',
    }

def get_pairs_list():
    raw = _s('active_pairs','BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,LINK/USDT,AVAX/USDT,DOT/USDT,AAVE/USDT,MATIC/USDT,NEAR/USDT,UNI/USDT')
    return [p.strip() for p in raw.split(',') if p.strip()]

def check_open_positions():
    cfg = get_config()
    for t in get_open_trades():
        ticker = fetch_ticker(t['pair'])
        if not ticker: continue
        cp=ticker['last']; side=t['side']; entry=t['entry_price']
        sl=t['stop_loss']; tp=t['take_profit']; qty=t['quantity']; mode=t['mode']
        pnl_pct = (cp-entry)/entry if side=='BUY' else (entry-cp)/entry

        # ── SMART TRAILING TAKE-PROFIT ────────────────────────────────────────
        # As price rises, TP rises with it. When price drops a %, TP locks in.
        # Example: entry $100, initial TP $103.
        # Price rises to $105 → TP moves to $104.16 (0.8% below peak)
        # Price rises to $108 → TP moves to $107.14
        # Price drops to $107.14 → trade closes at profit, never waits endlessly
        if cfg['trailing_stop'] and pnl_pct >= cfg['trailing_stop_pct']:
            trail_dist = cfg['trailing_stop_pct']
            if side == 'BUY':
                # New TP = current price minus trail distance (locks in profit)
                new_tp = round(cp * (1 - trail_dist), 8)
                # Only move TP UP, never down — ratchet mechanism
                if new_tp > tp:
                    update_trailing_stop(t['id'], sl)  # also keep SL updated
                    update_trailing_tp(t['id'], new_tp)
                    alog('trade', f"Trail TP {t['pair']} raised → ${new_tp:.4f} (price:${cp:.4f})",
                         detail={'pair':t['pair'],'new_tp':new_tp,'price':cp})
                    tp = new_tp
                # Also trail the stop loss up
                new_sl = round(cp * (1 - trail_dist * 2), 8)  # SL stays 2x trail below
                if new_sl > sl:
                    update_trailing_stop(t['id'], new_sl); sl = new_sl
            else:  # SELL
                new_tp = round(cp * (1 + trail_dist), 8)
                if new_tp < tp:
                    update_trailing_tp(t['id'], new_tp)
                    tp = new_tp
                new_sl = round(cp * (1 + trail_dist * 2), 8)
                if new_sl < sl:
                    update_trailing_stop(t['id'], new_sl); sl = new_sl

        # ── PARTIAL CLOSE ─────────────────────────────────────────────────────
        # Take some profit early, let the rest ride with trailing
        if (cfg['partial_close'] and pnl_pct >= cfg['partial_close_at_pct']
                and qty > 0 and not t.get('trailing_stop')):
            cqty = round(qty * cfg['partial_close_size'], 8)
            rem  = round(qty - cqty, 8)
            if cqty > 0 and rem > 0:
                pp = (cp-entry)*cqty if side=='BUY' else (entry-cp)*cqty
                try:
                    place_market_order(t['pair'],'SELL' if side=='BUY' else 'BUY',cqty,mode=mode)
                    partial_close_trade(t['id'],rem,pp)
                    if mode=='demo': adj_demo(pp)
                    alog('trade',f"Partial close {t['pair']} +${pp:.2f}",level='success',
                         detail={'pair':t['pair'],'partial_pnl':round(pp,4),'remain_qty':rem})
                except Exception as e: logger.error(f'Partial close: {e}')

        # ── FULL CLOSE at SL or TP ─────────────────────────────────────────────
        # For BUY: close if price drops to SL or rises above TP
        # With trailing TP: TP moves up as price rises, so "hitting TP" means
        # price dropped back to the trailing level = smart exit with locked profit
        hit = (cp<=sl or cp>=tp) if side=='BUY' else (cp>=sl or cp<=tp)
        if hit:
            pnl = (cp-entry)*qty if side=='BUY' else (entry-cp)*qty
            try: place_market_order(t['pair'],'SELL' if side=='BUY' else 'BUY',qty,mode=mode)
            except: continue
            # Deduct fees in demo mode for realistic P&L
            fee_rate = float(_s('demo_fee_rate','0.1')) / 100
            fee      = (entry * qty * fee_rate) + (cp * qty * fee_rate)
            pnl_after_fee = pnl - fee
            close_trade(t['id'],cp,pnl_after_fee)
            if mode=='demo': adj_demo(pnl_after_fee + cfg['position_size_usdt'])
            closed_by = 'TP' if ((side=='BUY' and cp>=tp) or (side=='SELL' and cp<=tp)) else 'SL'
            # With trailing: closing at "TP" often means trailing stop triggered = profit locked
            level = 'success' if pnl>=0 else 'warning'
            label = 'Trail-TP' if (t.get('trailing_stop') and closed_by=='TP') else closed_by
            alog('trade',f"CLOSED {side} {t['pair']} {label} — PnL:{pnl:+.2f} USDT",
                 level=level,
                 detail={'pair':t['pair'],'side':side,'pnl':round(pnl,4),
                         'closed_by':label,'exit_price':cp,'entry':entry})
            if pnl < 0:
                _loss_streak[t['pair']] = _loss_streak.get(t['pair'],0) + 1
                if _loss_streak[t['pair']] >= cfg['max_loss_streak']:
                    set_cooldown(t['pair'],cfg['cooldown_minutes'])
                    _loss_streak[t['pair']] = 0
                    alog('system',f"Cooldown: {t['pair']} paused {cfg['cooldown_minutes']}min",
                         level='warning')
            else:
                _loss_streak[t['pair']] = 0

def scan_and_trade():
    if _s('bot_running','false')!='true': return
    cfg=get_config(); mode=cfg['mode']
    alog('system',f"Scan cycle — mode:{mode} strategy:{cfg['strategy']} pairs:{len(get_pairs_list())}")
    # Check watchlist for auto-promotion opportunities
    promoted = check_watchlist_promotions()
    if promoted > 0:
        logger.info(f'Watchlist promoted {promoted} pair(s) to active')
    check_open_positions()
    open_t=get_open_trades(); open_pairs={t['pair'] for t in open_t}
    open_cnt=len(open_t)
    if open_cnt>=cfg['max_positions']: return
    news=get_news(20)

    for pair in get_pairs_list():
        if pair in open_pairs or open_cnt>=cfg['max_positions']: continue
        if is_in_cooldown(pair): continue

        df_1h=fetch_ohlcv(pair,timeframe='1h',limit=300)
        if df_1h is None or len(df_1h)<50: continue

        df_4h=None
        if cfg['mtf_enabled']:
            df_4h=fetch_ohlcv(pair,timeframe='4h',limit=150)

        sent  =get_pair_sentiment(pair)
        result=generate_signal(df_1h,sentiment_score=sent,strategy=cfg['strategy'],
                               df_4h=df_4h,pair=pair)
        sig=result['signal']; conf=result['confidence']
        reason=result['reason']; indic=result.get('indicators',{})
        sl_price=result.get('sl_price'); tp_price=result.get('tp_price')

        alog('signal',f"{pair}: {sig} ({conf}%)",
             detail={'pair':pair,'signal':sig,'confidence':conf,
                     'reason':reason,'sentiment':round(sent,1)})

        if sig in ('BUY','SELL') and conf>=55:
            # Apply macro filters
            try:
                from bot.macro import fetch_all_macro, get_macro_risk_level
                macro      = fetch_all_macro()
                risk       = get_macro_risk_level(macro)
                macro_mult = 1.0
                if risk['level'] == 'extreme':
                    alog('signal', f'{pair}: {sig} blocked — macro risk EXTREME', level='warning')
                    continue
                elif risk['level'] == 'high':
                    macro_mult = 0.8  # reduce size on high risk
            except:
                macro_mult = 1.0

            ticker=fetch_ticker(pair)
            if not ticker: continue
            price=ticker['last']; pos=cfg['position_size_usdt']
            avail=get_demo_balance() if mode=='demo' else get_balance().get('USDT',0)
            if avail<pos: logger.warning(f'Low balance:{avail:.2f}'); continue

            # LLM filter — only when we have balance to act
            if cfg['use_llm']:
                approved,llm_reason,adj_conf=llm_trade_decision(pair,sig,conf,indic,sent,news)
                if not approved or adj_conf<50: continue
                conf=adj_conf; reason=f'{reason} | AI: {llm_reason}'

            # Tiered position sizing × macro multiplier
            if conf >= 85 and cfg['use_llm']:
                tier_mult = 1.25
            elif conf >= 85:
                tier_mult = 1.15
            elif conf >= 70:
                tier_mult = 1.0
            elif conf >= 55:
                tier_mult = 0.8
            else:
                tier_mult = 0.75
            tiered_pos = round(pos * tier_mult * macro_mult, 2)
            if macro_mult != 1.0:
                logger.info(f'{pair}: macro size mult={macro_mult}x → ${tiered_pos}')
            qty=calculate_quantity(pair, tiered_pos, price)

            if sl_price and tp_price:
                sl=sl_price; tp=tp_price
            else:
                # Adaptive SL/TP based on price magnitude
                sl_pct=cfg['stop_loss_pct']; tp_pct=cfg['take_profit_pct']
                if price<0.1:    sl_pct*=2.0; tp_pct*=2.0
                elif price<1.0:  sl_pct*=1.5; tp_pct*=1.5
                sl=round(price*(1-sl_pct),8) if sig=='BUY' else round(price*(1+sl_pct),8)
                tp=round(price*(1+tp_pct),8) if sig=='BUY' else round(price*(1-tp_pct),8)

            try:
                order=place_market_order(pair,sig,qty,mode=mode)
                fill=order.get('price',price)
                tid=insert_trade(mode,pair,sig,fill,qty,sl,tp,reason,order.get('id'))
                if mode=='demo': adj_demo(-tiered_pos)
                open_cnt+=1
                alog('trade',f"OPENED {sig} {pair} @ {fill:.6g} SL:{sl:.6g} TP:{tp:.6g}",
                     level='success',
                     detail={'pair':pair,'side':sig,'price':fill,'sl':sl,'tp':tp,
                             'qty':qty,'id':tid,'mode':mode,'conf':conf})
            except Exception as e:
                logger.error(f'Order failed {pair}: {e}')

def open_manual_trade(pair, side, usdt_amount, sl_pct, tp_pct, mode):
    ticker=fetch_ticker(pair)
    if not ticker: raise ValueError(f'Cannot fetch price for {pair}')
    price=ticker['last']
    qty=calculate_quantity(pair,usdt_amount,price)
    sl=round(price*(1-sl_pct/100),8) if side=='BUY' else round(price*(1+sl_pct/100),8)
    tp=round(price*(1+tp_pct/100),8) if side=='BUY' else round(price*(1-tp_pct/100),8)
    order=place_market_order(pair,side,qty,mode=mode)
    fill=order.get('price',price)
    tid=insert_trade(mode,pair,side,fill,qty,sl,tp,'Manual trade',order.get('id'))
    if mode=='demo': adj_demo(-usdt_amount)
    alog('trade',f"MANUAL {side} {pair} @ {fill:.6g}",level='success',
         detail={'pair':pair,'side':side,'price':fill,'sl':sl,'tp':tp,'qty':qty,'id':tid})
    return {'id':tid,'pair':pair,'side':side,'price':fill,'qty':qty,'sl':sl,'tp':tp}

def close_manual_trade(trade_id):
    open_t=[t for t in get_open_trades() if t['id']==trade_id]
    if not open_t: raise ValueError('Trade not found or already closed')
    t=open_t[0]; ticker=fetch_ticker(t['pair'])
    if not ticker: raise ValueError('Cannot fetch price')
    cp=ticker['last']
    pnl=(cp-t['entry_price'])*t['quantity'] if t['side']=='BUY' else (t['entry_price']-cp)*t['quantity']
    place_market_order(t['pair'],'SELL' if t['side']=='BUY' else 'BUY',t['quantity'],mode=t['mode'])
    close_trade(trade_id,cp,pnl)
    if t['mode']=='demo': adj_demo(pnl)
    alog('trade',f"FORCE CLOSED {t['pair']} PnL:{pnl:+.2f}",
         level='success' if pnl>=0 else 'warning',
         detail={'pair':t['pair'],'pnl':round(pnl,4),'exit_price':cp})
    return {'id':trade_id,'closed_at':cp,'pnl':round(pnl,2)}

def refresh_pair_cache():
    cfg=get_config(); pairs_raw=get_pairs_list(); pair_data=[]
    for pair in pairs_raw:
        try:
            ticker=fetch_ticker(pair)
            price=ticker['last'] if ticker else 0
            change=ticker.get('percentage',0) if ticker else 0
            df_1h=fetch_ohlcv(pair,timeframe='1h',limit=100)
            df_4h=fetch_ohlcv(pair,timeframe='4h',limit=100) if cfg['mtf_enabled'] else None
            sent=get_pair_sentiment(pair)
            res={'signal':'HOLD','confidence':0,'reason':'Loading...','indicators':{}}
            if df_1h is not None and len(df_1h)>=50:
                res=generate_signal(df_1h,sentiment_score=sent,
                                    strategy=cfg['strategy'],df_4h=df_4h,pair=pair)
            pair_data.append({
                'symbol':pair,'price':price,'change':round(change,2),
                'signal':res['signal'],'confidence':res['confidence'],
                'reason':res['reason'],'sentiment':sent,
                'indicators':res['indicators'],'cooldown':is_in_cooldown(pair),
            })
        except Exception as e:
            logger.error(f'Cache {pair}: {e}')
            pair_data.append({'symbol':pair,'price':0,'change':0,'signal':'HOLD',
                              'confidence':0,'reason':'Error','sentiment':50,
                              'indicators':{},'cooldown':False})
    _cache['pairs']     = pair_data
    _cache['sentiments']= {p['symbol']:p['sentiment'] for p in pair_data}
    from datetime import datetime as dt
    _cache['last_update']= dt.utcnow().isoformat()

    # Refresh watchlist cache using already-fetched pair data
    try:
        wl_data = get_watchlist_data(cached_pairs=pair_data)
        _cache['watchlist'] = wl_data
    except Exception as e:
        logger.debug(f'Watchlist cache: {e}')

    logger.info('Cache refreshed')

def start_cache_refresh():
    t=threading.Thread(target=refresh_pair_cache,daemon=True); t.start()

def get_dashboard_data():
    cfg=get_config(); mode=cfg['mode']
    open_t=get_open_trades(); recent=get_recent_trades(30)
    for t in recent:
        if t.get('status')=='open':
            cached=next((p for p in _cache['pairs'] if p['symbol']==t['pair']),None)
            cp=cached['price'] if cached and cached['price'] else None
            if cp:
                t['unrealized_pnl']=round(
                    (cp-t['entry_price'])*t['quantity'] if t['side']=='BUY'
                    else (t['entry_price']-cp)*t['quantity'],2)
                t['current_price']=cp
    pairs_raw=get_pairs_list()
    pair_data=_cache['pairs'] if _cache['pairs'] else [
        {'symbol':p,'price':0,'change':0,'signal':'--','confidence':0,
         'reason':'Loading...','sentiment':50,'indicators':{},'cooldown':False}
        for p in pairs_raw]
    bal=get_demo_balance() if mode=='demo' else get_balance().get('USDT',0)
    llm_today=get_llm_today_count()
    # Watchlist data from cache only — refreshed during scan cycle
    watchlist_data = _cache.get('watchlist', [])

    return {
        'mode':mode, 'bot_running':_s('bot_running','false')=='true',
        'watchlist': watchlist_data,
        'stats':get_stats(), 'open_trades':open_t, 'recent_trades':recent,
        'pairs':pair_data, 'news':get_news(15),
        'sentiments':_cache.get('sentiments',{}),
        'usdt_balance':round(bal,2),
        'last_update':_cache.get('last_update'),
        'llm_today':   llm_today,
        'llm_cost_today': round(llm_today*0.00068,4),
        'config':{
            'max_positions':         cfg['max_positions'],
            'stop_loss_pct':         _s('stop_loss_pct','1.5'),
            'take_profit_pct':       _s('take_profit_pct','3.0'),
            'position_size_usdt':    _s('position_size_usdt','100'),
            'active_pairs':          pairs_raw,
            'starting_balance':      _s('starting_balance','1000'),
            'trailing_stop_enabled': _s('trailing_stop_enabled','true'),
            'trailing_stop_pct':     _s('trailing_stop_pct','0.8'),
            'partial_close_enabled': _s('partial_close_enabled','true'),
            'partial_close_at_pct':  _s('partial_close_at_pct','1.5'),
            'partial_close_size_pct':_s('partial_close_size_pct','50'),
            'strategy_mode':         cfg['strategy'],
            'max_loss_streak':       _s('max_loss_streak','3'),
            'cooldown_minutes':      _s('cooldown_minutes','60'),
            'use_llm_filter':        _s('use_llm_filter','false'),
            'mtf_enabled':           _s('mtf_enabled','false'),
            'scanner_enabled':       _s('scanner_enabled','true'),
            'scanner_auto_update':   _s('scanner_auto_update','true'),
            'last_scan_at':          _s('last_scan_at',''),
            'pinned_pairs':          _s('pinned_pairs','BTC/USDT,ETH/USDT'),
            'ai_brain_enabled':      _s('ai_brain_enabled','false'),
            'anthropic_key_set':     bool(get_setting('anthropic_api_key') not in (None,'','None')),
        }
    }
