# database.py
import sqlite3
from datetime import datetime
from typing import List, Tuple

DB_NAME = "links.db"


class Database:
    def __init__(self, db_path: str = DB_NAME):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._create_indexes()

    # -------------------------------------------------
    # إنشاء الجداول
    # -------------------------------------------------
    def _create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            category TEXT,
            source TEXT,
            chat_id TEXT,
            chat_title TEXT,
            year INTEGER,
            created_at TEXT
        )
        """)
        self.conn.commit()

    # -------------------------------------------------
    # فهارس لتحسين الأداء (مهم جداً)
    # -------------------------------------------------
    def _create_indexes(self):
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_category_year ON links(category, year)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_id ON links(chat_id)"
        )
        self.conn.commit()

    # -------------------------------------------------
    # إضافة رابط (بدون تكرار نهائياً)
    # -------------------------------------------------
    def add_link(
        self,
        url: str,
        category: str,
        source: str,
        chat_id: str,
        chat_title: str
    ):
        year = datetime.utcnow().year
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO links
                (url, category, source, chat_id, chat_title, year, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                category,
                source,
                chat_id,
                chat_title,
                year,
                datetime.utcnow().isoformat()
            ))
            self.conn.commit()
        except Exception:
            pass

    # -------------------------------------------------
    # جلب السنوات المتوفرة
    # -------------------------------------------------
    def get_years(self) -> List[int]:
        cur = self.conn.execute(
            "SELECT DISTINCT year FROM links ORDER BY year DESC"
        )
        return [row["year"] for row in cur.fetchall()]

    # -------------------------------------------------
    # عدّاد الروابط
    # -------------------------------------------------
    def count_links(self, category: str, year: int) -> int:
        cur = self.conn.execute("""
            SELECT COUNT(*) as total FROM links
            WHERE category = ? AND year = ?
        """, (category, year))
        return cur.fetchone()["total"]

    # -------------------------------------------------
    # Pagination (عرض داخل البوت)
    # -------------------------------------------------
    def get_links_paginated(
        self,
        category: str,
        year: int,
        limit: int,
        offset: int
    ) -> List[str]:
        cur = self.conn.execute("""
            SELECT url FROM links
            WHERE category = ? AND year = ?
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (category, year, limit, offset))
        return [row["url"] for row in cur.fetchall()]

    # -------------------------------------------------
    # تصدير الروابط (TXT)
    # -------------------------------------------------
    def export_links(self, category: str, year: int) -> List[str]:
        cur = self.conn.execute("""
            SELECT url FROM links
            WHERE category = ? AND year = ?
            ORDER BY id ASC
        """, (category, year))
        return [row["url"] for row in cur.fetchall()]

    # -------------------------------------------------
    # بحث سريع داخل الروابط
    # -------------------------------------------------
    def search_links(self, keyword: str, limit: int = 50) -> List[str]:
        cur = self.conn.execute("""
            SELECT url FROM links
            WHERE url LIKE ?
            ORDER BY id DESC
            LIMIT ?
        """, (f"%{keyword}%", limit))
        return [row["url"] for row in cur.fetchall()]

    # -------------------------------------------------
    # إغلاق الاتصال
    # -------------------------------------------------
    def close(self):
        self.conn.close()
