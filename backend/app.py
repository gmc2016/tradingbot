import os, sys, logging, json, threading, secrets, eventlet
sys.path.insert(0, '/app')
eventlet.monkey_patch()

from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
from functools import wraps

from db.database import (init_db, init_auth, get_setting, set_setting,
                          get_recent_trades, get_news, get_all_trades,
                          check_login, change_password)
from bot.engine import scan_and_trade, get_dashboard_data, start_cache_refresh, refresh_pair_cache, open_manual_trade, close_manual_trade
from bot.scanner import run_scanner, apply_scanner_results
from ai.brain import run_brain_cycle, apply_brain_recommendations, get_brain_log
from bot.account import get_full_account_status
from ai.sentiment import fetch_and_analyze

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='/app/static', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', secrets.token_hex(32))
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = False
CORS(app, origins='*', supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
scheduler = BackgroundScheduler()

# ── Auth decorator ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized', 'login_required': True}), 401
        return f(*args, **kwargs)
    return decorated

# ── Price stream ───────────────────────────────────────────────────────────────
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
                data   = json.loads(message); ticker = data.get('data', {})
                sym    = ticker.get('s', '')
                if not sym: return
                pair   = sym[:-4]+'/USDT' if sym.endswith('USDT') else sym
                price  = float(ticker.get('c', 0))
                open_p = float(ticker.get('o', price))
                change = round(((price-open_p)/open_p*100) if open_p else 0, 2)
                _prices[pair] = {'price': price, 'change': change}
                socketio.emit('price_update', {'pair': pair, 'price': price, 'change': change})
            except Exception as e: logger.debug(f'Price tick: {e}')
        def on_error(ws, e): logger.warning(f'Price stream: {e}')
        def on_close(ws, *a): eventlet.sleep(5); run()
        def on_open(ws):  logger.info('Price stream connected')
        try:
            ws_lib.WebSocketApp(build_url(), on_message=on_message,
                                on_error=on_error, on_close=on_close,
                                on_open=on_open).run_forever(ping_interval=20)
        except Exception as e: logger.error(f'Price stream failed: {e}')
    _ws_thread = threading.Thread(target=run, daemon=True)
    _ws_thread.start()

# ── Scheduler ──────────────────────────────────────────────────────────────────
def push():
    try: socketio.emit('dashboard_update', get_dashboard_data())
    except Exception as e: logger.error(f'Push: {e}')

def bot_cycle():
    try: scan_and_trade(); refresh_pair_cache(); push()
    except Exception as e: logger.error(f'Bot cycle: {e}')

def news_cycle():
    try: fetch_and_analyze(); push()
    except Exception as e: logger.error(f'News cycle: {e}')

scheduler.add_job(bot_cycle,  'interval', minutes=5,  id='bot')
scheduler.add_job(news_cycle, 'interval', minutes=15, id='news')
scheduler.add_job(lambda: (refresh_pair_cache(), push()), 'interval', minutes=1, id='cache')

def scanner_cycle():
    try:
        from db.database import get_setting
        if get_setting('scanner_enabled') != 'true': return
        use_llm  = get_setting('use_llm_filter') == 'true'
        top_n    = int(get_setting('scanner_top_n') or 8)
        auto_upd = get_setting('scanner_auto_update') == 'true'
        result   = run_scanner(top_n=top_n, use_llm=use_llm)
        if result:
            apply_scanner_results(result, auto_update=auto_upd)
            push()
    except Exception as e: logger.error(f'Scanner cycle: {e}')

# Run scanner every N hours (default 6)
scheduler.add_job(scanner_cycle, 'interval', hours=6, id='scanner')

def brain_cycle():
    try:
        result = run_brain_cycle()
        if result:
            changed = apply_brain_recommendations(result)
            if changed:
                refresh_pair_cache()
                push()
    except Exception as e: logger.error(f'Brain cycle: {e}')

scheduler.add_job(brain_cycle, 'interval', minutes=30, id='brain')
# Ensure DB is initialized before scheduler starts
init_db(); init_auth()
scheduler.start()
start_cache_refresh()
eventlet.spawn_after(3, start_price_stream)

# ── Auth routes ────────────────────────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    if check_login(data.get('username',''), data.get('password','')):
        session['logged_in'] = True
        session['username']  = data['username']
        return jsonify({'ok': True, 'username': data['username']})
    return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/auth/status')
def auth_status():
    return jsonify({'logged_in': bool(session.get('logged_in')),
                    'username':  session.get('username','')})

@app.route('/api/auth/change_password', methods=['POST'])
@login_required
def do_change_password():
    data = request.json or {}
    change_password(session['username'], data.get('new_password',''))
    return jsonify({'ok': True})

# ── App routes ─────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def spa(path=None): return send_from_directory('/app/static', 'index.html')

@app.route('/api/status')
def status(): return jsonify({'ok':True})

@app.route('/api/dashboard')
@login_required
def dashboard():
    try: return jsonify(get_dashboard_data())
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/bot/start',  methods=['POST'])
@login_required
def start(): set_setting('bot_running','true');  push(); return jsonify({'ok':True})

@app.route('/api/bot/stop',   methods=['POST'])
@login_required
def stop():  set_setting('bot_running','false'); push(); return jsonify({'ok':True})

@app.route('/api/bot/mode',   methods=['POST'])
@login_required
def set_mode():
    m = request.json.get('mode','demo')
    if m not in ('demo','live'): return jsonify({'error':'Invalid'}), 400
    set_setting('trading_mode', m); push(); return jsonify({'ok':True,'mode':m})

# Defaults for every setting — returned when DB has None
_SETTING_DEFAULTS = {
    'max_positions':'5', 'stop_loss_pct':'1.5', 'take_profit_pct':'3.0',
    'position_size_usdt':'100', 'trading_mode':'demo',
    'active_pairs':'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT',
    'bot_running':'false', 'starting_balance':'1000',
    'trailing_stop_enabled':'true', 'trailing_stop_pct':'0.8',
    'partial_close_enabled':'true', 'partial_close_at_pct':'1.5',
    'partial_close_size_pct':'50', 'strategy_mode':'combined',
    'max_loss_streak':'3', 'cooldown_minutes':'60',
    'use_llm_filter':'false', 'mtf_enabled':'false',
    'scanner_enabled':'true', 'scanner_interval_hours':'6',
    'scanner_auto_update':'true', 'scanner_top_n':'8',
    'pinned_pairs':'BTC/USDT,ETH/USDT', 'last_scan_at':'',
}

def _gs(k):
    """Safe get_setting — never returns None or the string 'None'."""
    val = get_setting(k)
    if val is None or val == 'None' or val == '':
        return _SETTING_DEFAULTS.get(k, '')
    return val

@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    keys = ['max_positions','stop_loss_pct','take_profit_pct','position_size_usdt',
            'trading_mode','active_pairs','bot_running','starting_balance',
            'trailing_stop_enabled','trailing_stop_pct','partial_close_enabled',
            'partial_close_at_pct','partial_close_size_pct',
            'strategy_mode','max_loss_streak','cooldown_minutes',
            'use_llm_filter','mtf_enabled',
            'scanner_enabled','scanner_interval_hours','scanner_auto_update',
            'scanner_top_n','pinned_pairs','ai_brain_enabled']
    data = {k: _gs(k) for k in keys}
    data['binance_api_key']    = '***' if get_setting('binance_api_key')    else ''
    data['binance_api_secret'] = '***' if get_setting('binance_api_secret') else ''
    data['newsapi_key']        = '***' if get_setting('newsapi_key')        else ''
    data['anthropic_api_key']  = '***' if get_setting('anthropic_api_key')  else ''
    return jsonify(data)

@app.route('/api/settings', methods=['POST'])
@login_required
def upd_settings():
    data = request.json or {}
    for k in ['max_positions','stop_loss_pct','take_profit_pct','position_size_usdt',
              'active_pairs','starting_balance','trailing_stop_enabled','trailing_stop_pct',
              'partial_close_enabled','partial_close_at_pct','partial_close_size_pct',
              'strategy_mode','max_loss_streak','cooldown_minutes','use_llm_filter','mtf_enabled',
              'scanner_enabled','scanner_interval_hours','scanner_auto_update','scanner_top_n','pinned_pairs',
              'ai_brain_enabled']:
        if k in data: set_setting(k, str(data[k]))
    for k in ['binance_api_key','binance_api_secret','newsapi_key','anthropic_api_key']:
        if k in data and data[k] and data[k] != '***':
            set_setting(k, str(data[k]))
            logger.info(f'Saved {k}')
    return jsonify({'ok':True})

@app.route('/api/trades')
@login_required
def trades(): return jsonify(get_recent_trades(int(request.args.get('limit',50))))

@app.route('/api/trades/history')
@login_required
def trade_history():
    return jsonify(get_all_trades(
        page=int(request.args.get('page',1)),
        per_page=int(request.args.get('per_page',50)),
        pair=request.args.get('pair'),
        status=request.args.get('status'),
        strategy=request.args.get('strategy')))

@app.route('/api/news')
@login_required
def news(): return jsonify(get_news(20))

@app.route('/api/news/refresh', methods=['POST'])
@login_required
def ref_news(): fetch_and_analyze(); push(); return jsonify({'ok':True})

@app.route('/api/ohlcv')
@login_required
def ohlcv():
    from bot.exchange import fetch_ohlcv
    df = fetch_ohlcv(request.args.get('symbol','BTC/USDT'),
                     request.args.get('timeframe','1h'),
                     int(request.args.get('limit',100)))
    if df is None: return jsonify({'error':'Failed'}), 500
    df = df.reset_index(); df['timestamp'] = df['timestamp'].astype(str)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/bot/run_now', methods=['POST'])
@login_required
def run_now():
    try: scan_and_trade(); refresh_pair_cache(); push(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/ai/test')
@login_required
def test_ai():
    from db.database import get_setting
    import requests as req, json, re
    key = get_setting('anthropic_api_key') or ''
    if not key:
        return jsonify({'ok': False, 'error': 'No Anthropic API key saved'})
    try:
        r = req.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 50,
                  'messages': [{'role': 'user', 'content': 'Reply with just: OK'}]},
            timeout=10)
        data = r.json()
        if r.status_code == 200:
            text = data.get('content', [{}])[0].get('text', '')
            return jsonify({'ok': True, 'message': f'AI working — response: {text.strip()}'})
        else:
            return jsonify({'ok': False, 'error': data.get('error', {}).get('message', 'Unknown error')})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/prices')
