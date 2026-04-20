import os, sys, logging, json, threading, secrets, eventlet
sys.path.insert(0,'/')
sys.path.insert(0,'/app')
eventlet.monkey_patch()

from flask import Flask, jsonify, request, send_from_directory, session, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
from functools import wraps
from datetime import datetime

# ── Init DB first ──────────────────────────────────────────────────────────────
from db.database import (init_db, init_auth, get_setting, set_setting,
                          get_recent_trades, get_news, get_all_trades,
                          get_stats, check_login, change_password)
from db.activitylog import init_activity_log, log as alog, set_push, get_logs
init_db(); init_auth(); init_activity_log()

from bot.engine import (scan_and_trade, get_dashboard_data, start_cache_refresh,
                         refresh_pair_cache, open_manual_trade, close_manual_trade)
from bot.scanner import run_scanner, apply_scanner_results
from bot.macro import fetch_all_macro, get_macro_risk_level
from bot.account import get_full_account_status
from ai.sentiment import fetch_and_analyze
from ai.brain import run_brain_cycle, apply_brain_recommendations, get_brain_log

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='/app/static', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', secrets.token_hex(16))
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = False
CORS(app, origins='*', supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
set_push(socketio.emit)

_DEFAULTS = {
    'max_positions':'5','stop_loss_pct':'1.5','take_profit_pct':'3.0',
    'position_size_usdt':'100','trading_mode':'demo',
    'active_pairs':'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,LINK/USDT,AVAX/USDT,DOT/USDT,XRP/USDT',
    'bot_running':'false','starting_balance':'1000',
    'trailing_stop_enabled':'true','trailing_stop_pct':'0.8',
    'partial_close_enabled':'true','partial_close_at_pct':'1.5',
    'partial_close_size_pct':'50','strategy_mode':'combined',
    'max_loss_streak':'3','cooldown_minutes':'60',
    'use_llm_filter':'false','mtf_enabled':'false',
    'scanner_enabled':'true','scanner_interval_hours':'6',
    'scanner_auto_update':'true','scanner_top_n':'8',
    'pinned_pairs':'BTC/USDT,ETH/USDT','last_scan_at':'',
    'ai_brain_enabled':'false','last_brain_run':'',
}
def _gs(k):
    val = get_setting(k)
    return val if (val is not None and val not in ('','None')) else _DEFAULTS.get(k,'')

def login_required(f):
    @wraps(f)
    def dec(*a,**kw):
        if not session.get('logged_in'):
            return jsonify({'error':'Unauthorized','login_required':True}),401
        return f(*a,**kw)
    return dec

# ── Price stream + Kline stream ───────────────────────────────────────────────
_prices       = {}
_ws_thread    = None
_kline_subs   = {}   # symbol -> timeframe currently subscribed
_kline_thread = None

def start_price_stream():
    global _ws_thread
    if _ws_thread and _ws_thread.is_alive(): return
    def run():
        import websocket as ws_lib
        def url():
            raw=get_setting('active_pairs') or 'BTC/USDT,ETH/USDT'
            streams='/'.join([p.strip().replace('/','').lower()+'@miniTicker'
                              for p in raw.split(',')])
            return f'wss://stream.binance.com:9443/stream?streams={streams}'
        def on_msg(ws,msg):
            try:
                t=json.loads(msg).get('data',{})
                sym=t.get('s',''); price=float(t.get('c',0))
                if not sym: return
                pair=sym[:-4]+'/USDT' if sym.endswith('USDT') else sym
                open_p=float(t.get('o',price))
                chg=round(((price-open_p)/open_p*100) if open_p else 0,2)
                _prices[pair]={'price':price,'change':chg}
                socketio.emit('price_update',{'pair':pair,'price':price,'change':chg})
            except: pass
        def on_close(ws,*a): eventlet.sleep(5); run()
        try:
            ws_lib.WebSocketApp(url(),on_message=on_msg,
                on_error=lambda ws,e:None,on_close=on_close,
                on_open=lambda ws:logger.info('Price stream connected')).run_forever(ping_interval=20)
        except Exception as e: logger.error(f'WS: {e}')
    _ws_thread=threading.Thread(target=run,daemon=True); _ws_thread.start()

# Kline stream — single active stream, switches when symbol/tf changes
_kline_state = {'symbol': None, 'tf': None, 'ws': None, 'running': False}
_kline_lock  = threading.Lock()

def subscribe_kline(symbol, timeframe='1h'):
    """
    Single kline stream manager. Only one stream active at a time.
    If same symbol+tf already running, do nothing.
    """
    with _kline_lock:
        # Already subscribed to this exact stream — skip
        if (_kline_state['symbol'] == symbol and
                _kline_state['tf'] == timeframe and
                _kline_state['running']):
            return

        # Close existing stream cleanly
        if _kline_state['ws']:
            try:
                _kline_state['ws'].close()
            except: pass
            _kline_state['ws'] = None

        _kline_state['symbol']  = symbol
        _kline_state['tf']      = timeframe
        _kline_state['running'] = True

    import websocket as ws_lib
    stream = symbol.replace('/','').lower()
    url    = f'wss://stream.binance.com:9443/ws/{stream}@kline_{timeframe}'

    def on_msg(ws, msg):
        try:
            k = json.loads(msg).get('k', {})
            if not k: return
            # Only emit if still the active stream
            if _kline_state['symbol'] != symbol or _kline_state['tf'] != timeframe:
                return
            socketio.emit('kline_update', {
                'pair': symbol, 'tf': timeframe,
                'candle': {
                    'time':   int(k['t']) // 1000,
                    'open':   float(k['o']), 'high':  float(k['h']),
                    'low':    float(k['l']), 'close': float(k['c']),
                    'volume': float(k['v']), 'closed':bool(k['x']),
                }
            })
        except: pass

    def on_close(ws, *a):
        # Only reconnect if still the active subscription
        if _kline_state['symbol'] == symbol and _kline_state['tf'] == timeframe:
            _kline_state['running'] = False
            eventlet.sleep(5)
            if _kline_state['symbol'] == symbol and _kline_state['tf'] == timeframe:
                subscribe_kline(symbol, timeframe)

    def on_error(ws, e):
        logger.debug(f'Kline WS error {symbol}: {e}')

    def run():
        try:
            ws = ws_lib.WebSocketApp(url, on_message=on_msg,
                                     on_error=on_error, on_close=on_close)
            with _kline_lock:
                _kline_state['ws'] = ws
            ws.run_forever(ping_interval=30)
        except Exception as e:
            logger.debug(f'Kline WS {symbol}: {e}')
            _kline_state['running'] = False

    # Use eventlet.spawn so the green thread works with monkey-patched eventlet
    eventlet.spawn(run)
    logger.info(f'Kline stream: {symbol} {timeframe}')

# ── Scheduler ─────────────────────────────────────────────────────────────────
def push():
    try: socketio.emit('dashboard_update',get_dashboard_data())
    except Exception as e: logger.error(f'Push: {e}')

def bot_cycle():
    try: scan_and_trade(); refresh_pair_cache(); push()
    except Exception as e: logger.error(f'Bot: {e}')

def news_cycle():
    try:
        fetch_and_analyze()
        fetch_all_macro()  # Refresh macro cache alongside news
        push()
    except Exception as e: logger.error(f'News: {e}')

def cache_cycle():
    try:
        refresh_pair_cache()
        push()
    except Exception as e: logger.error(f'Cache: {e}')

def macro_cycle():
    """Refresh macro data every 15 min and log notable changes."""
    try:
        from ai.macro import get_macro_data
        from db.activitylog import log as alog
        data  = get_macro_data(force_refresh=True)
        sigs  = data.get('signals', {})
        bias  = sigs.get('overall_bias', 'neutral')
        fg    = data.get('FEAR_GREED', {})
        sp    = data.get('SP500', {})
        detail = {
            'bias': bias,
            'fear_greed': fg.get('value'),
            'sp500_change': sp.get('change'),
            'position_mult': sigs.get('position_mult', 1.0),
            'suppress_buy': sigs.get('suppress_buy', False),
        }
        level = 'warning' if sigs.get('suppress_buy') or sigs.get('risk_level') == 'high' else 'info'
        reasons = sigs.get('reasons', [])
        msg = f'Macro update: {bias.upper()} | F&G:{fg.get("value","?")} SP500:{sp.get("change",0):+.1f}%'
        if reasons: msg += f' — {reasons[0]}'
        alog('system', msg, level=level, detail=detail)
    except Exception as e: logger.debug(f'Macro cycle: {e}')

def scanner_cycle():
    try:
        if _gs('scanner_enabled')!='true': return
        result=run_scanner(top_n=int(_gs('scanner_top_n') or 8),
                           use_llm=_gs('use_llm_filter')=='true')
        if result:
            apply_scanner_results(result,auto_update=_gs('scanner_auto_update')=='true')
            push()
    except Exception as e: logger.error(f'Scanner: {e}')

def brain_cycle():
    try:
        if _gs('ai_brain_enabled')!='true': return
        if _gs('bot_running')!='true': return   # Don't run brain when bot is stopped
        if _gs('ai_brain_paused')=='true': return
        result=run_brain_cycle()
        if result:
            changed=apply_brain_recommendations(result)
            if changed: refresh_pair_cache(); push()
    except Exception as e: logger.error(f'Brain: {e}')

scheduler = BackgroundScheduler()
scheduler.add_job(bot_cycle,    'interval',minutes=5,  id='bot',    max_instances=1,misfire_grace_time=60)
scheduler.add_job(news_cycle,   'interval',minutes=15, id='news',   max_instances=1,misfire_grace_time=120)
scheduler.add_job(cache_cycle,  'interval',minutes=1,  id='cache',  max_instances=1,misfire_grace_time=30)
scheduler.add_job(macro_cycle,  'interval',minutes=15, id='macro',  max_instances=1,misfire_grace_time=60)
scheduler.add_job(scanner_cycle,'interval',hours=6,    id='scanner',max_instances=1,misfire_grace_time=300)
scheduler.add_job(brain_cycle,  'interval',minutes=30, id='brain',  max_instances=1,misfire_grace_time=120)
scheduler.start()
start_cache_refresh()
eventlet.spawn_after(3, start_price_stream)
alog('system','Trading Bot started')
logger.info('Trading Bot ready')

# ── Auth ───────────────────────────────────────────────────────────────────────
@app.route('/api/auth/login',methods=['POST'])
def login():
    d=request.json or {}
    if check_login(d.get('username',''),d.get('password','')):
        session['logged_in']=True; session['username']=d['username']
        return jsonify({'ok':True,'username':d['username']})
    return jsonify({'error':'Invalid credentials'}),401

@app.route('/api/auth/logout',methods=['POST'])
def logout(): session.clear(); return jsonify({'ok':True})

@app.route('/api/auth/status')
def auth_status():
    return jsonify({'logged_in':bool(session.get('logged_in')),'username':session.get('username','')})

@app.route('/api/auth/change_password',methods=['POST'])
@login_required
def do_change_password():
    change_password(session['username'],request.json.get('new_password',''))
    return jsonify({'ok':True})

# ── SPA ────────────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def spa(path=None): return send_from_directory('/app/static','index.html')

@app.route('/api/status')
def status(): return jsonify({'ok':True})

# ── Dashboard & Bot ────────────────────────────────────────────────────────────
@app.route('/api/dashboard')
@login_required
def dashboard():
    try: return jsonify(get_dashboard_data())
    except Exception as e: return jsonify({'error':str(e)}),500

@app.route('/api/bot/start',methods=['POST'])
@login_required
def start():
    set_setting('bot_running','true')
    set_setting('ai_brain_paused','false')
    push()
    return jsonify({'ok':True})

@app.route('/api/bot/stop',methods=['POST'])
@login_required
def stop():
    set_setting('bot_running','false')
    # Pause AI brain when bot is stopped
    set_setting('ai_brain_paused','true')
    push()
    alog('system','Bot stopped — AI brain paused, sentiment cache still active')
    return jsonify({'ok':True})


@app.route('/api/bot/mode',methods=['POST'])
@login_required
def set_mode():
    m=request.json.get('mode','demo')
    if m not in ('demo','live'): return jsonify({'error':'Invalid'}),400
    set_setting('trading_mode',m); push(); return jsonify({'ok':True,'mode':m})

@app.route('/api/bot/run_now',methods=['POST'])
@login_required
def run_now():
    try: scan_and_trade(); refresh_pair_cache(); push(); return jsonify({'ok':True})
    except Exception as e: return jsonify({'error':str(e)}),500

# ── Settings ───────────────────────────────────────────────────────────────────
@app.route('/api/settings',methods=['GET'])
@login_required
def get_settings():
    keys=['max_positions','stop_loss_pct','take_profit_pct','position_size_usdt',
          'trading_mode','active_pairs','bot_running','starting_balance',
          'trailing_stop_enabled','trailing_stop_pct','partial_close_enabled',
          'partial_close_at_pct','partial_close_size_pct',
          'strategy_mode','max_loss_streak','cooldown_minutes',
          'use_llm_filter','mtf_enabled',
          'scanner_enabled','scanner_interval_hours','scanner_auto_update',
          'scanner_top_n','pinned_pairs','ai_brain_enabled']
    data={k:_gs(k) for k in keys}
    data['watchlist'] = get_setting('watchlist') or 'BTC/USDT,ETH/USDT'
    data['binance_api_key']   ='***' if get_setting('binance_api_key')    else ''
    data['binance_api_secret']='***' if get_setting('binance_api_secret') else ''
    data['newsapi_key']       ='***' if get_setting('newsapi_key')        else ''
    data['anthropic_api_key'] ='***' if get_setting('anthropic_api_key')  else ''
    return jsonify(data)

@app.route('/api/settings',methods=['POST'])
@login_required
def upd_settings():
    data=request.json or {}
    safe=['max_positions','stop_loss_pct','take_profit_pct','position_size_usdt',
          'active_pairs','starting_balance','trailing_stop_enabled','trailing_stop_pct',
          'partial_close_enabled','partial_close_at_pct','partial_close_size_pct',
          'strategy_mode','max_loss_streak','cooldown_minutes','use_llm_filter',
          'mtf_enabled','scanner_enabled','scanner_interval_hours','scanner_auto_update',
          'scanner_top_n','pinned_pairs','ai_brain_enabled']
    changed=[]
    for k in safe:
        if k in data:
            old=get_setting(k); new=str(data[k])
            if old!=new: set_setting(k,new); changed.append(f'{k}:{old}→{new}')
    for k in ['binance_api_key','binance_api_secret','newsapi_key','anthropic_api_key']:
        if k in data and data[k] and data[k]!='***':
            set_setting(k,str(data[k])); changed.append(f'{k}:updated')
    if changed:
        alog('settings',f'Settings changed: {", ".join(changed[:6])}{"..." if len(changed)>6 else ""}',
             detail={'changes':changed})
    return jsonify({'ok':True})

# ── Trades ─────────────────────────────────────────────────────────────────────
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
        strategy=request.args.get('strategy'),
        date_from=request.args.get('date_from'),
        date_to=request.args.get('date_to')))

