import os, sys, logging, eventlet
sys.path.insert(0, '/app')
eventlet.monkey_patch()

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler

from db.database import init_db, get_setting, set_setting, get_recent_trades, get_news
from bot.engine import scan_and_trade, get_dashboard_data, start_cache_refresh, refresh_pair_cache
from ai.sentiment import fetch_and_analyze

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='/app/static', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'changeme')
CORS(app, origins='*')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
scheduler = BackgroundScheduler()

def push():
    try: socketio.emit('dashboard_update', get_dashboard_data())
    except Exception as e: logger.error(f'Push error: {e}')

def bot_cycle():
    try:
        scan_and_trade()
        refresh_pair_cache()
        push()
    except Exception as e: logger.error(f'Bot cycle: {e}')

def news_cycle():
    try: fetch_and_analyze(); push()
    except Exception as e: logger.error(f'News cycle: {e}')

scheduler.add_job(bot_cycle,  'interval', minutes=5,  id='bot')
scheduler.add_job(news_cycle, 'interval', minutes=15, id='news')
# Refresh pair cache every 60s so prices stay current even when bot is idle
scheduler.add_job(lambda: (refresh_pair_cache(), push()), 'interval', minutes=1, id='cache')
scheduler.start()

# Kick off background cache warm-up immediately on start
start_cache_refresh()

@app.route('/')
@app.route('/<path:path>')
def spa(path=None):
    return send_from_directory('/app/static', 'index.html')

@app.route('/api/status')
def status():
    return jsonify({'ok':True,'mode':get_setting('trading_mode'),
                    'bot_running':get_setting('bot_running')=='true'})

@app.route('/api/dashboard')
def dashboard():
    try: return jsonify(get_dashboard_data())
    except Exception as e: logger.error(f'Dashboard: {e}'); return jsonify({'error':str(e)}), 500

@app.route('/api/bot/start', methods=['POST'])
def start(): set_setting('bot_running','true'); push(); return jsonify({'ok':True})

@app.route('/api/bot/stop', methods=['POST'])
def stop(): set_setting('bot_running','false'); push(); return jsonify({'ok':True})

@app.route('/api/bot/mode', methods=['POST'])
def set_mode():
    m = request.json.get('mode','demo')
    if m not in ('demo','live'): return jsonify({'error':'Invalid'}), 400
    set_setting('trading_mode', m); push(); return jsonify({'ok':True,'mode':m})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({k:get_setting(k) for k in [
        'max_positions','stop_loss_pct','take_profit_pct',
        'position_size_usdt','trading_mode','active_pairs','bot_running','starting_balance']})

@app.route('/api/settings', methods=['POST'])
def upd_settings():
    for k in ['max_positions','stop_loss_pct','take_profit_pct',
              'position_size_usdt','active_pairs','starting_balance']:
        if k in request.json: set_setting(k, str(request.json[k]))
    return jsonify({'ok':True})

@app.route('/api/trades')
def trades(): return jsonify(get_recent_trades(int(request.args.get('limit',50))))

@app.route('/api/news')
def news(): return jsonify(get_news(20))

@app.route('/api/ohlcv')
def ohlcv():
    from bot.exchange import fetch_ohlcv
    df = fetch_ohlcv(request.args.get('symbol','BTC/USDT'),
                     request.args.get('timeframe','1h'),
                     int(request.args.get('limit',100)))
    if df is None: return jsonify({'error':'Failed'}), 500
    df = df.reset_index(); df['timestamp'] = df['timestamp'].astype(str)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/news/refresh', methods=['POST'])
def ref_news(): fetch_and_analyze(); push(); return jsonify({'ok':True})

@app.route('/api/bot/run_now', methods=['POST'])
def run_now():
    try: scan_and_trade(); refresh_pair_cache(); push(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'error':str(e)}), 500

@socketio.on('connect')
def on_connect():
    logger.info('Client connected')
    try: emit('dashboard_update', get_dashboard_data())
    except Exception as e: logger.error(f'Connect push: {e}')

if __name__ == '__main__':
    init_db()
    logger.info('Trading Bot starting on port 5000...')
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
