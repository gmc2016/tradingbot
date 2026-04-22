import sqlite3, os, hashlib, secrets
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', '/app/data/trading.db')

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mode TEXT, pair TEXT, side TEXT,
        entry_price REAL, exit_price REAL, quantity REAL, pnl REAL,
        status TEXT DEFAULT 'open',
        strategy_reason TEXT, stop_loss REAL, take_profit REAL,
        opened_at TEXT, closed_at TEXT, order_id TEXT, trailing_stop REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS news_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, source TEXT, url TEXT,
        sentiment TEXT, sentiment_score REAL,
        published_at TEXT, fetched_at TEXT)''')

    # All defaults
    defaults = [
        ('max_positions','5'), ('stop_loss_pct','1.5'), ('take_profit_pct','3.0'),
        ('position_size_usdt','100'),
        ('trading_mode', os.environ.get('TRADING_MODE','demo')),
        ('active_pairs','BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,LINK/USDT,AVAX/USDT,DOT/USDT,AAVE/USDT,UNI/USDT,TON/USDT,ZEC/USDT'),
        ('bot_running','false'), ('starting_balance','1000'),
        ('trailing_stop_enabled','true'), ('trailing_stop_pct','0.8'),
        ('partial_close_enabled','true'), ('partial_close_at_pct','0.8'),
        ('partial_close_size_pct','50'), ('strategy_mode','combined'),
        ('max_loss_streak','3'), ('cooldown_minutes','60'),
        ('use_llm_filter','false'), ('mtf_enabled','false'),
        ('scanner_enabled','true'), ('scanner_interval_hours','6'),
        ('scanner_auto_update','true'), ('scanner_top_n','8'),
        ('pinned_pairs','BTC/USDT,ETH/USDT,SOL/USDT,AAVE/USDT'),
        ('last_scan_at',''), ('last_scan_result',''),
        ('ai_brain_enabled','false'), ('brain_log','[]'), ('last_brain_run',''),
        ('watchlist','BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,LINK/USDT'),
        ('trading_mode_scalp','false'),
        ('scalp_tp_pct','0.4'), ('scalp_sl_pct','0.25'),
        ('scalp_trail_pct','0.2'), ('scalp_pos_size','100'),
        ('scalp_pairs','BTC/USDT,ETH/USDT,SOL/USDT'),
        ('demo_fee_rate','0.1'),
    ]
    for k, v in defaults:
        c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (k, v))

    # Migration: add any missing keys to existing DBs
    migration = [
        ('use_llm_filter','false'), ('mtf_enabled','false'),
        ('scanner_enabled','true'), ('scanner_auto_update','true'),
        ('scanner_top_n','8'), ('scanner_interval_hours','6'),
        ('pinned_pairs','BTC/USDT,ETH/USDT,SOL/USDT,AAVE/USDT'),
        ('last_scan_at',''), ('last_scan_result',''),
        ('strategy_mode','combined'), ('max_loss_streak','3'),
        ('cooldown_minutes','60'), ('trailing_stop_enabled','true'),
        ('partial_close_enabled','true'), ('partial_close_at_pct','0.8'), ('max_positions','5'),
        ('ai_brain_enabled','false'), ('brain_log','[]'), ('last_brain_run',''),
        ('watchlist','BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,LINK/USDT'),
        ('trading_mode_scalp','false'),
        ('scalp_tp_pct','0.4'), ('scalp_sl_pct','0.25'),
        ('scalp_trail_pct','0.2'), ('scalp_pos_size','100'),
        ('scalp_pairs','BTC/USDT,ETH/USDT,SOL/USDT'),
        ('demo_fee_rate','0.1'),
        ('anthropic_api_key', os.environ.get('ANTHROPIC_API_KEY','')),
        ('binance_api_key',   os.environ.get('BINANCE_API_KEY','')),
        ('binance_api_secret',os.environ.get('BINANCE_API_SECRET','')),
        ('newsapi_key',       os.environ.get('NEWSAPI_KEY','')),
    ]
    # Update scalp pairs to include SOL
    try:
        cur_sp = c.execute("SELECT value FROM settings WHERE key='scalp_pairs'").fetchone()
        if cur_sp and cur_sp[0] == 'BTC/USDT,ETH/USDT':
            c.execute("UPDATE settings SET value='BTC/USDT,ETH/USDT,SOL/USDT' WHERE key='scalp_pairs'")
    except: pass

    # Remove ENJ from active pairs if present
    try:
        cur_pairs = c.execute("SELECT value FROM settings WHERE key='active_pairs'").fetchone()
        if cur_pairs and 'ENJ/USDT' in cur_pairs[0]:
            new_pairs = ','.join(p for p in cur_pairs[0].split(',') if 'ENJ' not in p)
            c.execute("UPDATE settings SET value=? WHERE key='active_pairs'", (new_pairs,))
    except: pass

    # Add scalp settings if missing
    scalp_defaults = [
        ('trading_mode_scalp','false'),('scalp_tp_pct','0.4'),
        ('scalp_sl_pct','0.25'),('scalp_trail_pct','0.2'),
        ('scalp_pos_size','100'),('scalp_pairs','BTC/USDT,ETH/USDT'),
        ('demo_fee_rate','0.1'),
    ]
    for k,v in scalp_defaults:
        c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(k,v))

    # Force update partial_close_at_pct if still at old default 1.5
    try:
        cur_pc = c.execute("SELECT value FROM settings WHERE key='partial_close_at_pct'").fetchone()
        if cur_pc and cur_pc[0] == '1.5':
            c.execute("UPDATE settings SET value='0.8' WHERE key='partial_close_at_pct'")
    except: pass

    # Force reset pairs if they contain known micro-cap junk from scanner
    try:
        current_pairs = c.execute("SELECT value FROM settings WHERE key='active_pairs'").fetchone()
        if current_pairs:
            pairs = current_pairs[0] or ''
            junk  = ['SPK','GUN','CFG','PROM','UTK','HIGH','SUPER','GIGGLE',
                     'AUDIO','ONT','ALICE','PORTAL','MOVR','ENJ','ORDI']
            if any(j+'/' in pairs for j in junk):
                c.execute("UPDATE settings SET value=? WHERE key='active_pairs'",
                    ('BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,LINK/USDT,AVAX/USDT,DOT/USDT,AAVE/USDT,UNI/USDT,TON/USDT,ZEC/USDT',))
                c.execute("UPDATE settings SET value=? WHERE key='pinned_pairs'",
                    ('BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT',))
    except: pass

    for k, v in migration:
        c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (k, v))

    conn.commit(); conn.close()

def get_setting(k):
    try:
        conn = get_conn()
        row  = conn.execute('SELECT value FROM settings WHERE key=?', (k,)).fetchone()
        conn.close()
        return row['value'] if row else None
    except: return None

def set_setting(k, v):
    conn = get_conn()
    conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (k, v))
    conn.commit(); conn.close()

def insert_trade(mode, pair, side, entry, qty, sl, tp, reason, order_id=None):
    conn = get_conn()
    c = conn.execute(
        '''INSERT INTO trades (mode,pair,side,entry_price,quantity,stop_loss,take_profit,
           strategy_reason,status,opened_at,order_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (mode, pair, side, entry, qty, sl, tp, reason, 'open',
         datetime.utcnow().isoformat(), order_id))
    tid = c.lastrowid
    conn.commit(); conn.close()
    return tid

