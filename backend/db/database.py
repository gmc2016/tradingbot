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
        opened_at TEXT, closed_at TEXT, order_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS news_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, source TEXT, url TEXT,
        sentiment TEXT, sentiment_score REAL,
        published_at TEXT, fetched_at TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    for k, v in [
        ('max_positions','3'), ('stop_loss_pct','1.5'), ('take_profit_pct','3.0'),
        ('position_size_usdt','100'),
        ('trading_mode', os.environ.get('TRADING_MODE', 'demo')),
        ('active_pairs', 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT'),
        ('bot_running', 'false'), ('starting_balance', '1000'),
        ('binance_api_key', os.environ.get('BINANCE_API_KEY', '')),
        ('binance_api_secret', os.environ.get('BINANCE_API_SECRET', '')),
        ('newsapi_key', os.environ.get('NEWSAPI_KEY', '')),
    ]:
        c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (k, v))
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

def get_open_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades WHERE status='open' ORDER BY opened_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_recent_trades(limit=50):
    conn = get_conn()
    rows = conn.execute('SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?', (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='closed'").fetchone()['c']
    wins  = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='closed' AND pnl>0").fetchone()['c']
    tp    = conn.execute("SELECT COALESCE(SUM(pnl),0) as s FROM trades WHERE status='closed'").fetchone()['s']
    tdp   = conn.execute("SELECT COALESCE(SUM(pnl),0) as s FROM trades WHERE status='closed' AND date(closed_at)=date('now')").fetchone()['s']
    tdt   = conn.execute("SELECT COUNT(*) as c FROM trades WHERE date(opened_at)=date('now')").fetchone()['c']
    conn.close()
    return {'total_trades':total,'wins':wins,'losses':total-wins,
            'win_rate':round((wins/total*100) if total>0 else 0,1),
            'total_pnl':round(tp,2),'today_pnl':round(tdp,2),'today_trades':tdt}

def insert_news(title, source, url, sentiment, score, published_at):
    conn = get_conn()
    conn.execute('INSERT INTO news_cache (title,source,url,sentiment,sentiment_score,published_at,fetched_at) VALUES (?,?,?,?,?,?,?)',
                 (title,source,url,sentiment,score,published_at,datetime.utcnow().isoformat()))
    conn.execute('DELETE FROM news_cache WHERE id NOT IN (SELECT id FROM news_cache ORDER BY fetched_at DESC LIMIT 50)')
    conn.commit(); conn.close()

def get_news(limit=20):
    conn = get_conn()
    rows = conn.execute('SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?', (limit,)).fetchall()
    conn.close(); return [dict(r) for r in rows]
