# -*- coding: utf-8 -*-
"""이미 요약한 뉴스 URL 저장 (중복 방지)."""
import sqlite3
from pathlib import Path

_DATA_DIR = Path("/data") if Path("/data").exists() else Path(__file__).parent
DB_PATH = _DATA_DIR / "seen_news.sqlite"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_news (
                url TEXT PRIMARY KEY,
                title TEXT,
                publisher TEXT,
                summarized_at TEXT
            )
        """)
        conn.commit()


def is_seen(url: str) -> bool:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT 1 FROM seen_news WHERE url = ?", (url,))
        return cur.fetchone() is not None


def mark_seen(url: str, title: str = "", publisher: str = ""):
    import datetime
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO seen_news (url, title, publisher, summarized_at) VALUES (?, ?, ?, ?)",
            (url, title, publisher, datetime.datetime.utcnow().isoformat()),
        )
        conn.commit()