def close_trade(tid, exit_price, pnl):
    conn = get_conn()
    conn.execute(
        'UPDATE trades SET status=?,exit_price=?,pnl=?,closed_at=? WHERE id=?',
        ('closed', exit_price, pnl, datetime.utcnow().isoformat(), tid))
    conn.commit(); conn.close()

def partial_close_trade(tid, new_qty, partial_pnl):
    conn = get_conn()
    conn.execute('UPDATE trades SET quantity=?,pnl=COALESCE(pnl,0)+? WHERE id=?',
                 (new_qty, partial_pnl, tid))
    conn.commit(); conn.close()

def update_trailing_stop(tid, new_sl):
    conn = get_conn()
    conn.execute('UPDATE trades SET stop_loss=?,trailing_stop=1 WHERE id=?', (new_sl, tid))
    conn.commit(); conn.close()

def update_trailing_tp(tid, new_tp):
    conn = get_conn()
    conn.execute('UPDATE trades SET take_profit=?,trailing_stop=1 WHERE id=?', (new_tp, tid))
    conn.commit(); conn.close()

def get_open_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades WHERE status='open'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_trades(limit=50):
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_trades(page=1, per_page=50, pair=None, status=None,
                   strategy=None, date_from=None, date_to=None):
    conn = get_conn()
    conditions = []; params = []
    if pair:      conditions.append('pair=?');                   params.append(pair)
    if status:    conditions.append('status=?');                 params.append(status)
    if strategy:  conditions.append('LOWER(strategy_reason) LIKE ?'); params.append(f'%{strategy}%')
    if date_from: conditions.append('date(opened_at)>=?');       params.append(date_from)
    if date_to:   conditions.append('date(opened_at)<=?');       params.append(date_to)
    where  = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    total  = conn.execute(f'SELECT COUNT(*) as c FROM trades {where}', params).fetchone()['c']
    offset = (page-1)*per_page
    rows   = conn.execute(
        f'SELECT * FROM trades {where} ORDER BY opened_at DESC LIMIT ? OFFSET ?',
        params+[per_page, offset]).fetchall()
    conn.close()
    return {'trades':[dict(r) for r in rows],'total':total,'page':page,'per_page':per_page}

