import logging, threading
from bot.exchange import fetch_ohlcv, fetch_ticker, place_market_order, calculate_quantity, get_balance
from bot.strategy import generate_signal, set_cooldown, is_in_cooldown
from ai.sentiment import get_pair_sentiment, fetch_and_analyze
from db.database import (get_setting, set_setting, insert_trade, close_trade,
                          partial_close_trade, update_trailing_stop,
                          get_open_trades, get_recent_trades, get_stats, get_news)

logger = logging.getLogger(__name__)

_demo  = {'balance': 1000.0, 'init': False}
_cache = {'pairs': [], 'sentiments': {}, 'last_update': None}

# Consecutive loss tracker per pair (Agno-inspired risk management)
_loss_streak = {}

def get_demo_balance():
    if not _demo['init']:
        try: _demo['balance'] = float(get_setting('starting_balance') or 1000)
        except: _demo['balance'] = 1000.0
        _demo['init'] = True
    return _demo['balance']

def adj_demo(d): _demo['balance'] += d

def get_config():
    return {
        'max_positions':        int(get_setting('max_positions') or 5),
        'stop_loss_pct':        float(get_setting('stop_loss_pct') or 1.5) / 100,
        'take_profit_pct':      float(get_setting('take_profit_pct') or 3.0) / 100,
        'position_size_usdt':   float(get_setting('position_size_usdt') or 100),
        'mode':                 get_setting('trading_mode') or 'demo',
        'trailing_stop':        get_setting('trailing_stop_enabled') == 'true',
        'trailing_stop_pct':    float(get_setting('trailing_stop_pct') or 0.8) / 100,
        'partial_close':        get_setting('partial_close_enabled') == 'true',
        'partial_close_at_pct': float(get_setting('partial_close_at_pct') or 1.5) / 100,
        'partial_close_size':   float(get_setting('partial_close_size_pct') or 50) / 100,
        'strategy':             get_setting('strategy_mode') or 'combined',
        'max_loss_streak':      int(get_setting('max_loss_streak') or 3),
        'cooldown_minutes':     int(get_setting('cooldown_minutes') or 60),
    }

def get_pairs_list():
    raw = get_setting('active_pairs') or 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,ADA/USDT,DOGE/USDT,AVAX/USDT'
    return [p.strip() for p in raw.split(',') if p.strip()]

def check_open_positions():
    cfg = get_config()
    for t in get_open_trades():
        ticker = fetch_ticker(t['pair'])
        if not ticker: continue
        cp    = ticker['last']
        side  = t['side']
        entry = t['entry_price']
        sl    = t['stop_loss']
        tp    = t['take_profit']
        qty   = t['quantity']
        mode  = t['mode']

        pnl_pct = (cp-entry)/entry if side=='BUY' else (entry-cp)/entry

        # ── Partial close ─────────────────────────────────────────────────
        if (cfg['partial_close'] and
                pnl_pct >= cfg['partial_close_at_pct'] and
                qty > 0 and not t.get('trailing_stop')):
            close_qty = round(qty * cfg['partial_close_size'], 8)
            remain    = round(qty - close_qty, 8)
            if close_qty > 0 and remain > 0:
                partial_pnl = (cp-entry)*close_qty if side=='BUY' else (entry-cp)*close_qty
                try:
                    place_market_order(t['pair'], 'SELL' if side=='BUY' else 'BUY', close_qty, mode=mode)
                    partial_close_trade(t['id'], remain, partial_pnl)
                    if mode == 'demo': adj_demo(partial_pnl)
                    logger.info(f"Partial close {t['pair']} {close_qty:.6f} PnL:{partial_pnl:.2f}")
                except Exception as e:
                    logger.error(f'Partial close error: {e}')

        # ── Trailing stop ──────────────────────────────────────────────────
        if cfg['trailing_stop'] and pnl_pct >= cfg['trailing_stop_pct']:
            if side == 'BUY':
                new_sl = round(cp * (1 - cfg['trailing_stop_pct']), 8)
                if new_sl > sl:
                    update_trailing_stop(t['id'], new_sl); sl = new_sl
                    logger.info(f"Trail {t['pair']} SL→{new_sl:.6f}")
            else:
                new_sl = round(cp * (1 + cfg['trailing_stop_pct']), 8)
                if new_sl < sl:
                    update_trailing_stop(t['id'], new_sl); sl = new_sl
                    logger.info(f"Trail {t['pair']} SL→{new_sl:.6f}")

        # ── Full close ─────────────────────────────────────────────────────
        hit = (cp <= sl or cp >= tp) if side=='BUY' else (cp >= sl or cp <= tp)
        if hit:
            pnl = (cp-entry)*qty if side=='BUY' else (entry-cp)*qty
            try:
                place_market_order(t['pair'], 'SELL' if side=='BUY' else 'BUY', qty, mode=mode)
            except: continue
            close_trade(t['id'], cp, pnl)
            if mode == 'demo': adj_demo(pnl)
            closed_by = 'TP' if ((side=='BUY' and cp>=tp) or (side=='SELL' and cp<=tp)) else 'SL'
            logger.info(f"Closed {t['pair']} {side} {closed_by} PnL:{pnl:.2f}")

            # Track loss streaks (Agno-style risk management)
            if pnl < 0:
                _loss_streak[t['pair']] = _loss_streak.get(t['pair'], 0) + 1
                if _loss_streak[t['pair']] >= cfg['max_loss_streak']:
                    set_cooldown(t['pair'], cfg['cooldown_minutes'])
                    _loss_streak[t['pair']] = 0
                    logger.warning(f"Cooldown triggered for {t['pair']} after {cfg['max_loss_streak']} consecutive losses")
            else:
                _loss_streak[t['pair']] = 0  # reset on win

