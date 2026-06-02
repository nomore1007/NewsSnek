import sqlite3
import hashlib
from pathlib import Path
from typing import List, Tuple, Optional

class DataManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self._connect() as conn:
            # Table for storing summarized articles
            conn.execute(
                "CREATE TABLE IF NOT EXISTS articles ("
                "url TEXT PRIMARY KEY, "
                "title TEXT, "
                "summary TEXT, "
                "group_name TEXT, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
            )
            # Table for content-based deduplication
            conn.execute(
                "CREATE TABLE IF NOT EXISTS dedup ("
                "fingerprint TEXT PRIMARY KEY, "
                "added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
            )
            conn.commit()

    def fingerprint_of(self, content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def is_duplicate(self, content: str) -> bool:
        fp = self.fingerprint_of(content)
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM dedup WHERE fingerprint = ?", (fp,))
            return cur.fetchone() is not None

    def mark_as_seen(self, content: str):
        fp = self.fingerprint_of(content)
        with self._connect() as conn:
            try:
                conn.execute("INSERT INTO dedup (fingerprint) VALUES (?)", (fp,))
                conn.commit()
            except sqlite3.IntegrityError:
                pass

    def has_article(self, url: str) -> bool:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
            return cur.fetchone() is not None

    def store_article(self, url: str, title: str, summary: str, group_name: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO articles (url, title, summary, group_name) VALUES (?, ?, ?, ?)",
                (url, title, summary, group_name)
            )
            conn.commit()

    def fetch_summaries_for_overview(self, max_items: int = 50) -> List[Tuple]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT url, title, summary, group_name FROM articles ORDER BY created_at DESC LIMIT ?",
                (max_items,)
            )
            return cur.fetchall()