@app.route('/api/trade/manual',methods=['POST'])
@login_required
def manual_trade():
    d=request.json or {}
    try:
        result=open_manual_trade(pair=d['pair'],side=d['side'],
            usdt_amount=float(d.get('usdt_amount',100)),
            sl_pct=float(d.get('sl_pct',1.5)),tp_pct=float(d.get('tp_pct',3.0)),
            mode=_gs('trading_mode'))
        refresh_pair_cache(); push()
        return jsonify({'ok':True,'trade':result})
    except Exception as e: return jsonify({'error':str(e)}),400

@app.route('/api/trade/close/<int:trade_id>',methods=['POST'])
@login_required
def force_close(trade_id):
    try:
        result=close_manual_trade(trade_id); refresh_pair_cache(); push()
        return jsonify({'ok':True,'result':result})
    except Exception as e: return jsonify({'error':str(e)}),400

# ── News ───────────────────────────────────────────────────────────────────────
@app.route('/api/news')
@login_required
def news(): return jsonify(get_news(20))

@app.route('/api/news/refresh',methods=['POST'])
@login_required
def ref_news(): fetch_and_analyze(); push(); return jsonify({'ok':True})

@app.route('/api/macro')
@login_required
def macro_data():
    try:
        macro = fetch_all_macro()
        risk  = get_macro_risk_level(macro)
        return jsonify({'macro': macro, 'risk': risk})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist', methods=['GET'])
