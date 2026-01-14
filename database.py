import sqlite3
import os
import shutil
import zipfile
from typing import Dict, List, Tuple
from datetime import datetime

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

    dir_name = os.path.dirname(DATABASE_PATH)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

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

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_links_platform_type
        ON links (platform, chat_type)
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
# Pagination (القديمة - لا نلمسها)
# ======================

def get_links_by_platform_paginated(
    platform: str,
    limit: int,
    offset: int
) -> List[Tuple[str, str]]:
    """
    جلب الروابط حسب المنصة فقط
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
# Pagination (جديدة: منصة + نوع)
# ======================

def get_links_by_platform_and_type(
    platform: str,
    chat_type: str,
    limit: int,
    offset: int
) -> List[Tuple[str, str]]:
    """
    جلب الروابط حسب:
    - المنصة (telegram / whatsapp)
    - النوع (group / channel)
    مع Pagination
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT url, message_date
        FROM links
        WHERE platform = ? AND chat_type = ?
        ORDER BY message_date DESC
        LIMIT ? OFFSET ?
        """,
        (platform, chat_type, limit, offset)
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


# ======================
# ✅ Backup System (NEW)
# ======================

def create_backup_zip(max_keep: int = 15) -> str | None:
    """
    إنشاء نسخة احتياطية ZIP تشمل:
    - DATABASE_PATH (مثل links.db)
    - مجلد exports/ (إذا موجود)

    ويرجع مسار ملف الـ backup النهائي.

    max_keep: عدد النسخ التي نحتفظ بها في backups/
    """
    # تأكد أن قاعدة البيانات موجودة
    if not os.path.exists(DATABASE_PATH):
        return None

    os.makedirs("backups", exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"backup_{ts}.zip"
    backup_path = os.path.join("backups", backup_name)

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as z:
        # 1) DB
        z.write(DATABASE_PATH, arcname=os.path.basename(DATABASE_PATH))

        # 2) exports folder
        if os.path.exists("exports") and os.path.isdir("exports"):
            for root, _, files in os.walk("exports"):
                for f in files:
                    full_path = os.path.join(root, f)
                    arc = os.path.relpath(full_path, start=".")
                    z.write(full_path, arcname=arc)

    # تنظيف النسخ القديمة
    _cleanup_old_backups(max_keep=max_keep)

    return backup_path


def _cleanup_old_backups(max_keep: int = 15):
    """
    يحذف أقدم النسخ في backups/ ويحتفظ بآخر max_keep فقط
    """
    if not os.path.exists("backups"):
        return

    files = []
    for f in os.listdir("backups"):
        if f.lower().endswith(".zip"):
            full = os.path.join("backups", f)
            files.append(full)

    # ترتيب حسب وقت التعديل
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    # حذف الزائد
    for old in files[max_keep:]:
        try:
            os.remove(old)
        except Exception:
            pass
