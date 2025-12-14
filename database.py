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
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                category TEXT,
                year INTEGER,
                created_at TEXT
            )
        """)
        self.conn.commit()

    # -------------------------
    # إضافة رابط بدون تكرار
    # -------------------------
    def add_link(self, url: str, category: str):
        year = datetime.utcnow().year
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO links (url, category, year, created_at) VALUES (?, ?, ?, ?)",
                (url, category, year, datetime.utcnow().isoformat())
            )
            self.conn.commit()
        except Exception:
            pass

    # -------------------------
    # جلب السنوات المتوفرة
    # -------------------------
    def get_years(self):
        self.cursor.execute(
            "SELECT DISTINCT year FROM links ORDER BY year DESC"
        )
        return [row[0] for row in self.cursor.fetchall()]

    # -------------------------
    # Pagination
    # -------------------------
    def get_links_paginated(self, category, year, limit, offset):
        self.cursor.execute("""
            SELECT url FROM links
            WHERE category = ? AND year = ?
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (category, year, limit, offset))
        return [row[0] for row in self.cursor.fetchall()]

    # -------------------------
    # عدّاد الروابط
    # -------------------------
    def count_links(self, category, year):
        self.cursor.execute("""
            SELECT COUNT(*) FROM links
            WHERE category = ? AND year = ?
        """, (category, year))
        return self.cursor.fetchone()[0]
