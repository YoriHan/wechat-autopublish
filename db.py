import sqlite3, hashlib
from pathlib import Path
from config import BASE_DIR

DB_PATH = str(BASE_DIR / "published.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url_hash TEXT PRIMARY KEY,
                url TEXT,
                title TEXT,
                published_at TEXT
            )
        """)

def is_duplicate(url: str) -> bool:
    h = hashlib.md5(url.encode()).hexdigest()
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT 1 FROM articles WHERE url_hash=?", (h,)
        ).fetchone() is not None

def mark_published(url: str, title: str):
    h = hashlib.md5(url.encode()).hexdigest()
    from datetime import datetime
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO articles VALUES (?,?,?,?)",
            (h, url, title, datetime.utcnow().isoformat())
        )
