# session_manager.py
import os
import sqlite3
from telethon import TelegramClient
from telethon.sessions import StringSession

# =============================
# إعدادات ثابتة (افتراضية)
# =============================
API_ID = 123456        # أي رقم (لن يُستخدم إلا مع Telethon)
API_HASH = "0123456789abcdef0123456789abcdef"

DB_NAME = "sessions.db"

# =============================
# قاعدة بيانات الجلسات
# =============================
class SessionsDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_string TEXT UNIQUE
            )
        """)
        self.conn.commit()

    def add(self, session_string: str):
        self.cursor.execute(
            "INSERT OR IGNORE INTO sessions (session_string) VALUES (?)",
            (session_string,)
        )
        self.conn.commit()

    def delete(self, session_string: str):
        self.cursor.execute(
            "DELETE FROM sessions WHERE session_string = ?",
            (session_string,)
        )
        self.conn.commit()

    def all(self):
        self.cursor.execute("SELECT session_string FROM sessions")
        return [row[0] for row in self.cursor.fetchall()]


sessions_db = SessionsDB()

# =============================
# إضافة Session String
# =============================
def add_session_string(session_string: str):
    sessions_db.add(session_string)

# =============================
# تحميل كل الجلسات
# =============================
def load_all_clients():
    clients = []
    for s in sessions_db.all():
        try:
            client = TelegramClient(
                StringSession(s),
                API_ID,
                API_HASH
            )
            clients.append(client)
        except Exception as e:
            print("Session load error:", e)
    return clients

# =============================
def sessions_count():
    return len(sessions_db.all())