@login_required
def get_watchlist_route():
    from bot.watchlist import get_watchlist
    from bot.engine import _cache
    try:
        # Use cached watchlist data — refreshed every minute in background
        wl_data  = _cache.get('watchlist', [])
        wl_pairs = get_watchlist()
        # If cache empty (first load), return minimal data quickly
        if not wl_data:
            wl_data = [{'symbol':p,'price':0,'change':0,'signal':'HOLD',
                        'confidence':0,'reason':'Loading...','sentiment':50,
                        'indicators':{},'in_active_pairs':False,'auto_promote':False}
                       for p in wl_pairs]
        return jsonify({'pairs': wl_data, 'watchlist': wl_pairs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist', methods=['POST'])
@login_required
def set_watchlist_route():
    from bot.watchlist import set_watchlist
    data  = request.json or {}
    pairs = data.get('pairs', [])
    if isinstance(pairs, str):
        pairs = [p.strip() for p in pairs.split(',') if p.strip()]
    set_watchlist(pairs)
    from db.activitylog import log as alog
    alog('settings', f'Watchlist updated: {", ".join(pairs[:5])}{"..." if len(pairs)>5 else ""}')
    return jsonify({'ok': True, 'pairs': pairs})

@app.route('/api/kline/subscribe', methods=['POST'])
@login_required
def kline_subscribe():
    data = request.json or {}
    symbol    = data.get('symbol','BTC/USDT')
    timeframe = data.get('timeframe','1h')
    subscribe_kline(symbol, timeframe)
    return jsonify({'ok': True, 'symbol': symbol, 'timeframe': timeframe})

@app.route('/api/ohlcv')
@login_required
def ohlcv():
    from bot.exchange import fetch_ohlcv
    df=fetch_ohlcv(request.args.get('symbol','BTC/USDT'),
                   request.args.get('timeframe','1h'),
                   int(request.args.get('limit',100)))
    if df is None: return jsonify({'error':'Failed'}),500
    df=df.reset_index(); df['timestamp']=df['timestamp'].astype(str)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/prices')
def get_prices(): return jsonify(_prices)

# ── Scanner ────────────────────────────────────────────────────────────────────
@app.route('/api/scanner/run',methods=['POST'])
@login_required
def run_scan():
    try:
        d=request.json or {}
        auto_upd=d.get('auto_update',_gs('scanner_auto_update')=='true')
        result=run_scanner(top_n=int(_gs('scanner_top_n') or 8),
                           use_llm=_gs('use_llm_filter')=='true')
        if result:
            final=apply_scanner_results(result,auto_update=auto_upd)
            refresh_pair_cache(); push()
            return jsonify({'ok':True,'result':result,'active_pairs':final})
        return jsonify({'error':'Scanner returned no results'}),500
    except Exception as e:
        logger.error(f'Scanner: {e}'); return jsonify({'error':str(e)}),500

@app.route('/api/scanner/last')
@login_required
def last_scan():
    raw=get_setting('last_scan_result') or ''
    try: return jsonify({'ok':True,'result':json.loads(raw) if raw else None,
                         'last_scan_at':get_setting('last_scan_at')})
    except: return jsonify({'ok':True,'result':None})

# ── AI Brain ───────────────────────────────────────────────────────────────────
@app.route('/api/brain/log')
@login_required
def brain_log():
    return jsonify({'log':get_brain_log(),'enabled':_gs('ai_brain_enabled')=='true',
                    'last_run':get_setting('last_brain_run') or ''})

@app.route('/api/brain/run',methods=['POST'])
@login_required
def run_brain():
    try:
        result=run_brain_cycle()
        if result:
            changed=apply_brain_recommendations(result)
            if changed: refresh_pair_cache(); push()
            return jsonify({'ok':True,'result':result,'changed':changed})
        return jsonify({'ok':False,'error':'Brain returned no result — check Anthropic API key'})
    except Exception as e:
        logger.error(f'Brain: {e}'); return jsonify({'error':str(e)}),500

# ── Account ────────────────────────────────────────────────────────────────────
@app.route('/api/account')
@login_required
def account():
    try: return jsonify(get_full_account_status())
    except Exception as e: return jsonify({'error':str(e)}),500

@app.route('/api/ai/test')
@login_required
def test_ai():
    key=get_setting('anthropic_api_key') or ''
    if not key: return jsonify({'ok':False,'error':'No Anthropic API key saved'})
    try:
        import requests as req
        r=req.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key':key,'anthropic-version':'2023-06-01',
                     'content-type':'application/json'},
            json={'model':'claude-haiku-4-5-20251001','max_tokens':30,
                  'messages':[{'role':'user','content':'Reply OK only'}]},timeout=10)
        if r.status_code==200:
            text=r.json().get('content',[{}])[0].get('text','')
            return jsonify({'ok':True,'message':f'Connected — {text.strip()}'})
        return jsonify({'ok':False,'error':f'HTTP {r.status_code}'})
    except Exception as e: return jsonify({'ok':False,'error':str(e)})

