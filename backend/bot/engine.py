import logging, threading
from bot.exchange import fetch_ohlcv, fetch_ticker, place_market_order, calculate_quantity, get_balance
from bot.strategy import generate_signal
from ai.sentiment import get_pair_sentiment, fetch_and_analyze
from db.database import (get_setting, set_setting, insert_trade, close_trade,
                          get_open_trades, get_recent_trades, get_stats, get_news)

logger = logging.getLogger(__name__)

_demo = {'balance': 1000.0, 'init': False}

# In-memory cache so dashboard returns instantly
_cache = {
    'pairs': [],
    'sentiments': {},
    'last_update': None,
}

def get_demo_balance():
    if not _demo['init']:
        try: _demo['balance'] = float(get_setting('starting_balance') or 1000)
        except: _demo['balance'] = 1000.0
        _demo['init'] = True
    return _demo['balance']

def adj_demo(d): _demo['balance'] += d

def get_config():
    return {
        'max_positions':      int(get_setting('max_positions') or 3),
        'stop_loss_pct':      float(get_setting('stop_loss_pct') or 1.5) / 100,
        'take_profit_pct':    float(get_setting('take_profit_pct') or 3.0) / 100,
        'position_size_usdt': float(get_setting('position_size_usdt') or 100),
        'mode':               get_setting('trading_mode') or 'demo'}

def get_pairs_list():
    raw = get_setting('active_pairs') or 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT'
    return [p.strip() for p in raw.split(',')]

def check_open_positions():
    for t in get_open_trades():
        ticker = fetch_ticker(t['pair'])
        if not ticker: continue
        cp  = ticker['last']; side = t['side']
        hit = (cp <= t['stop_loss'] or cp >= t['take_profit']) if side=='BUY' \
              else (cp >= t['stop_loss'] or cp <= t['take_profit'])
        if hit:
            pnl = (cp-t['entry_price'])*t['quantity'] if side=='BUY' \
                  else (t['entry_price']-cp)*t['quantity']
            try: place_market_order(t['pair'], 'SELL' if side=='BUY' else 'BUY', t['quantity'], mode=t['mode'])
            except: continue
            close_trade(t['id'], cp, pnl)
            if t['mode'] == 'demo': adj_demo(pnl)
            logger.info(f"Closed {t['pair']} {side} PnL:{pnl:.2f}")

def scan_and_trade():
    if get_setting('bot_running') != 'true': return
    cfg = get_config(); mode = cfg['mode']
    check_open_positions()
    open_t     = get_open_trades()
    open_pairs = {t['pair'] for t in open_t}
    open_cnt   = len(open_t)
    if open_cnt >= cfg['max_positions']: return
    for pair in get_pairs_list():
        if pair in open_pairs or open_cnt >= cfg['max_positions']: continue
        df   = fetch_ohlcv(pair, timeframe='1h', limit=300)
        if df is None or len(df) < 50: continue
        sent = get_pair_sentiment(pair)
        res  = generate_signal(df, sentiment_score=sent)
        sig  = res['signal']; conf = res['confidence']; reason = res['reason']
        logger.info(f'{pair}: {sig} ({conf}%) {reason}')
        if sig in ('BUY','SELL') and conf >= 55:
            ticker = fetch_ticker(pair)
            if not ticker: continue
            price = ticker['last']; pos = cfg['position_size_usdt']
            avail = get_demo_balance() if mode=='demo' else get_balance().get('USDT', 0)
            if avail < pos: logger.warning(f'Low balance: {avail:.2f}'); continue
            qty = calculate_quantity(pair, pos, price)
            sl  = round(price*(1-cfg['stop_loss_pct']),  8) if sig=='BUY' else round(price*(1+cfg['stop_loss_pct']),  8)
            tp  = round(price*(1+cfg['take_profit_pct']),8) if sig=='BUY' else round(price*(1-cfg['take_profit_pct']),8)
            try:
                order = place_market_order(pair, sig, qty, mode=mode)
                fill  = order.get('price', price)
                tid   = insert_trade(mode, pair, sig, fill, qty, sl, tp, reason, order.get('id'))
                if mode == 'demo': adj_demo(-pos)
                open_cnt += 1
                logger.info(f'Opened {sig} {pair}@{fill} id={tid}')
            except Exception as e: logger.error(f'Order failed {pair}: {e}')

