import sqlite3, os, json
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', '/app/data/trading.db')

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

_push_fn = None
def set_push(fn): global _push_fn; _push_fn = fn

def init_activity_log():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, category TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'info',
        message TEXT NOT NULL, detail TEXT)''')
    conn.commit(); conn.close()

def log(category, message, detail=None, level='info'):
    try:
        conn = get_conn()
        conn.execute(
            'INSERT INTO activity_log (ts,category,level,message,detail) VALUES (?,?,?,?,?)',
            (datetime.utcnow().isoformat(), category, level,
             message, json.dumps(detail) if detail else None))
        conn.execute(
            'DELETE FROM activity_log WHERE id NOT IN '
            '(SELECT id FROM activity_log ORDER BY id DESC LIMIT 500)')
        entry = conn.execute(
            'SELECT * FROM activity_log ORDER BY id DESC LIMIT 1').fetchone()
        conn.commit()
        if _push_fn and entry:
            try: _push_fn('activity_update', dict(entry))
            except: pass
        conn.close()
    except: pass

def get_logs(limit=100, category=None, date_from=None, date_to=None):
    conn = get_conn()
    conditions = []; params = []
    if category and category != 'all':
        conditions.append('category=?'); params.append(category)
    if date_from:
        conditions.append("date(ts)>=?"); params.append(date_from)
    if date_to:
        conditions.append("date(ts)<=?"); params.append(date_to)
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    rows  = conn.execute(
        f'SELECT * FROM activity_log {where} ORDER BY id DESC LIMIT ?',
        params+[limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]