# ── Activity log ───────────────────────────────────────────────────────────────
@app.route('/api/activity')
@login_required
def activity():
    return jsonify(get_logs(
        limit=int(request.args.get('limit',100)),
        category=request.args.get('category','all'),
        date_from=request.args.get('date_from'),
        date_to=request.args.get('date_to')))

# ── Demo reset ─────────────────────────────────────────────────────────────────
@app.route('/api/demo/reset',methods=['POST'])
@login_required
def reset_demo():
    try:
        from db.database import get_conn
        from bot.engine import _demo
        conn=get_conn()
        deleted=conn.execute("DELETE FROM trades WHERE mode='demo'").rowcount
        conn.commit(); conn.close()
        starting=float(_gs('starting_balance') or 1000)
        _demo['balance']=starting; _demo['init']=True
        alog('system',f'Demo reset: {deleted} trades deleted, balance reset to ${starting}')
        push()
        return jsonify({'ok':True,'deleted_trades':deleted,'new_balance':starting})
    except Exception as e: return jsonify({'error':str(e)}),500

# ── Export (with date range) ───────────────────────────────────────────────────
@app.route('/api/export/trades')
@login_required
def export_trades():
    import csv, io
    from db.database import get_conn
    date_from=request.args.get('date_from','')
    date_to  =request.args.get('date_to','')
    conditions=[]; params=[]
    if date_from: conditions.append("date(opened_at)>=?"); params.append(date_from)
    if date_to:   conditions.append("date(opened_at)<=?"); params.append(date_to)
    where=('WHERE '+' AND '.join(conditions)) if conditions else ''
    conn=get_conn()
    rows=conn.execute(f'SELECT * FROM trades {where} ORDER BY opened_at DESC',params).fetchall()
    conn.close()
    out=io.StringIO()
    w=csv.writer(out)
    w.writerow(['ID','Mode','Pair','Side','Entry','Exit','Qty','PnL','Status',
                'Strategy','SL','TP','Opened','Closed'])
    for r in rows:
        w.writerow([r['id'],r['mode'],r['pair'],r['side'],r['entry_price'],
                    r['exit_price'] or '',r['quantity'],round(r['pnl'] or 0,4),
                    r['status'],r['strategy_reason'] or '',r['stop_loss'],
                    r['take_profit'],r['opened_at'],r['closed_at'] or ''])
    fname=f"trades_{date_from or 'all'}{'_to_'+date_to if date_to else ''}.csv"
    return Response(out.getvalue(),mimetype='text/csv',
                    headers={'Content-Disposition':f'attachment; filename={fname}'})

