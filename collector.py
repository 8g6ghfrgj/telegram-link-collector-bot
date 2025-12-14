# collector.py
import asyncio
import re

from telethon import events
from session_manager import load_all_clients
from database import Database
from link_utils import extract_links_from_text, classify_link

db = Database()

URL_REGEX = re.compile(r"(https?://[^\s]+|t\.me/[^\s]+|wa\.me/[^\s]+)")

clients = []
running = False


async def start_collector(api_id=None, api_hash=None):
    global clients, running
    if running:
        return

    running = True
    clients = load_all_clients(api_id, api_hash)

    for client in clients:
        await client.start()

        @client.on(events.NewMessage)
        async def handler(event):
            text = event.raw_text or ""
            urls = set(extract_links_from_text(text))

            # روابط مخفية
            for ent in event.message.entities or []:
                if ent.url:
                    urls.add(ent.url)

            for url in urls:
                db.add_link(url, classify_link(url))

    await asyncio.gather(*(client.run_until_disconnected() for client in clients))


async def stop_collector():
    global clients, running
    running = False
    for client in clients:
        await client.disconnect()
    clients = []