def refresh_pair_cache():
    """Background thread: fetch prices + signals for all pairs, update cache."""
    pairs_raw = get_pairs_list()
    pair_data = []
    for pair in pairs_raw:
        try:
            ticker = fetch_ticker(pair)
            price  = ticker['last'] if ticker else 0
            change = ticker.get('percentage', 0) if ticker else 0
            df     = fetch_ohlcv(pair, timeframe='1h', limit=100)
            sent   = get_pair_sentiment(pair)
            res    = {'signal':'HOLD','confidence':0,'reason':'Loading...','indicators':{}}
            if df is not None and len(df) >= 50:
                res = generate_signal(df, sentiment_score=sent)
            pair_data.append({
                'symbol':pair,'price':price,'change':round(change,2),
                'signal':res['signal'],'confidence':res['confidence'],
                'reason':res['reason'],'sentiment':sent,'indicators':res['indicators']})
        except Exception as e:
            logger.error(f'Cache refresh error {pair}: {e}')
            pair_data.append({'symbol':pair,'price':0,'change':0,
                              'signal':'HOLD','confidence':0,'reason':'Error','sentiment':50,'indicators':{}})
    _cache['pairs'] = pair_data
    _cache['sentiments'] = {p['symbol']: p['sentiment'] for p in pair_data}
    from datetime import datetime
    _cache['last_update'] = datetime.utcnow().isoformat()
    logger.info('Pair cache refreshed')

def start_cache_refresh():
    """Fire background refresh without blocking."""
    t = threading.Thread(target=refresh_pair_cache, daemon=True)
    t.start()

def get_dashboard_data():
    """
    Returns immediately using cached pair data.
    If cache is empty, returns skeleton data so UI loads instantly.
    """
    cfg    = get_config(); mode = cfg['mode']
    open_t = get_open_trades()
    recent = get_recent_trades(30)

    # Enrich open trades with unrealized PnL from cache
    for t in recent:
        if t.get('status') == 'open':
            # Try to get price from cache first
            cached = next((p for p in _cache['pairs'] if p['symbol']==t['pair']), None)
            cp = cached['price'] if cached and cached['price'] else None
            if cp:
                t['unrealized_pnl'] = round((cp-t['entry_price'])*t['quantity'] if t['side']=='BUY'
                                            else (t['entry_price']-cp)*t['quantity'], 2)
                t['current_price']  = cp

    # Use cache if available, else return empty skeletons so UI still loads
    pairs_raw = get_pairs_list()
    if _cache['pairs']:
        pair_data = _cache['pairs']
    else:
        pair_data = [{'symbol':p,'price':0,'change':0,'signal':'--',
                      'confidence':0,'reason':'Loading...','sentiment':50,'indicators':{}}
                     for p in pairs_raw]

    bal = get_demo_balance() if mode=='demo' else get_balance().get('USDT', 0)

    return {
        'mode':        mode,
        'bot_running': get_setting('bot_running') == 'true',
        'stats':       get_stats(),
        'open_trades': open_t,
        'recent_trades': recent,
        'pairs':       pair_data,
        'news':        get_news(15),
        'sentiments':  _cache.get('sentiments', {}),
        'usdt_balance': round(bal, 2),
        'last_update': _cache.get('last_update'),
        'config': {
            'max_positions':      cfg['max_positions'],
            'stop_loss_pct':      get_setting('stop_loss_pct'),
            'take_profit_pct':    get_setting('take_profit_pct'),
            'position_size_usdt': get_setting('position_size_usdt'),
            'active_pairs':       pairs_raw,
            'starting_balance':   get_setting('starting_balance'),
        }
    }
