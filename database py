# database.py
import sqlite3
from datetime import datetime

DB_NAME = "links.db"


class Database:
    def __init__(self):
        # check_same_thread=False مهم لـ Render
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # ========================
        # جدول الجلسات
        # ========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_string TEXT UNIQUE,
            added_at DATETIME
        )
        """)

        # ========================
        # جدول الروابط
        # ========================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            category TEXT,
            year INTEGER,
            added_at DATETIME
        )
        """)

        # فهارس للأداء العالي
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_category ON links(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_year ON links(year)")

        self.conn.commit()

    # =================================================
    # الجلسات
    # =================================================
    def add_session(self, session_string: str) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO sessions (session_string, added_at) VALUES (?, ?)",
                (session_string, datetime.utcnow())
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # الجلسة موجودة مسبقاً
            return False

    def get_sessions(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT session_string FROM sessions")
        return [row[0] for row in cursor.fetchall()]

    def get_sessions_with_id(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, session_string FROM sessions")
        return cursor.fetchall()

    def delete_session(self, session_id: int):
        self.conn.execute(
            "DELETE FROM sessions WHERE id = ?",
            (session_id,)
        )
        self.conn.commit()

    # =================================================
    # الروابط
    # =================================================
    def add_link(self, url: str, category: str, year: int):
        try:
            self.conn.execute(
                """
                INSERT INTO links (url, category, year, added_at)
                VALUES (?, ?, ?, ?)
                """,
                (url, category, year, datetime.utcnow())
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # تجاهل التكرار
            pass