def get_prices(): return jsonify(_prices)

@app.route('/api/trade/manual', methods=['POST'])
@login_required
def manual_trade():
    data = request.json or {}
    try:
        mode = get_setting('trading_mode') or 'demo'
        result = open_manual_trade(
            pair       = data['pair'],
            side       = data['side'],
            usdt_amount= float(data.get('usdt_amount', 100)),
            sl_pct     = float(data.get('sl_pct', 1.5)),
            tp_pct     = float(data.get('tp_pct', 3.0)),
            mode       = mode,
        )
        refresh_pair_cache(); push()
        return jsonify({'ok': True, 'trade': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/trade/close/<int:trade_id>', methods=['POST'])
@login_required
def force_close_trade(trade_id):
    try:
        result = close_manual_trade(trade_id)
        refresh_pair_cache(); push()
        return jsonify({'ok': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/scanner/run', methods=['POST'])
@login_required
def run_scan():
    try:
        from db.database import get_setting
        use_llm  = get_setting('use_llm_filter') == 'true'
        top_n    = int(get_setting('scanner_top_n') or 8)
        auto_upd = request.json.get('auto_update', get_setting('scanner_auto_update')=='true')
        result   = run_scanner(top_n=top_n, use_llm=use_llm)
        if result:
            final = apply_scanner_results(result, auto_update=auto_upd)
            refresh_pair_cache(); push()
            return jsonify({'ok': True, 'result': result, 'active_pairs': final})
        return jsonify({'error': 'Scanner returned no results'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/demo/reset', methods=['POST'])
@login_required
def reset_demo():
    """Clear all demo trades and reset demo balance to starting amount."""
    try:
        from db.database import get_conn, get_setting, set_setting
        from bot.engine import _demo
        conn = get_conn()
        # Delete all demo trades
        deleted = conn.execute("DELETE FROM trades WHERE mode='demo'").rowcount
        conn.commit(); conn.close()
        # Reset in-memory demo balance
        starting = float(get_setting('starting_balance') or 1000)
        _demo['balance'] = starting
        _demo['init']    = True
        push()
        logger.info(f'Demo reset: deleted {deleted} trades, balance reset to {starting}')
        return jsonify({'ok': True, 'deleted_trades': deleted, 'new_balance': starting})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/brain/log')
@login_required
def brain_log():
    from db.database import get_setting
    return jsonify({
        'log': get_brain_log(),
        'enabled': get_setting('ai_brain_enabled') == 'true',
        'last_run': get_setting('last_brain_run') or '',
    })

@app.route('/api/brain/run', methods=['POST'])
@login_required
def run_brain():
    try:
        result = run_brain_cycle()
        if result:
            changed = apply_brain_recommendations(result)
            if changed: refresh_pair_cache(); push()
            return jsonify({'ok': True, 'result': result, 'changed': changed})
        return jsonify({'ok': False, 'error': 'Brain returned no result (check Anthropic key)'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scanner/last')
@login_required
def last_scan():
    from db.database import get_setting
    import json
    raw = get_setting('last_scan_result') or ''
    try:
        return jsonify({'ok': True, 'result': json.loads(raw) if raw else None,
                        'last_scan_at': get_setting('last_scan_at')})
    except: return jsonify({'ok': True, 'result': None})

@app.route('/api/account')
@login_required
def account_status():
    try: return jsonify(get_full_account_status())
    except Exception as e: return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def on_connect():
    logger.info('Client connected')
    try: emit('dashboard_update', get_dashboard_data())
    except Exception as e: logger.error(f'Connect push: {e}')

if __name__ == '__main__':
    init_db(); init_auth()
    logger.info('Trading Bot starting on port 5000...')
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
