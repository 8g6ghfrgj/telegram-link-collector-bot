# session_manager.py
import sqlite3
from telethon import TelegramClient
from telethon.sessions import StringSession

# ===============================
# إعداد قاعدة بيانات الجلسات
# ===============================
DB_NAME = "sessions.db"


class SessionManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_string TEXT UNIQUE
        )
        """)
        self.conn.commit()

    # ===============================
    # إضافة Session String
    # ===============================
    def add_session(self, session_string: str) -> bool:
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO sessions (session_string) VALUES (?)",
                (session_string,)
            )
            self.conn.commit()
            return True
        except Exception:
            return False

    # ===============================
    # حذف جلسة
    # ===============================
    def delete_session(self, session_string: str):
        self.cursor.execute(
            "DELETE FROM sessions WHERE session_string = ?",
            (session_string,)
        )
        self.conn.commit()

    # ===============================
    # جلب كل الجلسات
    # ===============================
    def get_all_sessions(self):
        self.cursor.execute(
            "SELECT session_string FROM sessions"
        )
        return [row[0] for row in self.cursor.fetchall()]

    # ===============================
    # تحميل كل الجلسات كـ Telethon Clients
    # ===============================
    def load_clients(self, api_id: int, api_hash: str):
        clients = []
        for session_string in self.get_all_sessions():
            try:
                client = TelegramClient(
                    StringSession(session_string),
                    api_id,
                    api_hash
                )
                clients.append(client)
            except Exception:
                continue
        return clients
