import asyncio
import logging
from typing import List
from datetime import datetime, timezone, timedelta

import requests

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Message

from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_CHAT_ID
from session_manager import get_all_sessions
from database import save_link
from link_utils import (
    extract_links_from_message,
    filter_and_classify_link,
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

# ✅ وقت بدء الجمع (لشرط 60 يوم واتساب)
_collect_started_at_utc: datetime | None = None

# ✅ لمنع جمع أكثر من رابط رسالة واحد لكل مجموعة/قناة
_collected_one_tg_message_link_per_chat: set[str] = set()

# ✅ تفعيل الإشعارات فقط بعد انتهاء جمع التاريخ
_notifications_enabled: bool = False


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
    global _collecting, _clients, _collect_started_at_utc, _notifications_enabled

    if _collecting:
        logger.info("Collection already running.")
        return

    sessions = get_all_sessions()
    if not sessions:
        logger.warning("No sessions found.")
        return

    # ✅ سجل وقت البداية (UTC) عند الضغط على زر بدء الجمع
    _collect_started_at_utc = datetime.now(timezone.utc)

    # ✅ Reset limiter
    _collected_one_tg_message_link_per_chat.clear()

    # ✅ أثناء جمع التاريخ: لا ترسل إشعارات
    _notifications_enabled = False

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
# Notifications
# ======================

def _safe_send_admin_message(text: str):
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return

    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params={
                "chat_id": ADMIN_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
    except Exception:
        pass


def notify_admin_new_link(
    url: str,
    platform: str,
    account_name: str,
    chat_type: str,
    chat_id: str,
    message_date: datetime | None = None
):
    try:
        dt = ""
        if message_date:
            try:
                dt = _to_utc(message_date).strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                dt = ""

        text = (
            "✅ رابط جديد تم جمعه\n\n"
            f"🔗 {url}\n\n"
            f"📌 المنصة: {platform}\n"
            f"💬 النوع: {chat_type}\n"
            f"👤 الحساب: {account_name}\n"
            f"🆔 chat_id: {chat_id}\n"
        )
        if dt:
            text += f"🕒 التاريخ: {dt}\n"

        _safe_send_admin_message(text)
    except Exception:
        pass


# ======================
# Client Runner
# ======================

async def run_client(session_data: dict):
    """
    تشغيل حساب واحد:
    - قراءة كل التاريخ
    - ثم الاستماع للجديد
    """
    global _notifications_enabled

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

    # ✅ بعد ما يخلص التاريخ نفعّل الإشعارات (مرة واحدة فقط)
    if not _notifications_enabled:
        _notifications_enabled = True
        _safe_send_admin_message("✅ تم الانتهاء من جمع الروابط القديمة. الآن سيتم إرسال الروابط الجديدة فقط.")

    # بعد الانتهاء من التاريخ نبقى فقط على الاستماع
    await _stop_event.wait()

    await client.disconnect()
    logger.info(f"Client stopped: {account_name}")


# ======================
# Collect History
# ======================

async def collect_old_messages(client: TelegramClient, account_name: str):
    """
    المرور على كل القنوات/الجروبات/الخاص وقراءة التاريخ
    """
    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        try:
            async for message in client.iter_messages(entity, reverse=True):
                if not _collecting:
                    return

                await process_message(
                    message=message,
                    account_name=account_name,
                    client=client
                )

        except Exception as e:
            logger.error(f"Error reading dialog {dialog.name}: {e}")


# ======================
# Helpers
# ======================

def _to_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _should_skip_whatsapp_by_date(message_date: datetime, platform: str) -> bool:
    """
    ✅ شرط واتساب:
    نجمع روابط واتساب فقط من آخر 60 يوم من وقت بدء الجمع
    """
    global _collect_started_at_utc

    if platform != "whatsapp":
        return False

    if not _collect_started_at_utc:
        return False

    msg_date_utc = _to_utc(message_date)
    cutoff = _collect_started_at_utc - timedelta(days=60)

    return msg_date_utc < cutoff


def _should_skip_tg_message_link(chat_id: int | None, platform: str) -> bool:
    """
    ✅ تيليجرام:
    اجمع رابط رسالة واحد فقط لكل مجموعة/قناة
    """
    if platform != "telegram_message":
        return False

    if chat_id is None:
        return False

    key = str(chat_id)
    if key in _collected_one_tg_message_link_per_chat:
        return True

    _collected_one_tg_message_link_per_chat.add(key)
    return False


# ======================
# Message Processing
# ======================

async def process_message(
    message: Message,
    account_name: str,
    client: TelegramClient,
):
    """
    استخراج الروابط من:
    - النص + المخفي + الأزرار
    - الملفات PDF/DOCX
    ثم حفظها بدون تكرار
    + إشعار فقط للروابط الجديدة بعد اكتمال جمع القديم
    """
    global _notifications_enabled

    if not message:
        return

    # ======================
    # 1) روابط النص + الأزرار
    # ======================
    links = extract_links_from_message(message)

    for link in links:
        classified = filter_and_classify_link(link)
        if not classified:
            continue

        platform, link_chat_type = classified

        # ✅ WhatsApp 60 days
        if _should_skip_whatsapp_by_date(message.date, platform):
            continue

        # ✅ only 1 TG message link per chat
        if _should_skip_tg_message_link(message.chat_id, platform):
            continue

        is_new = save_link(
            url=link,
            platform=platform,
            source_account=account_name,
            chat_type=link_chat_type,
            chat_id=str(message.chat_id),
            message_date=message.date
        )

        if is_new and _notifications_enabled:
            notify_admin_new_link(
                url=link,
                platform=platform,
                account_name=account_name,
                chat_type=link_chat_type,
                chat_id=str(message.chat_id),
                message_date=message.date
            )

    # ======================
    # 2) روابط الملفات
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

                if _should_skip_whatsapp_by_date(message.date, platform):
                    continue

                if _should_skip_tg_message_link(message.chat_id, platform):
                    continue

                is_new = save_link(
                    url=link,
                    platform=platform,
                    source_account=account_name,
                    chat_type=link_chat_type,
                    chat_id=str(message.chat_id),
                    message_date=message.date
                )

                if is_new and _notifications_enabled:
                    notify_admin_new_link(
                        url=link,
                        platform=platform,
                        account_name=account_name,
                        chat_type=link_chat_type,
                        chat_id=str(message.chat_id),
                        message_date=message.date
                    )

        except Exception as e:
            logger.error(f"File extraction error: {e}")
