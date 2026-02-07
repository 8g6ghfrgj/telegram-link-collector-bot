import sqlite3
import os
from typing import Optional

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
    قاعدة البيانات الآن مخصصة فقط لـ:
    - تخزين قنوات / قروبات كل مشرف
    - لا تخزين روابط
    """

    dir_name = os.path.dirname(DATABASE_PATH)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            target_chat TEXT NOT NULL,
            UNIQUE(admin_id, platform)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_admin_targets_admin
        ON admin_targets (admin_id)
    """)

    conn.commit()
    conn.close()


# ======================
# Admin Targets
# ======================

def save_admin_target(admin_id: int, platform: str, target_chat: str):
    """
    حفظ أو تحديث قناة / قروب المشرف
    لكل منصة (whatsapp / telegram)
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO admin_targets (admin_id, platform, target_chat)
        VALUES (?, ?, ?)
        ON CONFLICT(admin_id, platform)
        DO UPDATE SET target_chat = excluded.target_chat
    """, (admin_id, platform, target_chat))

    conn.commit()
    conn.close()


def get_admin_target(admin_id: int, platform: str) -> Optional[str]:
    """
    جلب قناة / قروب المشرف لمنصة معينة
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT target_chat
        FROM admin_targets
        WHERE admin_id = ? AND platform = ?
        LIMIT 1
    """, (admin_id, platform))

    row = cur.fetchone()
    conn.close()

    return row[0] if row else None
