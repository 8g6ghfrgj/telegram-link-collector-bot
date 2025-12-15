import sqlite3
import os
from config import DATABASE_PATH


def conn():
    return sqlite3.connect(DATABASE_PATH, check_same_thread=False)


def init_db():
    c = conn()
    cur = c.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            platform TEXT,
            source_account TEXT,
            chat_type TEXT,
            chat_id TEXT,
            message_date TEXT
        )
    """)
    c.commit()
    c.close()


def save_link(url, platform, source, chat_type, chat_id, date):
    if not url:
        return
    c = conn()
    cur = c.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO links VALUES (NULL,?,?,?,?,?,?)",
        (url, platform, source, chat_type, chat_id, str(date))
    )
    c.commit()
    c.close()


def count_links_by_platform():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT platform, COUNT(*) FROM links GROUP BY platform")
    rows = cur.fetchall()
    c.close()
    return {r[0] or "other": r[1] for r in rows}


def get_links(limit=20, offset=0):
    c = conn()
    cur = c.cursor()
    cur.execute("""
        SELECT url, message_date
        FROM links
        ORDER BY message_date DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cur.fetchall()
    c.close()
    return rows


def export_links(platform="all"):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT url FROM links ORDER BY id ASC")
    rows = cur.fetchall()
    c.close()

    if not rows:
        return None

    os.makedirs("exports", exist_ok=True)
    path = "exports/links_all.txt"

    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(r[0] + "\n")

    return path
