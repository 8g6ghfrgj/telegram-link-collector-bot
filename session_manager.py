import sqlite3
import uuid
from datetime import datetime

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH, DATABASE_PATH


# ======================
# Database Helpers
# ======================

def get_connection():
    return sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False
    )


def init_sessions_table():
    """
    جدول الجلسات (Telegram Accounts)

    كل Session يمثل:
    - حساب تيليجرام مستقل
    - يُعتبر Admin مستقل في النظام
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            session TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            disabled_reason TEXT,
            created_at TEXT
        )
    """)

    # Migration (آمن)
    cur.execute("PRAGMA table_info(sessions)")
    cols = [r[1] for r in cur.fetchall()]

    if "active" not in cols:
        cur.execute("ALTER TABLE sessions ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    if "disabled_reason" not in cols:
        cur.execute("ALTER TABLE sessions ADD COLUMN disabled_reason TEXT")
    if "created_at" not in cols:
        cur.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT")

    conn.commit()
    conn.close()


# ======================
# Session Validation
# ======================

def _validate_session_string(session_string: str):
    """
    التحقق من أن Session String صالح
    ويملك صلاحية الدخول
    """
    client = TelegramClient(
        StringSession(session_string),
        API_ID,
        API_HASH
    )

    try:
        client.connect()

        if not client.is_user_authorized():
            raise ValueError("Session غير صالح أو منتهي")

    except ValueError:
        raise
    except Exception:
        raise ValueError("Session String غير صحيح")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


# ======================
# Session Operations
# ======================

def add_session(session_string: str):
    """
    إضافة Session String جديد

    ملاحظة معمارية مهمة:
    - كل Session = Admin مستقل
    - يملك قنواته الخاصة
    """
    init_sessions_table()
    _validate_session_string(session_string)

    account_name = f"Account-{uuid.uuid4().hex[:6]}"
    created_at = datetime.utcnow().isoformat()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO sessions
            (name, session, active, disabled_reason, created_at)
            VALUES (?, ?, 1, NULL, ?)
        """, (account_name, session_string, created_at))
        conn.commit()

    except sqlite3.IntegrityError:
        raise ValueError("هذا الحساب مضاف مسبقًا")

    finally:
        conn.close()


def get_all_sessions(include_inactive: bool = False):
    """
    جلب جميع الجلسات

    include_inactive = False
    → فقط الجلسات الفعالة
    """
    init_sessions_table()

    conn = get_connection()
    cur = conn.cursor()

    if include_inactive:
        cur.execute("""
            SELECT id, name, session, active, disabled_reason
            FROM sessions
        """)
    else:
        cur.execute("""
            SELECT id, name, session, active, disabled_reason
            FROM sessions
            WHERE active = 1
        """)

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "name": r[1],
            "session": r[2],
            "active": int(r[3]),
            "disabled_reason": r[4],
        }
        for r in rows
    ]


def disable_session(session_id: int, reason: str = "Disabled by admin"):
    """
    تعطيل جلسة بدون حذفها
    """
    init_sessions_table()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE sessions
        SET active = 0,
            disabled_reason = ?
        WHERE id = ?
    """, (reason, session_id))

    conn.commit()
    conn.close()


def enable_session(session_id: int):
    """
    إعادة تفعيل جلسة
    """
    init_sessions_table()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE sessions
        SET active = 1,
            disabled_reason = NULL
        WHERE id = ?
    """, (session_id,))

    conn.commit()
    conn.close()


def delete_session(session_id: int):
    """
    حذف جلسة يدويًا (قرار إداري فقط)
    """
    init_sessions_table()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM sessions WHERE id = ?",
        (session_id,)
    )

    conn.commit()
    conn.close()