def get_stats():
    conn = get_conn()
    r = conn.execute('''SELECT
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN pnl<0 THEN 1 ELSE 0 END) as losses,
        ROUND(SUM(CASE WHEN pnl>0 THEN pnl ELSE 0 END),2) as gross_profit,
        ROUND(SUM(CASE WHEN pnl<0 THEN pnl ELSE 0 END),2) as gross_loss,
        ROUND(SUM(COALESCE(pnl,0)),2) as total_pnl,
        ROUND(AVG(CASE WHEN pnl IS NOT NULL THEN pnl END),4) as avg_pnl
        FROM trades WHERE status="closed"''').fetchone()
    today = conn.execute('''SELECT
        COUNT(*) as trades_today,
        ROUND(SUM(COALESCE(pnl,0)),2) as pnl_today
        FROM trades WHERE status="closed" AND date(closed_at)=date("now")''').fetchone()
    conn.close()
    d = dict(r); d.update(dict(today))
    total = d.get('total_trades',0)
    wins  = d.get('wins',0) or 0
    d['win_rate'] = round(wins/total*100,1) if total>0 else 0
    return d

def get_news(limit=20):
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_news(title, source, url, sentiment, score, published_at):
    conn = get_conn()
    existing = conn.execute('SELECT id FROM news_cache WHERE title=?', (title,)).fetchone()
    if not existing:
        conn.execute(
            '''INSERT INTO news_cache (title,source,url,sentiment,sentiment_score,
               published_at,fetched_at) VALUES (?,?,?,?,?,?,?)''',
            (title, source, url, sentiment, score, published_at,
             datetime.utcnow().isoformat()))
        conn.execute(
            'DELETE FROM news_cache WHERE id NOT IN '
            '(SELECT id FROM news_cache ORDER BY fetched_at DESC LIMIT 200)')
    conn.commit(); conn.close()

# ── Auth ───────────────────────────────────────────────────────────────────────
def hash_password(pw):
    salt = secrets.token_hex(16)
    h    = hashlib.sha256((salt+pw).encode()).hexdigest()
    return f'{salt}:{h}'

def verify_password(pw, stored):
    try:
        salt, h = stored.split(':')
        return hashlib.sha256((salt+pw).encode()).hexdigest() == h
    except: return False

def init_auth():
    conn = get_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)''')
    if c.execute('SELECT COUNT(*) as n FROM users').fetchone()['n'] == 0:
        c.execute('INSERT INTO users (username,password_hash) VALUES (?,?)',
                  ('admin', hash_password('admin')))
    conn.commit(); conn.close()

def check_login(username, password):
    conn = get_conn()
    row  = conn.execute('SELECT password_hash FROM users WHERE username=?',
                        (username,)).fetchone()
    conn.close()
    return bool(row and verify_password(password, row['password_hash']))

def change_password(username, new_password):
    conn = get_conn()
    conn.execute('UPDATE users SET password_hash=? WHERE username=?',
                 (hash_password(new_password), username))
    conn.commit(); conn.close()
