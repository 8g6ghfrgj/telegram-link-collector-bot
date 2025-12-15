# session_manager.py
import sqlite3
from telethon import TelegramClient
from telethon.sessions import StringSession

# قيم ثابتة (لا مشكلة تكون وهمية إذا الجلسة جاهزة)
API_ID = 123456
API_HASH = "0123456789abcdef0123456789abcdef"

DB_NAME = "sessions.db"


class SessionManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create()

    def _create(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_string TEXT UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()

    # إضافة Session String
    def add_session(self, session_string: str):
        self.cursor.execute(
            "INSERT OR IGNORE INTO sessions (session_string) VALUES (?)",
            (session_string.strip(),)
        )
        self.conn.commit()

    # جلب كل الجلسات
    def get_all_sessions(self):
        self.cursor.execute("SELECT session_string FROM sessions")
        return [row[0] for row in self.cursor.fetchall()]

    # تحميل كل عملاء Telethon
    def load_clients(self):
        clients = []
        for session_string in self.get_all_sessions():
            try:
                client = TelegramClient(
                    StringSession(session_string),
                    API_ID,
                    API_HASH
                )
                clients.append(client)
            except Exception:
                continue
        return clients
