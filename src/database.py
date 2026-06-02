import sqlite3
import hashlib
from pathlib import Path

DB_PATH = Path("/home/nomore/newsnek/news_reader.db")

def _connect():
    return sqlite3.connect(str(DB_PATH))

def init_dedup_table():
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS dedup (id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        conn.commit()

def fingerprint_of(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def is_duplicate(content: str) -> bool:
    fp = fingerprint_of(content)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM dedup WHERE fingerprint = ?", (fp,))
        return cur.fetchone() is not None

def mark_as_seen(content: str):
    fp = fingerprint_of(content)
    with _connect() as conn:
        try:
            conn.execute("INSERT INTO dedup (fingerprint) VALUES (?)", (fp,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
