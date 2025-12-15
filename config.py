import asyncio
import logging
from typing import List

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Message

from config import API_ID, API_HASH
from session_manager import get_all_sessions
from database import save_link
from link_utils import extract_links_from_message
from file_extractors import extract_links_from_file

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
    global _collecting
    _collecting = False
    _stop_event.set()
    logger.info("Collection stopped (listening only).")


async def start_collection():
    global _collecting, _clients
    if _collecting:
        return

    _collecting = True
    _stop_event.clear()
    _clients = []

    sessions = get_all_sessions()
    if not sessions:
        logger.warning("No sessions available.")
        _collecting = False
        return

    tasks = []
    for session in sessions:
        tasks.append(run_client(session))

    await asyncio.gather(*tasks)
    logger.info("Finished collecting old history.")
    # بعد الانتهاء من التاريخ القديم نبقى فقط على الاستماع


# ======================
# Client Runner
# ======================

async def run_client(session_data: dict):
    session_string = session_data["session"]
    account_name = session_data["name"]

    client = TelegramClient(
        StringSession(session_string),
        API_ID,
        API_HASH,
    )

    await client.connect()
    _clients.append(client)

    logger.info(f"Client started: {account_name}")

    # استماع للرسائل الجديدة
    @client.on(events.NewMessage)
    async def handler(event):
        if not _collecting:
            return
        await process_message(
            event.message,
            account_name,
            client
        )

    # قراءة كل الرسائل القديمة
    await collect_old_messages(client, account_name)

    # إبقاء الاتصال مفتوح للاستماع
    await _stop_event.wait()
    await client.disconnect()


# ======================
# Collect History
# ======================

async def collect_old_messages(client: TelegramClient, account_name: str):
    async for dialog in client.iter_dialogs():
        try:
            entity = dialog.entity
            chat_type = get_chat_type(entity)

            async for message in client.iter_messages(entity, reverse=True):
                if not _collecting:
                    return

                await process_message(
                    message,
                    account_name,
                    client,
                    chat_type_override=chat_type
                )

        except Exception as e:
            logger.error(f"Error reading dialog: {e}")


# ======================
# Message Processing
# ======================

async def process_message(
    message: Message,
    account_name: str,
    client: TelegramClient,
    chat_type_override: str | None = None
):
    if not message:
        return

    chat = await message.get_chat()
    chat_type = chat_type_override or get_chat_type(chat)

    # 1️⃣ استخراج الروابط من النص + الأزرار
    links = extract_links_from_message(message)

    for link in links:
        save_link(
            url=link,
            platform=None,
            source_account=account_name,
            chat_type=chat_type,
            chat_id=str(message.chat_id),
            message_date=message.date
        )

    # 2️⃣ استخراج الروابط من الملفات (PDF / DOCX)
    if message.file:
        try:
            file_links = await extract_links_from_file(
                client=client,
                message=message
            )
            for link in file_links:
                save_link(
                    url=link,
                    platform=None,
                    source_account=account_name,
                    chat_type=chat_type,
                    chat_id=str(message.chat_id),
                    message_date=message.date
                )
        except Exception as e:
            logger.error(f"File extraction error: {e}")


# ======================
# Helpers
# ======================

def get_chat_type(entity) -> str:
    cls = entity.__class__.__name__.lower()
    if "channel" in cls:
        return "channel"
    if "chat" in cls:
        return "group"
    return "private"
