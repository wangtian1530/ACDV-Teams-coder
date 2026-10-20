"""Lớp truy cập SQLite cho user + token."""
import json
import sqlite3
import logging
from datetime import datetime

from config import DB_PATH
from crypto import fernet

log = logging.getLogger("hrm-bot")


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            username TEXT NOT NULL,
            password_enc TEXT NOT NULL,
            tokens_json TEXT,
            notify_hour INTEGER DEFAULT 20,
            notify_min INTEGER DEFAULT 0,
            updated_at TEXT
        )""")


def db_get(tg_id: int):
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
    return dict(row) if row else None


def db_all():
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM users").fetchall()]


def db_upsert(tg_id, chat_id, username, password, tokens=None):
    enc = fernet.encrypt(password.encode()).decode()
    tj = json.dumps(tokens) if tokens else None
    with sqlite3.connect(DB_PATH) as c:
        if c.execute("SELECT 1 FROM users WHERE telegram_id=?", (tg_id,)).fetchone():
            c.execute("""UPDATE users SET chat_id=?, username=?, password_enc=?, tokens_json=?,
                         updated_at=? WHERE telegram_id=?""",
                      (chat_id, username, enc, tj, datetime.utcnow().isoformat(), tg_id))
        else:
            c.execute("""INSERT INTO users (telegram_id, chat_id, username, password_enc, tokens_json, updated_at)
                         VALUES (?,?,?,?,?,?)""",
                      (tg_id, chat_id, username, enc, tj, datetime.utcnow().isoformat()))
    log.info("[TG:%s] DB upsert user=%s chat=%s", tg_id, username, chat_id)


def db_save_tokens(tg_id, tokens):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE users SET tokens_json=?, updated_at=? WHERE telegram_id=?",
                  (json.dumps(tokens), datetime.utcnow().isoformat(), tg_id))


def db_set_time(tg_id, h, m):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE users SET notify_hour=?, notify_min=? WHERE telegram_id=?",
                  (h, m, tg_id))
    log.info("[TG:%s] DB set_time=%02d:%02d", tg_id, h, m)


def db_delete(tg_id):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM users WHERE telegram_id=?", (tg_id,))
    log.info("[TG:%s] DB delete user", tg_id)