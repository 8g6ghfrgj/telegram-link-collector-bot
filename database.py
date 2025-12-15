import sqlite3
import os
from typing import Dict, List
from datetime import datetime

from config import DATABASE_PATH


# ======================
# Connection
# ======================

def get_connection():
    return sqlite3.connect(DATABASE_PATH, check_same_thread=False)


# ======================
# Init
# ======================

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            platform TEXT,
            source_account TEXT,
            chat_type TEXT,
            chat_id TEXT,
            message_date TEXT
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_platform
        ON links (platform)
    """)

    conn.commit()
    conn.close()


# ======================
# Save Link
# ======================

def save_link(
    url: str,
    platform: str | None,
    source_account: str,
    chat_type: str,
    chat_id: str,
    message_date
):
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
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT platform, COUNT(*)
        FROM links
        GROUP BY platform
    """)

    rows = cur.fetchall()
    conn.close()

    stats = {}
    for platform, count in rows:
        stats[platform or "other"] = count

    return stats


# ======================
# Pagination
# ======================

def get_links_paginated(
    platform: str | None,
    limit: int,
    offset: int
) -> List[str]:

    conn = get_connection()
    cur = conn.cursor()

    if platform and platform != "all":
        cur.execute(
            """
            SELECT url FROM links
            WHERE platform = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (platform, limit, offset)
        )
    else:
        cur.execute(
            """
            SELECT url FROM links
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )

    rows = cur.fetchall()
    conn.close()

    return [r[0] for r in rows]


# ======================
# Export
# ======================

def export_links(platform: str) -> str:
    conn = get_connection()
    cur = conn.cursor()

    if platform == "all":
        cur.execute("SELECT url FROM links ORDER BY id ASC")
        filename = "links_all.txt"
    else:
        cur.execute(
            "SELECT url FROM links WHERE platform = ? ORDER BY id ASC",
            (platform,)
        )
        filename = f"links_{platform}.txt"

    rows = cur.fetchall()
    conn.close()

    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", filename)

    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(row[0] + "\n")

    return path
