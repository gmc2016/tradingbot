import os, ccxt, pandas as pd, logging
from datetime import datetime

logger = logging.getLogger(__name__)
API_KEY    = os.environ.get('BINANCE_API_KEY', '')
API_SECRET = os.environ.get('BINANCE_API_SECRET', '')

def get_exchange():
    return ccxt.binance({
        'apiKey': API_KEY, 'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType':'spot','adjustForTimeDifference':True}})

def fetch_ohlcv(symbol, timeframe='1h', limit=300):
    try:
        raw = get_exchange().fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df  = pd.DataFrame(raw, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        logger.error(f'OHLCV error {symbol}: {e}'); return None

def fetch_ticker(symbol):
    try: return get_exchange().fetch_ticker(symbol)
    except Exception as e: logger.error(f'Ticker error {symbol}: {e}'); return None

def get_balance():
    if not API_KEY or not API_SECRET: return {}
    try: return get_exchange().fetch_balance().get('total', {})
    except Exception as e: logger.error(f'Balance error: {e}'); return {}

def place_market_order(symbol, side, quantity, mode='demo'):
    ticker = fetch_ticker(symbol)
    if not ticker: return None
    price = ticker['last']
    if mode == 'demo':
        return {'id': f'DEMO_{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}',
                'symbol':symbol,'side':side,'price':price,
                'amount':quantity,'filled':quantity,'status':'closed','demo':True}
    if not API_KEY or not API_SECRET:
        raise ValueError('API keys not configured')
    try: return get_exchange().create_market_order(symbol, side.lower(), quantity)
    except Exception as e: logger.error(f'Order error {symbol}: {e}'); raise

def calculate_quantity(symbol, usdt_amount, price):
    try:
        ex  = get_exchange()
        qty = usdt_amount / price
        return float(ex.amount_to_precision(symbol, qty))
    except: return round(usdt_amount / price, 6)
