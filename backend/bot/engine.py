import logging, threading
from bot.exchange import fetch_ohlcv, fetch_ticker, place_market_order, calculate_quantity, get_balance
from bot.strategy import generate_signal, set_cooldown, is_in_cooldown
from ai.sentiment import get_pair_sentiment, fetch_and_analyze, llm_trade_decision
from db.database import (get_setting, set_setting, insert_trade, close_trade,
                          partial_close_trade, update_trailing_stop,
                          get_open_trades, get_recent_trades, get_stats, get_news)

logger = logging.getLogger(__name__)
_demo  = {'balance':1000.0,'init':False}
_cache = {'pairs':[],'sentiments':{},'last_update':None}
_loss_streak = {}

def _s(key, default):
    try:
        val = get_setting(key)
        if val is None or val=='' or val=='None': return str(default)
        return val
    except: return str(default)

def get_demo_balance():
    if not _demo['init']:
        try: _demo['balance']=float(_s('starting_balance',1000))
        except: _demo['balance']=1000.0
        _demo['init']=True
    return _demo['balance']

def adj_demo(d): _demo['balance']+=d

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
        'use_llm':              _s('use_llm_filter','true')=='true',
        'mtf_enabled':          _s('mtf_enabled','true')=='true',
    }

def get_pairs_list():
    raw=_s('active_pairs','BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,ADA/USDT,DOGE/USDT,AVAX/USDT')
    return [p.strip() for p in raw.split(',') if p.strip()]

def check_open_positions():
    cfg=get_config()
    for t in get_open_trades():
        ticker=fetch_ticker(t['pair'])
        if not ticker: continue
        cp=ticker['last']; side=t['side']; entry=t['entry_price']
        sl=t['stop_loss']; tp=t['take_profit']; qty=t['quantity']; mode=t['mode']
        pnl_pct=(cp-entry)/entry if side=='BUY' else (entry-cp)/entry

        if (cfg['partial_close'] and pnl_pct>=cfg['partial_close_at_pct'] and qty>0 and not t.get('trailing_stop')):
            close_qty=round(qty*cfg['partial_close_size'],8)
            remain   =round(qty-close_qty,8)
            if close_qty>0 and remain>0:
                partial_pnl=(cp-entry)*close_qty if side=='BUY' else (entry-cp)*close_qty
                try:
                    place_market_order(t['pair'],'SELL' if side=='BUY' else 'BUY',close_qty,mode=mode)
                    partial_close_trade(t['id'],remain,partial_pnl)
                    if mode=='demo': adj_demo(partial_pnl)
                    logger.info(f"Partial close {t['pair']} PnL:{partial_pnl:.2f}")
                except Exception as e: logger.error(f'Partial close: {e}')

        if cfg['trailing_stop'] and pnl_pct>=cfg['trailing_stop_pct']:
            if side=='BUY':
                new_sl=round(cp*(1-cfg['trailing_stop_pct']),8)
                if new_sl>sl: update_trailing_stop(t['id'],new_sl); sl=new_sl
            else:
                new_sl=round(cp*(1+cfg['trailing_stop_pct']),8)
                if new_sl<sl: update_trailing_stop(t['id'],new_sl); sl=new_sl

        hit=(cp<=sl or cp>=tp) if side=='BUY' else (cp>=sl or cp<=tp)
        if hit:
            pnl=(cp-entry)*qty if side=='BUY' else (entry-cp)*qty
            try: place_market_order(t['pair'],'SELL' if side=='BUY' else 'BUY',qty,mode=mode)
            except: continue
            close_trade(t['id'],cp,pnl)
            if mode=='demo': adj_demo(pnl)
            closed_by='TP' if ((side=='BUY' and cp>=tp) or (side=='SELL' and cp<=tp)) else 'SL'
            logger.info(f"Closed {t['pair']} {side} {closed_by} PnL:{pnl:.2f}")
            if pnl<0:
                _loss_streak[t['pair']]=_loss_streak.get(t['pair'],0)+1
                if _loss_streak[t['pair']]>=cfg['max_loss_streak']:
                    set_cooldown(t['pair'],cfg['cooldown_minutes'])
                    _loss_streak[t['pair']]=0
            else:
                _loss_streak[t['pair']]=0

