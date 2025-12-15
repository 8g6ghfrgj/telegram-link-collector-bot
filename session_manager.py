# session_manager.py
import os
import sqlite3
from telethon import TelegramClient
from telethon.sessions import StringSession

SESSIONS_DIR = "sessions"
DB_NAME = "sessions.db"

os.makedirs(SESSIONS_DIR, exist_ok=True)


class SessionsDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cur = self.conn.cursor()
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_string TEXT UNIQUE
        )
        """)
        self.conn.commit()

    def add(self, session_string: str):
        self.cur.execute(
            "INSERT OR IGNORE INTO sessions (session_string) VALUES (?)",
            (session_string,)
        )
        self.conn.commit()

    def all(self):
        self.cur.execute("SELECT session_string FROM sessions")
        return [r[0] for r in self.cur.fetchall()]


sessions_db = SessionsDB()


# ===============================
# إضافة Session String
# ===============================
def add_session_string(session_string: str):
    sessions_db.add(session_string)


# ===============================
# تحميل كل الجلسات (مهم جداً)
# ===============================
def load_all_clients(api_id: int, api_hash: str):
    clients = []

    for s in sessions_db.all():
        client = TelegramClient(
            StringSession(s),
            api_id,
            api_hash
        )
        clients.append(client)

    return clients
