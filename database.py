# database.py
import sqlite3
from datetime import datetime

DB_NAME = "links.db"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._setup()

    def _setup(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            category TEXT,
            year INTEGER,
            created_at TEXT
        )
        """)

        # فهارس (مهم جداً للأداء)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_category_year ON links(category, year)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_url ON links(url)"
        )

        self.conn.commit()

    # -------------------------
    # إضافة رابط
    # -------------------------
    def add_link(self, url: str, category: str):
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO links (url, category, year, created_at) VALUES (?, ?, ?, ?)",
                (url, category, datetime.utcnow().year, datetime.utcnow().isoformat())
            )
            self.conn.commit()
        except:
            pass

    # -------------------------
    # سنوات
    # -------------------------
    def get_years(self):
        self.cursor.execute(
            "SELECT DISTINCT year FROM links ORDER BY year DESC"
        )
        return [r[0] for r in self.cursor.fetchall()]

    # -------------------------
    # Pagination
    # -------------------------
    def get_links_paginated(self, category, year, limit, offset):
        self.cursor.execute("""
            SELECT url FROM links
            WHERE category = ? AND year = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (category, year, limit, offset))
        return [r[0] for r in self.cursor.fetchall()]

    def count_links(self, category, year):
        self.cursor.execute("""
            SELECT COUNT(*) FROM links
            WHERE category = ? AND year = ?
        """, (category, year))
        return self.cursor.fetchone()[0]

    # -------------------------
    # البحث
    # -------------------------
    def search_links(self, keyword, limit=50):
        self.cursor.execute("""
            SELECT url FROM links
            WHERE url LIKE ?
            ORDER BY id DESC
            LIMIT ?
        """, (f"%{keyword}%", limit))
        return [r[0] for r in self.cursor.fetchall()]

    # -------------------------
    # التصدير
    # -------------------------
    def export_links(self, category, year):
        self.cursor.execute("""
            SELECT url FROM links
            WHERE category = ? AND year = ?
            ORDER BY id DESC
        """, (category, year))
        return [r[0] for r in self.cursor.fetchall()]
