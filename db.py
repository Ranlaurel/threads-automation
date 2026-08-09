"""SQLite: схема + тонкая обёртка. Никаких ORM — задача маленькая."""
import json
import sqlite3
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS hooks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    text         TEXT NOT NULL,
    category     TEXT,           -- категория формулы из библиотеки хуков
    used         INTEGER DEFAULT 0,
    created_at   INTEGER
);

CREATE TABLE IF NOT EXISTS threads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    hook_id      INTEGER,
    posts_json   TEXT NOT NULL,  -- json-список текстов постов (якорь + ответы)
    status       TEXT DEFAULT 'new',  -- new/posting/posted/failed
    created_at   INTEGER,
    posted_at    INTEGER,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS post_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id    INTEGER,
    posted_at    INTEGER
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def unused_hooks_count(conn) -> int:
    row = conn.execute("SELECT COUNT(*) c FROM hooks WHERE used=0").fetchone()
    return row["c"]


def insert_hooks(conn, items):
    """items: список (text, category)."""
    now = int(time.time())
    conn.executemany(
        "INSERT INTO hooks(text, category, used, created_at) VALUES(?,?,0,?)",
        [(text, category, now) for text, category in items],
    )


def pick_unused_hooks(conn, n):
    return conn.execute(
        "SELECT * FROM hooks WHERE used=0 ORDER BY created_at ASC LIMIT ?", (n,)
    ).fetchall()


def mark_hook_used(conn, hook_id):
    conn.execute("UPDATE hooks SET used=1 WHERE id=?", (hook_id,))


def threads_created_today(conn) -> int:
    day_start = int(time.time()) - (int(time.time()) % 86400)
    row = conn.execute(
        "SELECT COUNT(*) c FROM threads WHERE created_at >= ?", (day_start,)
    ).fetchone()
    return row["c"]


def save_thread(conn, hook_id, posts: list) -> int:
    cur = conn.execute(
        "INSERT INTO threads(hook_id, posts_json, status, created_at) VALUES(?,?,?,?)",
        (hook_id, json.dumps(posts, ensure_ascii=False), "new", int(time.time())),
    )
    return cur.lastrowid


def next_queued_thread(conn):
    return conn.execute(
        "SELECT * FROM threads WHERE status='new' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()


def set_thread_status(conn, thread_id, status, error=None):
    conn.execute(
        "UPDATE threads SET status=?, error=? WHERE id=?", (status, error, thread_id)
    )


def mark_thread_posted(conn, thread_id):
    now = int(time.time())
    conn.execute(
        "UPDATE threads SET status='posted', posted_at=? WHERE id=?", (now, thread_id)
    )
    conn.execute(
        "INSERT INTO post_log(thread_id, posted_at) VALUES(?,?)", (thread_id, now)
    )


def posted_today(conn) -> int:
    day_start = int(time.time()) - (int(time.time()) % 86400)
    row = conn.execute(
        "SELECT COUNT(*) c FROM post_log WHERE posted_at >= ?", (day_start,)
    ).fetchone()
    return row["c"]


if __name__ == "__main__":
    init_db()
    print(f"DB initialised at {config.DB_PATH}")