def scan_and_trade():
    if _s('bot_running','false')!='true': return
    cfg=get_config(); mode=cfg['mode']
    check_open_positions()
    open_t    =get_open_trades()
    open_pairs={t['pair'] for t in open_t}
    open_cnt  =len(open_t)
    if open_cnt>=cfg['max_positions']: return
    news=get_news(20)

    for pair in get_pairs_list():
        if pair in open_pairs or open_cnt>=cfg['max_positions']: continue
        if is_in_cooldown(pair): logger.info(f'{pair}: cooldown'); continue

        df_1h=fetch_ohlcv(pair,timeframe='1h',limit=300)
        if df_1h is None or len(df_1h)<50: continue

        # Fetch 4h data for MTF
        df_4h=None
        if cfg['strategy'] in ('mtf','combined') and cfg['mtf_enabled']:
            df_4h=fetch_ohlcv(pair,timeframe='4h',limit=150)

        sent  =get_pair_sentiment(pair)
        result=generate_signal(df_1h,sentiment_score=sent,strategy=cfg['strategy'],df_4h=df_4h)
        sig   =result['signal']; conf=result['confidence']
        reason=result['reason']; sl_price=result.get('sl_price'); tp_price=result.get('tp_price')
        indic =result.get('indicators',{})

        logger.info(f'{pair}: {sig} ({conf}%) {reason}')

        if sig in ('BUY','SELL') and conf>=55:
            # LLM second opinion
            if cfg['use_llm']:
                approved,llm_reason,adj_conf=llm_trade_decision(pair,sig,conf,indic,sent,news)
                if not approved:
                    logger.info(f'LLM rejected {pair} {sig}: {llm_reason}')
                    continue
                if adj_conf<50:
                    logger.info(f'LLM reduced confidence too low {pair}: {adj_conf}%')
                    continue
                conf=adj_conf
                reason=f'{reason} | LLM: {llm_reason}'

            ticker=fetch_ticker(pair)
            if not ticker: continue
            price=ticker['last']; pos=cfg['position_size_usdt']
            avail=get_demo_balance() if mode=='demo' else get_balance().get('USDT',0)
            if avail<pos: logger.warning(f'Low balance:{avail:.2f}'); continue
            qty=calculate_quantity(pair,pos,price)
            if sl_price and tp_price: sl=sl_price; tp=tp_price
            else:
                sl=round(price*(1-cfg['stop_loss_pct']),8) if sig=='BUY' else round(price*(1+cfg['stop_loss_pct']),8)
                tp=round(price*(1+cfg['take_profit_pct']),8) if sig=='BUY' else round(price*(1-cfg['take_profit_pct']),8)
            try:
                order=place_market_order(pair,sig,qty,mode=mode)
                fill =order.get('price',price)
                tid  =insert_trade(mode,pair,sig,fill,qty,sl,tp,reason,order.get('id'))
                if mode=='demo': adj_demo(-pos)
                open_cnt+=1
                logger.info(f'Opened {sig} {pair}@{fill} SL:{sl} TP:{tp} id={tid}')
            except Exception as e: logger.error(f'Order failed {pair}:{e}')

def open_manual_trade(pair, side, usdt_amount, sl_pct, tp_pct, mode):
    """Open a manual trade bypassing signal logic."""
    ticker=fetch_ticker(pair)
    if not ticker: raise ValueError(f'Cannot fetch price for {pair}')
    price=ticker['last']
    qty  =calculate_quantity(pair,usdt_amount,price)
    sl   =round(price*(1-sl_pct/100),8) if side=='BUY' else round(price*(1+sl_pct/100),8)
    tp   =round(price*(1+tp_pct/100),8) if side=='BUY' else round(price*(1-tp_pct/100),8)
    order=place_market_order(pair,side,qty,mode=mode)
    fill =order.get('price',price)
    tid  =insert_trade(mode,pair,side,fill,qty,sl,tp,'Manual trade',order.get('id'))
    if mode=='demo': adj_demo(-usdt_amount)
    logger.info(f'Manual {side} {pair}@{fill} qty={qty} SL:{sl} TP:{tp} id={tid}')
    return {'id':tid,'pair':pair,'side':side,'price':fill,'qty':qty,'sl':sl,'tp':tp}