def scan_and_trade():
    if get_setting('bot_running') != 'true': return
    cfg        = get_config(); mode = cfg['mode']
    check_open_positions()
    open_t     = get_open_trades()
    open_pairs = {t['pair'] for t in open_t}
    open_cnt   = len(open_t)
    if open_cnt >= cfg['max_positions']: return

    for pair in get_pairs_list():
        if pair in open_pairs or open_cnt >= cfg['max_positions']: continue
        if is_in_cooldown(pair):
            logger.info(f'{pair}: in cooldown, skipping')
            continue

        df = fetch_ohlcv(pair, timeframe='1h', limit=300)
        if df is None or len(df) < 50: continue

        sent   = get_pair_sentiment(pair)
        result = generate_signal(df, sentiment_score=sent, strategy=cfg['strategy'])
        sig    = result['signal']
        conf   = result['confidence']
        reason = result['reason']
        # ATR-based SL/TP from Donchian (may be None for confluence-only)
        sl_price = result.get('sl_price')
        tp_price = result.get('tp_price')

        logger.info(f'{pair}: {sig} ({conf}%) {reason}')

        if sig in ('BUY','SELL') and conf >= 55:
            ticker = fetch_ticker(pair)
            if not ticker: continue
            price = ticker['last']; pos = cfg['position_size_usdt']
            avail = get_demo_balance() if mode=='demo' else get_balance().get('USDT', 0)
            if avail < pos: logger.warning(f'Low balance: {avail:.2f}'); continue

            qty = calculate_quantity(pair, pos, price)

            # Use ATR-based SL/TP if available (Donchian), else use config %
            if sl_price and tp_price:
                sl = sl_price; tp = tp_price
            else:
                sl = round(price*(1-cfg['stop_loss_pct']),  8) if sig=='BUY' else round(price*(1+cfg['stop_loss_pct']),  8)
                tp = round(price*(1+cfg['take_profit_pct']),8) if sig=='BUY' else round(price*(1-cfg['take_profit_pct']),8)

            try:
                order = place_market_order(pair, sig, qty, mode=mode)
                fill  = order.get('price', price)
                tid   = insert_trade(mode, pair, sig, fill, qty, sl, tp, reason, order.get('id'))
                if mode == 'demo': adj_demo(-pos)
                open_cnt += 1
                logger.info(f'Opened {sig} {pair}@{fill} SL:{sl:.6f} TP:{tp:.6f} id={tid}')
            except Exception as e:
                logger.error(f'Order failed {pair}: {e}')

