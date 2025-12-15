import sqlite3
import os
from typing import Dict, List, Tuple

from config import DATABASE_PATH


# ======================
# Connection
# ======================

def get_connection():
    return sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False
    )


# ======================
# Init
# ======================

def init_db():
    """
    إنشاء جدول الروابط
    مع منع التكرار (url UNIQUE)
    """
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            source_account TEXT,
            chat_type TEXT,
            chat_id TEXT,
            message_date TEXT
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_links_platform
        ON links (platform)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_links_date
        ON links (message_date)
    """)

    conn.commit()
    conn.close()


# ======================
# Save Link
# ======================

def save_link(
    url: str,
    platform: str,
    source_account: str,
    chat_type: str,
    chat_id: str,
    message_date
):
    """
    حفظ الرابط مرة واحدة فقط مهما تكرر
    """
    if not url:
        return

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT OR IGNORE INTO links
            (url, platform, source_account, chat_type, chat_id, message_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                platform,
                source_account,
                chat_type,
                chat_id,
                message_date.isoformat() if message_date else None
            )
        )
        conn.commit()
    finally:
        conn.close()


# ======================
# Stats
# ======================

def count_links_by_platform() -> Dict[str, int]:
    """
    إحصائيات الروابط حسب المنصة
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT platform, COUNT(*)
        FROM links
        GROUP BY platform
    """)

    rows = cur.fetchall()
    conn.close()

    return {platform: count for platform, count in rows}


# ======================
# Pagination / View
# ======================

def get_links_by_platform_paginated(
    platform: str,
    limit: int,
    offset: int
) -> List[Tuple[str, str]]:
    """
    جلب الروابط حسب المنصة
    مع Pagination
    مرتبة بالأحدث أولاً
    """
    conn = get_connection()
    cur = conn.cursor()

    if platform == "all":
        cur.execute(
            """
            SELECT url, message_date
            FROM links
            ORDER BY message_date DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
    else:
        cur.execute(
            """
            SELECT url, message_date
            FROM links
            WHERE platform = ?
            ORDER BY message_date DESC
            LIMIT ? OFFSET ?
            """,
            (platform, limit, offset)
        )

    rows = cur.fetchall()
    conn.close()

    return rows


# ======================
# Export
# ======================

def export_links(platform: str) -> str | None:
    """
    تصدير الروابط إلى ملف TXT
    (الكل أو حسب المنصة)
    """
    conn = get_connection()
    cur = conn.cursor()

    if platform == "all":
        cur.execute("""
            SELECT url FROM links
            ORDER BY message_date ASC
        """)
        filename = "links_all.txt"
    else:
        cur.execute("""
            SELECT url FROM links
            WHERE platform = ?
            ORDER BY message_date ASC
        """, (platform,))
        filename = f"links_{platform}.txt"

    rows = cur.fetchall()
    conn.close()

    if not rows:
        return None

    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", filename)

    with open(path, "w", encoding="utf-8") as f:
        for (url,) in rows:
            f.write(url + "\n")

    return path