def close_manual_trade(trade_id):
    """Force close an open trade at market price."""
    open_t=[t for t in get_open_trades() if t['id']==trade_id]
    if not open_t: raise ValueError('Trade not found or already closed')
    t   =open_t[0]
    ticker=fetch_ticker(t['pair'])
    if not ticker: raise ValueError('Cannot fetch price')
    cp  =ticker['last']
    pnl =(cp-t['entry_price'])*t['quantity'] if t['side']=='BUY' else (t['entry_price']-cp)*t['quantity']
    place_market_order(t['pair'],'SELL' if t['side']=='BUY' else 'BUY',t['quantity'],mode=t['mode'])
    close_trade(trade_id,cp,pnl)
    if t['mode']=='demo': adj_demo(pnl)
    return {'id':trade_id,'closed_at':cp,'pnl':round(pnl,2)}

def refresh_pair_cache():
    cfg=get_config()
    pairs_raw=get_pairs_list()
    pair_data=[]
    for pair in pairs_raw:
        try:
            ticker=fetch_ticker(pair)
            price =ticker['last'] if ticker else 0
            change=ticker.get('percentage',0) if ticker else 0
            df_1h =fetch_ohlcv(pair,timeframe='1h',limit=100)
            df_4h =fetch_ohlcv(pair,timeframe='4h',limit=100) if cfg['mtf_enabled'] else None
            sent  =get_pair_sentiment(pair)
            res   ={'signal':'HOLD','confidence':0,'reason':'Loading...','indicators':{}}
            if df_1h is not None and len(df_1h)>=50:
                res=generate_signal(df_1h,sentiment_score=sent,strategy=cfg['strategy'],df_4h=df_4h)
            pair_data.append({
                'symbol':pair,'price':price,'change':round(change,2),
                'signal':res['signal'],'confidence':res['confidence'],
                'reason':res['reason'],'sentiment':sent,'indicators':res['indicators'],
                'cooldown':is_in_cooldown(pair),
            })
        except Exception as e:
            logger.error(f'Cache {pair}:{e}')
            pair_data.append({'symbol':pair,'price':0,'change':0,'signal':'HOLD',
                              'confidence':0,'reason':'Error','sentiment':50,'indicators':{},'cooldown':False})
    _cache['pairs']     =pair_data
    _cache['sentiments']={p['symbol']:p['sentiment'] for p in pair_data}
    from datetime import datetime
    _cache['last_update']=datetime.utcnow().isoformat()
    logger.info('Cache refreshed')

def start_cache_refresh():
    t=threading.Thread(target=refresh_pair_cache,daemon=True)
    t.start()

def get_dashboard_data():
    cfg   =get_config(); mode=cfg['mode']
    open_t=get_open_trades(); recent=get_recent_trades(30)
    for t in recent:
        if t.get('status')=='open':
            cached=next((p for p in _cache['pairs'] if p['symbol']==t['pair']),None)
            cp=cached['price'] if cached and cached['price'] else None
            if cp:
                t['unrealized_pnl']=round((cp-t['entry_price'])*t['quantity'] if t['side']=='BUY' else (t['entry_price']-cp)*t['quantity'],2)
                t['current_price']=cp
    pairs_raw=get_pairs_list()
    pair_data=_cache['pairs'] if _cache['pairs'] else [
        {'symbol':p,'price':0,'change':0,'signal':'--','confidence':0,
         'reason':'Loading...','sentiment':50,'indicators':{},'cooldown':False}
        for p in pairs_raw]
    bal=get_demo_balance() if mode=='demo' else get_balance().get('USDT',0)
    return {
        'mode':mode,'bot_running':_s('bot_running','false')=='true',
        'stats':get_stats(),'open_trades':open_t,'recent_trades':recent,
        'pairs':pair_data,'news':get_news(15),
        'sentiments':_cache.get('sentiments',{}),'usdt_balance':round(bal,2),
        'last_update':_cache.get('last_update'),
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
            'use_llm_filter':        _s('use_llm_filter','true'),
            'mtf_enabled':           _s('mtf_enabled','true'),
            'anthropic_key_set':     bool(_s('anthropic_api_key','')),
            'scanner_enabled':       _s('scanner_enabled','true'),
            'scanner_auto_update':   _s('scanner_auto_update','true'),
            'last_scan_at':          _s('last_scan_at',''),
            'pinned_pairs':          _s('pinned_pairs','BTC/USDT,ETH/USDT'),
        }
    }
