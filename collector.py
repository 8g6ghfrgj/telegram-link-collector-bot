import asyncio
import logging
from typing import List

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Message

from config import API_ID, API_HASH
from session_manager import get_all_sessions
from database import save_link
from link_utils import (
    extract_links_from_message,
    classify_platform,
    filter_and_classify_link,   # ✅ إضافة فقط
)
from file_extractors import extract_links_from_file

# ======================
# Logging
# ======================

logger = logging.getLogger(__name__)

# ======================
# Global State
# ======================

_clients: List[TelegramClient] = []
_collecting: bool = False
_stop_event = asyncio.Event()


# ======================
# Public API
# ======================

def is_collecting() -> bool:
    return _collecting


def stop_collection():
    """
    يوقف الاستماع للرسائل الجديدة فقط
    لا يحذف أي بيانات
    """
    global _collecting
    _collecting = False
    _stop_event.set()
    logger.info("Collection stopped (listening disabled).")


async def start_collection():
    """
    تشغيل كل Sessions
    وبدء جمع التاريخ + الاستماع للجديد
    """
    global _collecting, _clients

    if _collecting:
        logger.info("Collection already running.")
        return

    sessions = get_all_sessions()
    if not sessions:
        logger.warning("No sessions found.")
        return

    _collecting = True
    _stop_event.clear()
    _clients = []

    tasks = []
    for session in sessions:
        tasks.append(run_client(session))

    # تشغيل كل الحسابات معاً
    await asyncio.gather(*tasks)

    logger.info("Finished collecting old history.")


# ======================
# Client Runner
# ======================

async def run_client(session_data: dict):
    """
    تشغيل حساب واحد:
    - قراءة كل التاريخ
    - ثم الاستماع للجديد
    """
    session_string = session_data["session"]
    account_name = session_data["name"]

    client = TelegramClient(
        StringSession(session_string),
        API_ID,
        API_HASH
    )

    await client.connect()
    _clients.append(client)

    logger.info(f"Client started: {account_name}")

    # ======================
    # Listener (New Messages)
    # ======================

    @client.on(events.NewMessage)
    async def new_message_handler(event):
        if not _collecting:
            return

        await process_message(
            message=event.message,
            account_name=account_name,
            client=client
        )

    # ======================
    # Read Old History
    # ======================

    await collect_old_messages(client, account_name)

    # بعد الانتهاء من التاريخ نبقى فقط على الاستماع
    await _stop_event.wait()

    await client.disconnect()
    logger.info(f"Client stopped: {account_name}")


# ======================
# Collect History
# ======================

async def collect_old_messages(client: TelegramClient, account_name: str):
    """
    المرور على:
    - كل القنوات
    - كل الجروبات
    - كل المحادثات الخاصة
    وقراءة كل الرسائل من أول رسالة
    """
    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        chat_type = get_chat_type(entity)

        try:
            async for message in client.iter_messages(entity, reverse=True):
                if not _collecting:
                    return

                await process_message(
                    message=message,
                    account_name=account_name,
                    client=client,
                    chat_type_override=chat_type
                )

        except Exception as e:
            logger.error(f"Error reading dialog {dialog.name}: {e}")


# ======================
# Message Processing
# ======================

async def process_message(
    message: Message,
    account_name: str,
    client: TelegramClient,
    chat_type_override: str | None = None
):
    """
    استخراج كل الروابط من الرسالة:
    - النص
    - الروابط المخفية
    - الأزرار
    - الملفات (PDF / DOCX)
    ثم حفظها بدون تكرار
    """

    if not message:
        return

    chat = await message.get_chat()
    _ = chat_type_override or get_chat_type(chat)  # لم نعد نستخدمه للحفظ

    # ======================
    # 1️⃣ روابط النص + الأزرار
    # ======================

    links = extract_links_from_message(message)

    for link in links:
        classified = filter_and_classify_link(link)
        if not classified:
            continue  # ❌ تجاهل روابط غير مرغوبة

        platform, link_chat_type = classified

        save_link(
            url=link,
            platform=platform,
            source_account=account_name,
            chat_type=link_chat_type,  # ✅ group / channel
            chat_id=str(message.chat_id),
            message_date=message.date
        )

    # ======================
    # 2️⃣ روابط الملفات (PDF / DOCX)
    # ======================

    if message.file:
        try:
            file_links = await extract_links_from_file(
                client=client,
                message=message
            )

            for link in file_links:
                classified = filter_and_classify_link(link)
                if not classified:
                    continue

                platform, link_chat_type = classified

                save_link(
                    url=link,
                    platform=platform,
                    source_account=account_name,
                    chat_type=link_chat_type,
                    chat_id=str(message.chat_id),
                    message_date=message.date
                )

        except Exception as e:
            logger.error(f"File extraction error: {e}")


# ======================
# Helpers
# ======================

def get_chat_type(entity) -> str:
    """
    تحديد نوع المحادثة:
    channel / group / private
    """
    cls = entity.__class__.__name__.lower()

    if "channel" in cls:
        return "channel"
    if "chat" in cls:
        return "group"
    return "private"
