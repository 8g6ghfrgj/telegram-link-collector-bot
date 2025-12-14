# database.py
import sqlite3
from datetime import datetime

DB_NAME = "links.db"


class Database:
    def __init__(self):
        # check_same_thread=False مهم لـ Render و async
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.create_tables()

    # =========================
    # إنشاء الجداول
    # =========================
    def create_tables(self):
        cur = self.conn.cursor()

        # جدول الروابط
        cur.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            category TEXT,
            year INTEGER,
            created_at TEXT
        )
        """)

        # فهارس لتحسين الأداء (مهم جداً مع كثرة الروابط)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_category ON links(category)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_year ON links(year)"
        )

        self.conn.commit()

    # =========================
    # إضافة رابط (بدون تكرار)
    # =========================
    def add_link(self, url: str, category: str):
        try:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO links
                (url, category, year, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    url,
                    category,
                    datetime.now().year,
                    datetime.now().isoformat()
                )
            )
            self.conn.commit()
        except Exception:
            # تجاهل أي خطأ بدون كسر البوت
            pass

    # =========================
    # جلب السنوات المتوفرة
    # =========================
    def get_years(self):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT DISTINCT year FROM links ORDER BY year DESC"
        )
        return [row[0] for row in cur.fetchall()]

    # =========================
    # جلب الروابط مع Pagination
    # =========================
    def get_links_paginated(
        self,
        category: str,
        year: int,
        limit: int = 30,
        offset: int = 0
    ):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT url FROM links
            WHERE category = ? AND year = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (category, year, limit, offset)
        )
        return [row[0] for row in cur.fetchall()]

    # =========================
    # (اختياري) إحصائيات سريعة
    # =========================
    def count_links(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM links")
        return cur.fetchone()[0]
