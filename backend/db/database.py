import sqlite3, os
from datetime import datetime

DB_PATH = '/app/data/trading.db'

def get_conn():
    os.makedirs('/app/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mode TEXT, pair TEXT, side TEXT,
        entry_price REAL, exit_price REAL, quantity REAL,
        pnl REAL, status TEXT DEFAULT 'open',
        strategy_reason TEXT, stop_loss REAL, take_profit REAL,
        trailing_stop REAL,
        opened_at TEXT, closed_at TEXT, order_id TEXT)''')
    # Add trailing_stop column if upgrading from old schema
    try:
        c.execute('ALTER TABLE trades ADD COLUMN trailing_stop REAL')
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS news_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, source TEXT, url TEXT,
        sentiment TEXT, sentiment_score REAL,
        published_at TEXT, fetched_at TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    # Defaults — INSERT OR IGNORE so existing values are preserved
    for k, v in [
        ('max_positions','5'),
        ('stop_loss_pct','1.5'),
        ('take_profit_pct','3.0'),
        ('position_size_usdt','100'),
        ('trading_mode', os.environ.get('TRADING_MODE', 'demo')),
        ('active_pairs', 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,ADA/USDT,DOGE/USDT,AVAX/USDT'),
        ('bot_running', 'false'),
        ('starting_balance', '1000'),
        ('trailing_stop_enabled', 'true'),
        ('trailing_stop_pct', '0.8'),
        ('partial_close_enabled', 'true'),
        ('partial_close_at_pct', '1.5'),
        ('partial_close_size_pct', '50'),
    ]:
        c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (k, v))

    # API keys: seed from env vars ONLY if DB value is currently empty
    for env_var, db_key in [
        ('BINANCE_API_KEY',    'binance_api_key'),
        ('BINANCE_API_SECRET', 'binance_api_secret'),
        ('NEWSAPI_KEY',        'newsapi_key'),
    ]:
        env_val = os.environ.get(env_var, '')
        c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (db_key, env_val))
        # If DB has empty string but env has a value, update it
        row = c.execute('SELECT value FROM settings WHERE key=?', (db_key,)).fetchone()
        if row and not row['value'] and env_val:
            c.execute('UPDATE settings SET value=? WHERE key=?', (env_val, db_key))

    conn.commit(); conn.close()

def get_setting(k):
    conn = get_conn()
    r = conn.execute('SELECT value FROM settings WHERE key=?', (k,)).fetchone()
    conn.close()
    return r['value'] if r else None

def set_setting(k, v):
    conn = get_conn()
    conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (k, str(v)))
    conn.commit(); conn.close()

def insert_trade(mode, pair, side, entry_price, quantity, stop_loss, take_profit, reason, order_id=None):
    conn = get_conn(); c = conn.cursor()
    c.execute('''INSERT INTO trades
        (mode,pair,side,entry_price,quantity,stop_loss,take_profit,
         strategy_reason,opened_at,status,order_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (mode,pair,side,entry_price,quantity,stop_loss,take_profit,
         reason,datetime.utcnow().isoformat(),'open',order_id))
    tid = c.lastrowid; conn.commit(); conn.close(); return tid

def close_trade(tid, exit_price, pnl):
    conn = get_conn()
    conn.execute("UPDATE trades SET exit_price=?,pnl=?,status='closed',closed_at=? WHERE id=?",
                 (exit_price,pnl,datetime.utcnow().isoformat(),tid))
    conn.commit(); conn.close()

def partial_close_trade(tid, quantity_remaining, pnl_realized):
    """Reduce position size, book partial PnL."""
    conn = get_conn()
    conn.execute('UPDATE trades SET quantity=?, pnl=COALESCE(pnl,0)+? WHERE id=?',
                 (quantity_remaining, pnl_realized, tid))
    conn.commit(); conn.close()

def update_trailing_stop(tid, new_stop):
    conn = get_conn()
    conn.execute('UPDATE trades SET trailing_stop=?, stop_loss=? WHERE id=?',
                 (new_stop, new_stop, tid))
    conn.commit(); conn.close()

