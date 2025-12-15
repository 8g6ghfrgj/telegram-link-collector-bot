import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from config import API_ID, API_HASH
from session_manager import get_all_sessions
from database import save_link
from link_utils import extract_links_from_message
from file_extractors import extract_links_from_file

_clients = []
_collecting = False
_stop_event = asyncio.Event()


def is_collecting():
    return _collecting


def stop_collection():
    global _collecting
    _collecting = False
    _stop_event.set()


async def start_collection():
    global _collecting
    _collecting = True
    _stop_event.clear()
    sessions = get_all_sessions()
    tasks = [run_client(s) for s in sessions]
    await asyncio.gather(*tasks)


async def run_client(session):
    client = TelegramClient(
        StringSession(session["session"]),
        API_ID,
        API_HASH
    )
    await client.start()

    @client.on(events.NewMessage)
    async def handler(event):
        if not _collecting:
            return
        await process_message(client, event.message, session["name"])

    async for dialog in client.iter_dialogs():
        async for msg in client.iter_messages(dialog.entity, reverse=True):
            if not _collecting:
                return
            await process_message(client, msg, session["name"])

    await _stop_event.wait()
    await client.disconnect()


async def process_message(client, message, account):
    links = extract_links_from_message(message)
    for link in links:
        save_link(link, None, account, "unknown", str(message.chat_id), message.date)

    if message.file:
        file_links = await extract_links_from_file(client, message)
        for link in file_links:
            save_link(link, None, account, "unknown", str(message.chat_id), message.date)
