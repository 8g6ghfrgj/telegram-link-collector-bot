# session_manager.py
import os
from telethon import TelegramClient
from sessions_db import SessionsDB

SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

sessions_db = SessionsDB()


def save_uploaded_session(file_path: str, original_name: str):
    """
    حفظ ملف session مرفوع
    """
    session_name = original_name.replace(".session", "")
    target = os.path.join(SESSIONS_DIR, original_name)

    os.replace(file_path, target)

    sessions_db.add_session(
        phone="uploaded",
        session_name=session_name
    )

    return session_name


def load_all_clients(api_id=None, api_hash=None):
    """
    تحميل كل الجلسات الموجودة
    """
    clients = []

    for _, session_name in sessions_db.get_sessions():
        try:
            client = TelegramClient(
                os.path.join(SESSIONS_DIR, session_name),
                api_id,
                api_hash
            )
            clients.append(client)
        except:
            continue

    return clients
