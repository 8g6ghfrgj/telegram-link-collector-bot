# session_manager.py
import os
import sqlite3
from telethon import TelegramClient
from telethon.sessions import StringSession

# =========================
# الإعدادات
# =========================
SESSIONS_DB = "sessions.db"

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")

# =========================
# قاعدة البيانات
# =========================
class SessionsDB:
    def __init__(self):
        self.conn = sqlite3.connect(SESSIONS_DB, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                session_string TEXT UNIQUE
            )
        """)
        self.conn.commit()

    def add(self, phone, session_string):
        self.cursor.execute(
            "INSERT OR IGNORE INTO sessions (phone, session_string) VALUES (?, ?)",
            (phone, session_string)
        )
        self.conn.commit()

    def delete(self, session_string):
        self.cursor.execute(
            "DELETE FROM sessions WHERE session_string = ?",
            (session_string,)
        )
        self.conn.commit()

    def all(self):
        self.cursor.execute(
            "SELECT phone, session_string FROM sessions ORDER BY id DESC"
        )
        return self.cursor.fetchall()


sessions_db = SessionsDB()

# =========================
# إضافة Session String
# =========================
def add_session_string(session_string: str, phone: str = "manual"):
    sessions_db.add(phone, session_string)

# =========================
# تحميل كل الجلسات (مهم لـ collector)
# =========================
def load_all_clients():
    clients = []

    if not API_ID or not API_HASH:
        print("❌ API_ID أو API_HASH غير موجود")
        return clients

    for phone, session_string in sessions_db.all():
        try:
            client = TelegramClient(
                StringSession(session_string),
                API_ID,
                API_HASH
            )
            clients.append(client)
        except Exception as e:
            print(f"❌ فشل تحميل جلسة {phone}: {e}")

    return clients

# =========================
def get_sessions_count():
    return len(sessions_db.all())
