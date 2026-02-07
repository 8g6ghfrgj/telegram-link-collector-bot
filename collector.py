import asyncio
import logging
from typing import List
from datetime import datetime, timezone, timedelta

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Message

from config import API_ID, API_HASH
from session_manager import get_all_sessions
from database import get_admin_target
from link_utils import extract_links_from_message, filter_and_classify_link
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
_selected_platform: str | None = None
_collect_started_at_utc: datetime | None = None

# لمنع أكثر من رابط رسالة تيليجرام لكل شات
_collected_one_tg_message_link_per_chat: set[str] = set()


# ======================
# Public API
# ======================

def is_collecting() -> bool:
    return _collecting


def stop_collection():
    global _collecting
    _collecting = False
    _stop_event.set()
    logger.info("Collection stopped")


async def start_collection(platform: str | None = None):
    global _collecting, _clients, _selected_platform, _collect_started_at_utc

    if _collecting:
        return

    sessions = get_all_sessions()
    if not sessions:
        return

    _selected_platform = platform
    _collect_started_at_utc = datetime.now(timezone.utc)

    _collecting = True
    _stop_event.clear()
    _clients = []
    _collected_one_tg_message_link_per_chat.clear()

    tasks = [run_client(session) for session in sessions]
    await asyncio.gather(*tasks)


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
        await process_message(event.message, client)

    async for dialog in client.iter_dialogs():
        try:
            async for message in client.iter_messages(dialog.entity, reverse=True):
                if not _collecting:
                    return
                await process_message(message, client)
        except Exception as e:
            logger.error(f"Dialog error: {e}")

    await _stop_event.wait()
    await client.disconnect()


# ======================
# Helpers
# ======================

def _to_utc(dt: datetime) -> datetime:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _skip_old_messages(message_date: datetime) -> bool:
    if not _collect_started_at_utc or not message_date:
        return False

    return _to_utc(message_date) < (_collect_started_at_utc - timedelta(days=60))


def _should_skip_tg_message_link(chat_id: int | None, platform: str) -> bool:
    if platform != "telegram" or not chat_id:
        return False

    key = str(chat_id)
    if key in _collected_one_tg_message_link_per_chat:
        return True

    _collected_one_tg_message_link_per_chat.add(key)
    return False


async def _link_exists_in_channel(client: TelegramClient, chat: str, link: str) -> bool:
    """
    فحص التكرار من آخر 200 رسالة في القناة
    """
    try:
        async for msg in client.iter_messages(chat, limit=200):
            if msg.text and link in msg.text:
                return True
    except Exception:
        pass

    return False


async def _send_unique_link(
    client: TelegramClient,
    target_chat: str,
    link: str
):
    if not await _link_exists_in_channel(client, target_chat, link):
        await client.send_message(target_chat, link)
        return True
    return False


# ======================
# Message Processing
# ======================

async def process_message(message: Message, client: TelegramClient):
    if not message:
        return

    # ========= Text =========
    links = extract_links_from_message(message)

    for link in links:
        await _handle_link(link, message, client)

    # ========= Files =========
    if message.file:
        if _skip_old_messages(message.date):
            return

        try:
            file_links = await extract_links_from_file(client, message)
            for link in file_links:
                await _handle_link(link, message, client)
        except Exception as e:
            logger.error(f"File extract error: {e}")


async def _handle_link(link: str, message: Message, client: TelegramClient):
    classified = filter_and_classify_link(link)
    if not classified:
        return

    platform, _ = classified

    # فقط واتساب / تليجرام
    if platform not in ("whatsapp", "telegram"):
        return

    # حسب اختيار الزر
    if _selected_platform and platform != _selected_platform:
        return

    if _skip_old_messages(message.date):
        return

    if _should_skip_tg_message_link(message.chat_id, platform):
        return

    # 🔑 تحديد المشرف (مالك الجلسة)
    me = await client.get_me()
    admin_id = me.id

    target_chat = get_admin_target(admin_id, platform)
    if not target_chat:
        return  # لم يتم تعيين قناة

    await _send_unique_link(client, target_chat, link)
