"""
News Snek - SQLite Database Layer
Stores processed articles and their summaries so the bot can avoid duplicates
and later generate an overall world‑state overview.
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)


class DataManager:
    """Manage persistence of article metadata and summaries.
    
    The schema is deliberately simple:
    
    * ``articles`` – one row per processed article.
        - ``url``   – unique identifier of the source article
        - ``title`` – article title (optional but useful for overview)
        - ``summary`` – the AI‑generated summary text
        - ``source`` – name of the source group/channel
        - ``fetched_at`` – ISO timestamp when the article was processed
    """

    def __init__(self, db_path: str = "news_reader.db"):
        self.db_path = db_path
        self._ensure_db()

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_db(self):
        """Create the SQLite file and tables if they don't exist yet."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT,
                    summary TEXT,
                    source TEXT,
                    fetched_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
            logger.info(f"✅ SQLite database initialized at {self.db_path}")
        finally:
            conn.close()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def store_article(self, url: str, title: str, summary: str, source: str) -> bool:
        """Insert a new article record.
        
        Returns ``True`` if the row was inserted, ``False`` if the URL already
        existed (duplicate) or an error occurred.
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO articles (url, title, summary, source, fetched_at) VALUES (?, ?, ?, ?, ?)",
                (url, title, summary, source, datetime.utcnow().isoformat())
            )
            conn.commit()
            if cur.rowcount == 0:
                logger.debug(f"⚠️ Duplicate article ignored: {url}")
                return False
            logger.debug(f"✅ Stored article: {url}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store article {url}: {e}")
            return False
        finally:
            conn.close()

    def has_article(self, url: str) -> bool:
        """Check whether the given URL has already been processed."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM articles WHERE url = ? LIMIT 1", (url,))
            return cur.fetchone() is not None
        finally:
            conn.close()

    def get_recent_summaries(self, limit: int = 50) -> List[Tuple[str, str, str]]:
        """Return a list of recent summaries.
        
        Each entry is ``(title, summary, source)`` ordered by ``fetched_at``
        descending (newest first). ``limit`` caps the number of rows returned.
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT title, summary, source FROM articles ORDER BY fetched_at DESC LIMIT ?",
                (limit,)
            )
            return cur.fetchall()
        finally:
            conn.close()

    def purge_older_than(self, days: int = 30) -> int:
        """Delete rows older than *days* and return the number of rows removed.
        This is useful for periodic cleanup so the DB does not grow without bound.
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            cutoff = datetime.utcnow().timestamp() - days * 86400
            # SQLite stores ISO strings, so we compare via datetime functions
            cur.execute(
                "DELETE FROM articles WHERE strftime('%s', fetched_at) < ?",
                (int(cutoff),)
            )
            removed = cur.rowcount
            conn.commit()
            logger.info(f"🧹 Purged {removed} article rows older than {days} days")
            return removed
        finally:
            conn.close()

    # ---------------------------------------------------------------------
    # Helper for Overview generation
    # ---------------------------------------------------------------------
    def fetch_summaries_for_overview(self, max_items: int = 50) -> List[Dict[str, str]]:
        """Return a list of dicts ``{"title": ..., "summary": ..., "source": ...}``
        that can be fed to a summarizer to produce a world‑state overview.
        """
        rows = self.get_recent_summaries(limit=max_items)
        return [{"title": r[0], "summary": r[1], "source": r[2]} for r in rows]