@app.route('/api/export/activity')
@login_required
def export_activity():
    import csv, io
    date_from=request.args.get('date_from','')
    date_to  =request.args.get('date_to','')
    logs=get_logs(limit=2000,category=request.args.get('category','all'),
                  date_from=date_from or None, date_to=date_to or None)
    out=io.StringIO()
    w=csv.writer(out)
    w.writerow(['ID','Timestamp','Category','Level','Message','Detail'])
    for entry in reversed(logs):
        detail=''
        try:
            if entry.get('detail'):
                d=json.loads(entry['detail'])
                detail=' | '.join(f'{k}={v}' for k,v in d.items())
        except: pass
        w.writerow([entry.get('id',''),entry.get('ts',''),entry.get('category',''),
                    entry.get('level',''),entry.get('message',''),detail])
    fname=f"activity_{date_from or 'all'}.csv"
    return Response(out.getvalue(),mimetype='text/csv',
                    headers={'Content-Disposition':f'attachment; filename={fname}'})

@app.route('/api/export/summary')
@login_required
def export_summary():
    try:
        from db.database import get_conn
        date_from=request.args.get('date_from','')
        date_to  =request.args.get('date_to','')
        cond=[]; params=[]
        if date_from: cond.append("date(opened_at)>=?"); params.append(date_from)
        if date_to:   cond.append("date(opened_at)<=?"); params.append(date_to)
        where=('WHERE '+' AND '.join(cond)) if cond else ''
        conn=get_conn()
        trades=[dict(r) for r in conn.execute(
            f"SELECT * FROM trades WHERE status='closed' {('AND '+' AND '.join(cond)) if cond else ''} ORDER BY opened_at",
            params).fetchall()]
        open_trades=[dict(r) for r in conn.execute("SELECT * FROM trades WHERE status='open'").fetchall()]
        pair_stats=[dict(r) for r in conn.execute(f'''
            SELECT pair,COUNT(*) as total,
            SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl<0 THEN 1 ELSE 0 END) as losses,
            ROUND(AVG(pnl),4) as avg_pnl,ROUND(SUM(pnl),4) as total_pnl,
            ROUND(MAX(pnl),4) as best_trade,ROUND(MIN(pnl),4) as worst_trade
            FROM trades WHERE status='closed' {('AND '+' AND '.join(cond)) if cond else ''}
            GROUP BY pair ORDER BY total_pnl DESC''',params).fetchall()]
        strategy_stats=[dict(r) for r in conn.execute(f'''
            SELECT CASE
                WHEN strategy_reason LIKE '%Donchian%' THEN 'Donchian'
                WHEN strategy_reason LIKE '%MTF%' THEN 'MTF'
                WHEN strategy_reason LIKE '%EMA%cross%' THEN 'EMA Cross'
                WHEN strategy_reason LIKE '%Manual%' THEN 'Manual'
                ELSE 'RSI/MACD/BB' END as strategy,
            COUNT(*) as total,SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
            ROUND(SUM(pnl),4) as total_pnl,ROUND(AVG(pnl),4) as avg_pnl
            FROM trades WHERE status='closed' {('AND '+' AND '.join(cond)) if cond else ''}
            GROUP BY strategy ORDER BY total_pnl DESC''',params).fetchall()]
        daily=[dict(r) for r in conn.execute(f'''
            SELECT date(closed_at) as date,COUNT(*) as trades,
            SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,ROUND(SUM(pnl),4) as pnl
            FROM trades WHERE status='closed' {('AND '+' AND '.join(cond)) if cond else ''}
            GROUP BY date(closed_at) ORDER BY date''',params).fetchall()]
        conn.close()
        settings={k:get_setting(k) for k in
                  ['strategy_mode','stop_loss_pct','take_profit_pct','position_size_usdt',
                   'max_positions','trailing_stop_enabled','partial_close_enabled',
                   'use_llm_filter','mtf_enabled','ai_brain_enabled','trading_mode']}
        summary={
            'exported_at':datetime.utcnow().isoformat(),
            'period':{'from':date_from or 'all','to':date_to or 'all'},
            'overall_stats':get_stats(),
            'settings':settings,
            'pair_stats':pair_stats,
            'strategy_stats':strategy_stats,
            'daily_pnl':daily,
            'open_trades':open_trades,
            'closed_trades':trades,
            'brain_log':get_brain_log()[:10],
        }
        fname=f"summary_{date_from or 'all'}.json"
        return Response(json.dumps(summary,indent=2,default=str),
                        mimetype='application/json',
                        headers={'Content-Disposition':f'attachment; filename={fname}'})
    except Exception as e:
        logger.error(f'Export summary: {e}'); return jsonify({'error':str(e)}),500

# ── WebSocket ──────────────────────────────────────────────────────────────────
@socketio.on('connect')
def on_connect():
    logger.info('Client connected')
    try: emit('dashboard_update',get_dashboard_data())
    except Exception as e: logger.error(f'Connect: {e}')

if __name__=='__main__':
    logger.info('Starting on port 5000...')
    socketio.run(app,host='0.0.0.0',port=5000,debug=False)
