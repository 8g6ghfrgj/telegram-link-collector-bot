# sessions_db.py
import sqlite3
from datetime import datetime

DB_NAME = "sessions.db"


class SessionsDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create()

    def _create(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            session_name TEXT UNIQUE,
            created_at TEXT
        )
        """)
        self.conn.commit()

    def add_session(self, phone, session_name):
        self.cursor.execute(
            "INSERT OR IGNORE INTO sessions (phone, session_name, created_at) VALUES (?, ?, ?)",
            (phone, session_name, datetime.utcnow().isoformat())
        )
        self.conn.commit()

    def delete_session(self, session_name):
        self.cursor.execute(
            "DELETE FROM sessions WHERE session_name = ?",
            (session_name,)
        )
        self.conn.commit()

    def get_sessions(self):
        self.cursor.execute(
            "SELECT phone, session_name FROM sessions ORDER BY id DESC"
        )
        return self.cursor.fetchall()