def get_open_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades WHERE status='open' ORDER BY opened_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_recent_trades(limit=50):
    conn = get_conn()
    rows = conn.execute('SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?', (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_all_trades(page=1, per_page=50, pair=None, status=None, strategy=None):
    conn = get_conn()
    conditions = []; params = []
    if pair:     conditions.append('pair=?');   params.append(pair)
    if status:   conditions.append('status=?'); params.append(status)
    if strategy: conditions.append('LOWER(strategy_reason) LIKE ?'); params.append(f'%{strategy}%')
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    total = conn.execute(f'SELECT COUNT(*) as c FROM trades {where}', params).fetchone()['c']
    offset = (page-1)*per_page
    rows = conn.execute(f'SELECT * FROM trades {where} ORDER BY opened_at DESC LIMIT ? OFFSET ?',
                        params+[per_page, offset]).fetchall()
    conn.close()
    return {'trades': [dict(r) for r in rows], 'total': total, 'page': page, 'per_page': per_page}

def get_stats():
    conn = get_conn()
    total    = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='closed'").fetchone()['c']
    wins     = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='closed' AND pnl>0").fetchone()['c']
    tp       = conn.execute("SELECT COALESCE(SUM(pnl),0) as s FROM trades WHERE status='closed'").fetchone()['s']
    tdp      = conn.execute("SELECT COALESCE(SUM(pnl),0) as s FROM trades WHERE status='closed' AND date(closed_at)=date('now')").fetchone()['s']
    tdt      = conn.execute("SELECT COUNT(*) as c FROM trades WHERE date(opened_at)=date('now')").fetchone()['c']
    best     = conn.execute("SELECT MAX(pnl) as m FROM trades WHERE status='closed'").fetchone()['m'] or 0
    worst    = conn.execute("SELECT MIN(pnl) as m FROM trades WHERE status='closed'").fetchone()['m'] or 0
    avg_pnl  = conn.execute("SELECT AVG(pnl) as m FROM trades WHERE status='closed'").fetchone()['m'] or 0
    conn.close()
    return {'total_trades':total,'wins':wins,'losses':total-wins,
            'win_rate':round((wins/total*100) if total>0 else 0,1),
            'total_pnl':round(tp,2),'today_pnl':round(tdp,2),'today_trades':tdt,
            'best_trade':round(best,2),'worst_trade':round(worst,2),'avg_pnl':round(avg_pnl,2)}

def insert_news(title, source, url, sentiment, score, published_at):
    conn = get_conn()
    conn.execute('INSERT INTO news_cache (title,source,url,sentiment,sentiment_score,published_at,fetched_at) VALUES (?,?,?,?,?,?,?)',
                 (title,source,url,sentiment,score,published_at,datetime.utcnow().isoformat()))
    conn.execute('DELETE FROM news_cache WHERE id NOT IN (SELECT id FROM news_cache ORDER BY fetched_at DESC LIMIT 100)')
    conn.commit(); conn.close()

def get_news(limit=20):
    conn = get_conn()
    rows = conn.execute('SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?', (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

# ── Auth ──────────────────────────────────────────────────────────────────────
import hashlib, secrets

def hash_password(pw):
    salt = secrets.token_hex(16)
    h    = hashlib.sha256((salt + pw).encode()).hexdigest()
    return f'{salt}:{h}'

def verify_password(pw, stored):
    try:
        salt, h = stored.split(':')
        return hashlib.sha256((salt + pw).encode()).hexdigest() == h
    except: return False

def init_auth():
    conn = get_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT)''')
    # Default admin/admin if no users exist
    count = c.execute('SELECT COUNT(*) as n FROM users').fetchone()['n']
    if count == 0:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?,?)',
                  ('admin', hash_password('admin')))
    conn.commit(); conn.close()

def check_login(username, password):
    conn = get_conn()
    row  = conn.execute('SELECT password_hash FROM users WHERE username=?', (username,)).fetchone()
    conn.close()
    if not row: return False
    return verify_password(password, row['password_hash'])

def change_password(username, new_password):
    conn = get_conn()
    conn.execute('UPDATE users SET password_hash=? WHERE username=?',
                 (hash_password(new_password), username))
    conn.commit(); conn.close()
