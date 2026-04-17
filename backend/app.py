import os, sys, logging, json, threading, eventlet
sys.path.insert(0, '/app')
eventlet.monkey_patch()

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler

from db.database import (init_db, get_setting, set_setting,
                          get_recent_trades, get_news, get_all_trades)
from bot.engine import scan_and_trade, get_dashboard_data, start_cache_refresh, refresh_pair_cache
from ai.sentiment import fetch_and_analyze

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='/app/static', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'changeme')
CORS(app, origins='*')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
scheduler = BackgroundScheduler()

# ── Real-time price stream ─────────────────────────────────────────────────────
_prices    = {}
_ws_thread = None

def start_price_stream():
    global _ws_thread
    if _ws_thread and _ws_thread.is_alive(): return

    def run():
        import websocket as ws_lib
        def build_url():
            pairs_raw = get_setting('active_pairs') or 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT'
            streams   = '/'.join([p.strip().replace('/','').lower()+'@miniTicker'
                                  for p in pairs_raw.split(',')])
            return f'wss://stream.binance.com:9443/stream?streams={streams}'

        def on_message(ws, message):
            try:
                data   = json.loads(message)
                ticker = data.get('data', {})
                sym    = ticker.get('s', '')
                if not sym: return
                pair   = sym[:-4]+'/USDT' if sym.endswith('USDT') else sym
                price  = float(ticker.get('c', 0))
                open_p = float(ticker.get('o', price))
                change = round(((price-open_p)/open_p*100) if open_p else 0, 2)
                _prices[pair] = {'price': price, 'change': change}
                socketio.emit('price_update', {'pair': pair, 'price': price, 'change': change})
            except Exception as e: logger.debug(f'Price tick error: {e}')

        def on_error(ws, error): logger.warning(f'Price stream error: {error}')
        def on_close(ws, *args):
            logger.info('Price stream closed, reconnecting...')
            eventlet.sleep(5); run()
        def on_open(ws): logger.info('Price stream connected')

        try:
            wsa = ws_lib.WebSocketApp(build_url(), on_message=on_message,
                                       on_error=on_error, on_close=on_close, on_open=on_open)
            wsa.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e: logger.error(f'Price stream failed: {e}')

    _ws_thread = threading.Thread(target=run, daemon=True)
    _ws_thread.start()

# ── Scheduler ──────────────────────────────────────────────────────────────────
def push():
    try: socketio.emit('dashboard_update', get_dashboard_data())
    except Exception as e: logger.error(f'Push error: {e}')

def bot_cycle():
    try: scan_and_trade(); refresh_pair_cache(); push()
    except Exception as e: logger.error(f'Bot cycle: {e}')

def news_cycle():
    try: fetch_and_analyze(); push()
    except Exception as e: logger.error(f'News cycle: {e}')

scheduler.add_job(bot_cycle,  'interval', minutes=5,  id='bot')
scheduler.add_job(news_cycle, 'interval', minutes=15, id='news')
scheduler.add_job(lambda: (refresh_pair_cache(), push()), 'interval', minutes=1, id='cache')
scheduler.start()

start_cache_refresh()
eventlet.spawn_after(3, start_price_stream)

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def spa(path=None): return send_from_directory('/app/static', 'index.html')

@app.route('/api/status')
def status(): return jsonify({'ok':True,'mode':get_setting('trading_mode'),
                               'bot_running':get_setting('bot_running')=='true'})

@app.route('/api/dashboard')
def dashboard():
    try: return jsonify(get_dashboard_data())
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/bot/start',  methods=['POST'])
def start(): set_setting('bot_running','true');  push(); return jsonify({'ok':True})

@app.route('/api/bot/stop',   methods=['POST'])
def stop():  set_setting('bot_running','false'); push(); return jsonify({'ok':True})

@app.route('/api/bot/mode',   methods=['POST'])
def set_mode():
    m = request.json.get('mode','demo')
    if m not in ('demo','live'): return jsonify({'error':'Invalid'}), 400
    set_setting('trading_mode', m); push(); return jsonify({'ok':True,'mode':m})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    keys = ['max_positions','stop_loss_pct','take_profit_pct','position_size_usdt',
            'trading_mode','active_pairs','bot_running','starting_balance',
            'trailing_stop_enabled','trailing_stop_pct',
            'partial_close_enabled','partial_close_at_pct','partial_close_size_pct']
    data = {k: get_setting(k) for k in keys}
    data['binance_api_key']    = '***' if get_setting('binance_api_key')    else ''
    data['binance_api_secret'] = '***' if get_setting('binance_api_secret') else ''
    data['newsapi_key']        = '***' if get_setting('newsapi_key')        else ''
    return jsonify(data)

@app.route('/api/settings', methods=['POST'])
def upd_settings():
    data = request.json or {}
    for k in ['max_positions','stop_loss_pct','take_profit_pct','position_size_usdt',
              'active_pairs','starting_balance','trailing_stop_enabled','trailing_stop_pct',
              'partial_close_enabled','partial_close_at_pct','partial_close_size_pct']:
        if k in data: set_setting(k, str(data[k]))
    for k in ['binance_api_key','binance_api_secret','newsapi_key']:
        if k in data and data[k] and data[k] != '***':
            set_setting(k, str(data[k]))
            logger.info(f'Updated {k}')
    return jsonify({'ok':True})

@app.route('/api/trades')
def trades(): return jsonify(get_recent_trades(int(request.args.get('limit',50))))

@app.route('/api/trades/history')
def trade_history():
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    pair     = request.args.get('pair')
    status   = request.args.get('status')
    return jsonify(get_all_trades(page=page, per_page=per_page, pair=pair, status=status))

@app.route('/api/news')
def news(): return jsonify(get_news(20))

@app.route('/api/news/refresh', methods=['POST'])
def ref_news(): fetch_and_analyze(); push(); return jsonify({'ok':True})

@app.route('/api/news/test')
def news_test():
    from ai.sentiment import get_newsapi_key
    key = get_newsapi_key()
    if not key: return jsonify({'error': 'No NewsAPI key saved'})
    try:
        import requests as req
        r = req.get('https://newsapi.org/v2/everything', timeout=15,
                    params={'q':'bitcoin','apiKey':key,'pageSize':3,'language':'en'})
        return jsonify({'status': r.status_code, 'body': r.json()})
    except Exception as e: return jsonify({'error': str(e)})

@app.route('/api/ohlcv')
def ohlcv():
    from bot.exchange import fetch_ohlcv
    df = fetch_ohlcv(request.args.get('symbol','BTC/USDT'),
                     request.args.get('timeframe','1h'),
                     int(request.args.get('limit',100)))
    if df is None: return jsonify({'error':'Failed'}), 500
    df = df.reset_index(); df['timestamp'] = df['timestamp'].astype(str)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/bot/run_now', methods=['POST'])
def run_now():
    try: scan_and_trade(); refresh_pair_cache(); push(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/prices')
def get_prices(): return jsonify(_prices)

@socketio.on('connect')
def on_connect():
    logger.info('Client connected')
    try: emit('dashboard_update', get_dashboard_data())
    except Exception as e: logger.error(f'Connect push: {e}')

if __name__ == '__main__':
    init_db()
    logger.info('Trading Bot starting on port 5000...')
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
