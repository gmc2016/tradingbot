"""
Activity log — stores all bot decisions, AI calls, setting changes with timestamps.
Persisted in SQLite so nothing is lost on restart.
"""
import sqlite3, os, json
from datetime import datetime

DB_PATH = '/app/data/trading.db'

def get_conn():
    os.makedirs('/app/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_activity_log():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS activity_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        ts        TEXT NOT NULL,
        category  TEXT NOT NULL,
        level     TEXT NOT NULL DEFAULT 'info',
        message   TEXT NOT NULL,
        detail    TEXT
    )''')
    conn.commit(); conn.close()

# Will be set by app.py after socketio is created
_push_fn = None

def set_push(fn):
    global _push_fn
    _push_fn = fn

def log(category, message, detail=None, level='info'):
    """
    category: trade | signal | ai | brain | scanner | system | settings
    level:    info | success | warning | error
    """
    try:
        conn = get_conn()
        conn.execute(
            'INSERT INTO activity_log (ts, category, level, message, detail) VALUES (?,?,?,?,?)',
            (datetime.utcnow().isoformat(), category, level,
             message, json.dumps(detail) if detail else None)
        )
        # Keep last 500 entries
        conn.execute(
            'DELETE FROM activity_log WHERE id NOT IN '
            '(SELECT id FROM activity_log ORDER BY id DESC LIMIT 500)'
        )
        conn.commit()
        # Get the inserted row to push to frontend
        entry = conn.execute(
            'SELECT * FROM activity_log ORDER BY id DESC LIMIT 1'
        ).fetchone()
        conn.close()
        # Push to connected clients
        if _push_fn and entry:
            try: _push_fn('activity_update', dict(entry))
            except: pass
    except Exception as e:
        pass  # Never crash the bot due to logging

def get_logs(limit=100, category=None):
    conn = get_conn()
    if category and category != 'all':
        rows = conn.execute(
            'SELECT * FROM activity_log WHERE category=? ORDER BY id DESC LIMIT ?',
            (category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM activity_log ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
