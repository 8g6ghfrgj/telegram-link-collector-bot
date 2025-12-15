# database.py
import sqlite3
from datetime import datetime

DB_NAME = "links.db"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # جدول الروابط
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            source TEXT,
            chat_title TEXT,
            year INTEGER,
            created_at TEXT
        )
        """)

        # تحسين الأداء
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_year ON links(year)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_source ON links(source)"
        )

        self.conn.commit()

    # ----------------------------------
    # إضافة رابط (بدون تكرار)
    # ----------------------------------
    def add_link(self, url: str, source: str, chat_title: str):
        year = datetime.utcnow().year
        try:
            self.cursor.execute("""
                INSERT OR IGNORE INTO links
                (url, source, chat_title, year, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (url, source, chat_title, year, datetime.utcnow().isoformat()))
            self.conn.commit()
        except Exception:
            pass

    # ----------------------------------
    # جلب السنوات
    # ----------------------------------
    def get_years(self):
        self.cursor.execute(
            "SELECT DISTINCT year FROM links ORDER BY year DESC"
        )
        return [row[0] for row in self.cursor.fetchall()]

    # ----------------------------------
    # Pagination للعرض
    # ----------------------------------
    def get_links_paginated(self, year, limit, offset):
        self.cursor.execute("""
            SELECT url FROM links
            WHERE year = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (year, limit, offset))
        return [row[0] for row in self.cursor.fetchall()]

    def count_links(self, year):
        self.cursor.execute(
            "SELECT COUNT(*) FROM links WHERE year = ?",
            (year,)
        )
        return self.cursor.fetchone()[0]

    # ----------------------------------
    # تصدير (سيستخدم لاحقاً)
    # ----------------------------------
    def export_links(self, year):
        self.cursor.execute("""
            SELECT url FROM links
            WHERE year = ?
            ORDER BY id DESC
        """, (year,))
        return [row[0] for row in self.cursor.fetchall()]
