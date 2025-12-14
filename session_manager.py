# session_manager.py
import os
import sqlite3
from telethon import TelegramClient

# ==================================================
# قيم ثابتة (لمنع الخطأ)
# ==================================================
API_ID = 123456
API_HASH = "0123456789abcdef0123456789abcdef"

# ==================================================
SESSIONS_DIR = "sessions"
DB_PATH = "sessions.db"

os.makedirs(SESSIONS_DIR, exist_ok=True)


class SessionsDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create()

    def _create(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT UNIQUE,
                created_at TEXT
            )
        """)
        self.conn.commit()

    def add(self, session_name):
        self.cursor.execute(
            "INSERT OR IGNORE INTO sessions (session_name, created_at) VALUES (?, datetime('now'))",
            (session_name,)
        )
        self.conn.commit()

    def delete(self, session_name):
        self.cursor.execute(
            "DELETE FROM sessions WHERE session_name = ?",
            (session_name,)
        )
        self.conn.commit()

    def all(self):
        self.cursor.execute(
            "SELECT session_name FROM sessions ORDER BY id DESC"
        )
        return [row[0] for row in self.cursor.fetchall()]


sessions_db = SessionsDB()


# ==================================================
# حفظ جلسة مرفوعة
# ==================================================
def save_uploaded_session(temp_path: str, filename: str):
    session_name = filename.replace(".session", "")
    target = os.path.join(SESSIONS_DIR, filename)

    os.replace(temp_path, target)
    sessions_db.add(session_name)

    return session_name


# ==================================================
# تحميل كل الجلسات
# ==================================================
def load_all_clients():
    clients = []

    for name in sessions_db.all():
        session_path = os.path.join(SESSIONS_DIR, name)

        try:
            client = TelegramClient(session_path, API_ID, API_HASH)
            clients.append(client)
        except Exception:
            continue

    return clients


def get_sessions_count():
    return len(sessions_db.all())
