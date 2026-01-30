import asyncio
import logging
from typing import List
from datetime import datetime, timezone, timedelta

import urllib.parse
import urllib.request

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

# وقت بدء الجمع
_collect_started_at_utc: datetime | None = None

# لمنع جمع أكثر من رابط رسالة تيليجرام لكل مجموعة
_collected_one_tg_message_link_per_chat: set[str] = set()

# الإشعارات بعد انتهاء التاريخ
_notifications_enabled: bool = False

# Counters
_history_total_clients: int = 0
_history_finished_clients: int = 0
_history_lock = asyncio.Lock()

# ✅ المنصة المختارة من الأزرار
_selected_platform: str | None = None


# ======================
# Public API
# ======================

def is_collecting() -> bool:
    return _collecting


def stop_collection():
    global _collecting
    _collecting = False
    _stop_event.set()
    logger.info("Collection stopped.")


async def start_collection(platform: str | None = None):
    global _collecting, _clients, _collect_started_at_utc
    global _notifications_enabled
    global _history_total_clients, _history_finished_clients
    global _selected_platform

    if _collecting:
        return

    sessions = get_all_sessions()
    if not sessions:
        return

    _selected_platform = platform

    _collect_started_at_utc = datetime.now(timezone.utc)

    _collected_one_tg_message_link_per_chat.clear()
    _notifications_enabled = False

    _history_total_clients = len(sessions)
    _history_finished_clients = 0

    _collecting = True
    _stop_event.clear()
    _clients = []

    tasks = [run_client(session) for session in sessions]
    await asyncio.gather(*tasks)


# ======================
# Notifications
# ======================

def _safe_send_admin_message(text: str):
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()

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
            dt = _to_utc(message_date).strftime("%Y-%m-%d %H:%M UTC")

        text = (
            "✅ رابط جديد\n\n"
            f"🔗 {url}\n\n"
            f"📌 المنصة: {platform}\n"
            f"💬 النوع: {chat_type}\n"
            f"👤 الحساب: {account_name}\n"
            f"🆔 chat_id: {chat_id}\n"
        )

        if dt:
            text += f"🕒 {dt}"

        _safe_send_admin_message(text)

    except Exception:
        pass


# ======================
# Client Runner
# ======================

async def run_client(session_data: dict):
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

    @client.on(events.NewMessage)
    async def new_message_handler(event):
        if not _collecting:
            return

        await process_message(
            message=event.message,
            account_name=account_name,
            client=client
        )

    await collect_old_messages(client, account_name)
    await _mark_history_finished(account_name)

    await _stop_event.wait()
    await client.disconnect()


async def _mark_history_finished(account_name: str):
    global _history_finished_clients, _notifications_enabled

    async with _history_lock:
        _history_finished_clients += 1

        if (_history_finished_clients >= _history_total_clients) and not _notifications_enabled:
            _notifications_enabled = True
            _safe_send_admin_message(
                "✅ انتهى جمع الروابط القديمة من جميع الحسابات."
            )


# ======================
# Collect History
# ======================

async def collect_old_messages(client: TelegramClient, account_name: str):
    async for dialog in client.iter_dialogs():
        try:
            async for message in client.iter_messages(dialog.entity, reverse=True):
                if not _collecting:
                    return

                await process_message(
                    message=message,
                    account_name=account_name,
                    client=client
                )

        except Exception as e:
            logger.error(f"Dialog error {dialog.name}: {e}")


# ======================
# Helpers
# ======================

def _to_utc(dt: datetime) -> datetime:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _should_skip_whatsapp_by_date(message_date: datetime, platform: str) -> bool:
    if platform != "whatsapp":
        return False

    if not _collect_started_at_utc:
        return False

    msg_date_utc = _to_utc(message_date)
    cutoff = _collect_started_at_utc - timedelta(days=60)

    return msg_date_utc < cutoff


def _should_skip_files_by_date(message_date: datetime) -> bool:
    if not _collect_started_at_utc or not message_date:
        return False

    msg_date_utc = _to_utc(message_date)
    cutoff = _collect_started_at_utc - timedelta(days=60)

    return msg_date_utc < cutoff


def _should_skip_tg_message_link(chat_id: int | None, platform: str) -> bool:
    if platform != "telegram":
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
    global _notifications_enabled

    if not message:
        return

    # ========= Text links =========

    links = extract_links_from_message(message)

    for link in links:
        classified = filter_and_classify_link(link)
        if not classified:
            continue

        platform, link_chat_type = classified

        # ✅ السماح فقط واتساب وتيليجرام
        if platform not in ("whatsapp", "telegram"):
            continue

        # ✅ فلترة حسب زر الاختيار
        if _selected_platform and platform != _selected_platform:
            continue

        # قيود التاريخ
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

    # ========= Files =========

    if message.file:

        if _should_skip_files_by_date(message.date):
            return

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

                # ✅ فقط واتساب وتيليجرام
                if platform not in ("whatsapp", "telegram"):
                    continue

                # ✅ حسب الزر
                if _selected_platform and platform != _selected_platform:
                    continue

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
