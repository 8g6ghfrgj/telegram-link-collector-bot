import sqlite3
import os
import uuid
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH, DATABASE_PATH


# ======================
# Database Helper
# ======================

def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def ensure_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            session TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()
    conn.close()


# ======================
# Session Operations
# ======================

def add_session(session_string: str):
    """
    إضافة Session String بعد التحقق من صحته
    """
    ensure_table()

    # تحقق من أن الـ session صالح
    try:
        client = TelegramClient(
            StringSession(session_string),
            API_ID,
            API_HASH
        )
        client.connect()
        if not client.is_user_authorized():
            client.disconnect()
            raise ValueError("Session غير صالح أو منتهي")
        client.disconnect()
    except Exception:
        raise ValueError("Session String غير صحيح")

    name = f"Account-{uuid.uuid4().hex[:6]}"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sessions (name, session) VALUES (?, ?)",
            (name, session_string)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("هذا الحساب مضاف مسبقاً")
    finally:
        conn.close()


def get_all_sessions():
    ensure_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, session FROM sessions")
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "session": row[2]
        }
        for row in rows
    ]


def delete_session(session_id: int):
    ensure_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM sessions WHERE id = ?",
        (session_id,)
    )
    conn.commit()
    conn.close()
