# session_manager.py
import os
import sqlite3
from telethon import TelegramClient
from telethon.sessions import StringSession

SESSIONS_DIR = "sessions"
DB_PATH = "sessions.db"

os.makedirs(SESSIONS_DIR, exist_ok=True)


class SessionsDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                session_file TEXT UNIQUE
            )
        """)
        self.conn.commit()

    def add(self, phone, session_file):
        self.conn.execute(
            "INSERT OR IGNORE INTO sessions (phone, session_file) VALUES (?, ?)",
            (phone, session_file)
        )
        self.conn.commit()

    def delete(self, session_file):
        self.conn.execute(
            "DELETE FROM sessions WHERE session_file = ?",
            (session_file,)
        )
        self.conn.commit()

    def all(self):
        cur = self.conn.cursor()
        cur.execute("SELECT phone, session_file FROM sessions")
        return cur.fetchall()


sessions_db = SessionsDB()


# ===============================
# إضافة جلسة من StringSession
# ===============================
def add_string_session(string_session, phone="manual"):
    path = os.path.join(SESSIONS_DIR, f"{phone}.session")
    with open(path, "w") as f:
        f.write(string_session)
    sessions_db.add(phone, path)


# ===============================
# تحميل كل الجلسات
# ===============================
def load_all_clients(api_id, api_hash):
    clients = []
    for phone, session_file in sessions_db.all():
        if not os.path.exists(session_file):
            continue

        with open(session_file) as f:
            string = f.read().strip()

        client = TelegramClient(
            StringSession(string),
            api_id,
            api_hash
        )
        clients.append(client)

    return clients


def get_sessions_count():
    return len(sessions_db.all())
