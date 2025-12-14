# session_manager.py
import os
import sqlite3

SESSIONS_DIR = "sessions"
DB_PATH = "sessions.db"

os.makedirs(SESSIONS_DIR, exist_ok=True)


class SessionsDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                session_name TEXT UNIQUE
            )
        """)
        self.conn.commit()

    def add(self, phone, session_name):
        self.cursor.execute(
            "INSERT OR IGNORE INTO sessions (phone, session_name) VALUES (?, ?)",
            (phone, session_name)
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
            "SELECT phone, session_name FROM sessions ORDER BY id DESC"
        )
        return self.cursor.fetchall()


sessions_db = SessionsDB()


def save_uploaded_session(temp_path: str, filename: str):
    """
    حفظ ملف session مرفوع
    """
    session_name = filename.replace(".session", "")
    target = os.path.join(SESSIONS_DIR, filename)

    os.replace(temp_path, target)

    sessions_db.add("uploaded", session_name)
    return session_name


def get_sessions_count():
    return len(sessions_db.all())