def refresh_pair_cache():
    pairs_raw = get_pairs_list()
    pair_data = []
    cfg       = get_config()
    for pair in pairs_raw:
        try:
            ticker = fetch_ticker(pair)
            price  = ticker['last'] if ticker else 0
            change = ticker.get('percentage', 0) if ticker else 0
            df     = fetch_ohlcv(pair, timeframe='1h', limit=100)
            sent   = get_pair_sentiment(pair)
            res    = {'signal':'HOLD','confidence':0,'reason':'Loading...','indicators':{}}
            if df is not None and len(df) >= 50:
                res = generate_signal(df, sentiment_score=sent, strategy=cfg['strategy'])
            cooldown = is_in_cooldown(pair)
            pair_data.append({
                'symbol':pair,'price':price,'change':round(change,2),
                'signal':res['signal'],'confidence':res['confidence'],
                'reason':res['reason'],'sentiment':sent,'indicators':res['indicators'],
                'cooldown': cooldown,
            })
        except Exception as e:
            logger.error(f'Cache refresh error {pair}: {e}')
            pair_data.append({'symbol':pair,'price':0,'change':0,'signal':'HOLD',
                              'confidence':0,'reason':'Error','sentiment':50,'indicators':{},'cooldown':False})
    _cache['pairs']      = pair_data
    _cache['sentiments'] = {p['symbol']: p['sentiment'] for p in pair_data}
    from datetime import datetime
    _cache['last_update'] = datetime.utcnow().isoformat()
    logger.info('Pair cache refreshed')

def start_cache_refresh():
    t = threading.Thread(target=refresh_pair_cache, daemon=True)
    t.start()

def get_dashboard_data():
    cfg    = get_config(); mode = cfg['mode']
    open_t = get_open_trades()
    recent = get_recent_trades(30)
    for t in recent:
        if t.get('status') == 'open':
            cached = next((p for p in _cache['pairs'] if p['symbol']==t['pair']), None)
            cp = cached['price'] if cached and cached['price'] else None
            if cp:
                t['unrealized_pnl'] = round((cp-t['entry_price'])*t['quantity'] if t['side']=='BUY'
                                            else (t['entry_price']-cp)*t['quantity'], 2)
                t['current_price']  = cp
    pairs_raw = get_pairs_list()
    pair_data = _cache['pairs'] if _cache['pairs'] else [
        {'symbol':p,'price':0,'change':0,'signal':'--','confidence':0,
         'reason':'Loading...','sentiment':50,'indicators':{},'cooldown':False}
        for p in pairs_raw]
    bal = get_demo_balance() if mode=='demo' else get_balance().get('USDT', 0)
    return {
        'mode':          mode,
        'bot_running':   get_setting('bot_running') == 'true',
        'stats':         get_stats(),
        'open_trades':   open_t,
        'recent_trades': recent,
        'pairs':         pair_data,
        'news':          get_news(15),
        'sentiments':    _cache.get('sentiments', {}),
        'usdt_balance':  round(bal, 2),
        'last_update':   _cache.get('last_update'),
        'config': {
            'max_positions':         cfg['max_positions'],
            'stop_loss_pct':         get_setting('stop_loss_pct'),
            'take_profit_pct':       get_setting('take_profit_pct'),
            'position_size_usdt':    get_setting('position_size_usdt'),
            'active_pairs':          pairs_raw,
            'starting_balance':      get_setting('starting_balance'),
            'trailing_stop_enabled': get_setting('trailing_stop_enabled'),
            'trailing_stop_pct':     get_setting('trailing_stop_pct'),
            'partial_close_enabled': get_setting('partial_close_enabled'),
            'partial_close_at_pct':  get_setting('partial_close_at_pct'),
            'partial_close_size_pct':get_setting('partial_close_size_pct'),
            'strategy_mode':         get_setting('strategy_mode') or 'combined',
            'max_loss_streak':       get_setting('max_loss_streak') or '3',
            'cooldown_minutes':      get_setting('cooldown_minutes') or '60',
        }
    }
