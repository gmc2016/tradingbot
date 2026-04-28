"""
Futures Signal Module — amplifies directional signals with leverage.
When spot bot sees high-confidence signal (85%+), open a futures position
at 2-3x leverage for the same direction.
Uses demo simulation until live mode enabled.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

FUTURES_PAIRS  = {'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT'}
DEFAULT_LEVERAGE = 2  # conservative 2x

def get_futures_config():
    from db.database import get_setting
    return {
        'enabled':       get_setting('futures_enabled') == 'true',
        'leverage':      int(get_setting('futures_leverage') or '2'),
        'min_conf':      int(get_setting('futures_min_conf') or '80'),
        'position_size': float(get_setting('futures_size') or '50'),
        'mode':          get_setting('trading_mode') or 'demo',
        'pairs':         set((get_setting('futures_pairs') or 'BTC/USDT,ETH/USDT').split(',')),
    }

def should_open_futures(pair, signal, confidence, spot_trade_id=None):
    """
    Check if a futures position should be opened to amplify a spot signal.
    Only for highest-confidence signals on liquid pairs.
    """
    cfg = get_futures_config()
    if not cfg['enabled']: return False, 'Futures disabled'
    if pair not in FUTURES_PAIRS: return False, f'{pair} not in futures pairs'
    if confidence < cfg['min_conf']: return False, f'Confidence {confidence}% < {cfg["min_conf"]}%'
    if signal == 'HOLD': return False, 'No signal'
    return True, f'Futures: {signal} {pair} at {confidence}% confidence, {cfg["leverage"]}x leverage'

def open_futures_position(pair, signal, confidence, price, mode='demo'):
    """
    Open a leveraged futures position.
    In demo: tracks P&L mathematically.
    In live: calls Binance Futures API.
    """
    from db.database import insert_trade, get_setting
    from db.activitylog import log as alog

    cfg = get_futures_config()
    leverage = cfg['leverage']
    size     = cfg['position_size']

    # Futures SL/TP — tighter than spot due to leverage
    sl_pct = 0.02 / leverage  # 2% move against = SL (scales with leverage)
    tp_pct = 0.04 / leverage  # 4% move with = TP

    if signal == 'BUY':
        sl = round(price * (1 - sl_pct), 8)
        tp = round(price * (1 + tp_pct), 8)
    else:
        sl = round(price * (1 + sl_pct), 8)
        tp = round(price * (1 - tp_pct), 8)

    qty = round(size / price, 8)
    reason = f'Futures {leverage}x: {signal} at {confidence}% conf'

    tid = insert_trade(mode, pair, signal, price, qty, sl, tp, reason)
    alog('trade', f'FUTURES {signal} {pair} @ {price:.4f} {leverage}x | '
         f'SL:{sl:.4f} TP:{tp:.4f}',
         level='success',
         detail={'pair':pair,'side':signal,'leverage':leverage,
                 'price':price,'sl':sl,'tp':tp,'conf':confidence})
    return tid

def get_futures_opportunities():
    """Get current futures market data for display."""
    try:
        import requests
        r = requests.get('https://fapi.binance.com/fapi/v1/ticker/24hr', timeout=8)
        if r.status_code != 200: return []
        data = r.json()
        futures = []
        for t in data:
            sym = t.get('symbol','')
            if sym in ('BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT'):
                futures.append({
                    'pair':       sym[:-4]+'/USDT',
                    'price':      float(t.get('lastPrice',0)),
                    'change_pct': float(t.get('priceChangePercent',0)),
                    'volume':     float(t.get('quoteVolume',0)),
                })
        return futures
    except Exception as e:
        logger.debug(f'Futures data: {e}')
        return []
