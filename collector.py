# collector.py
import asyncio
from telethon import events

from session_manager import load_all_clients
from database import Database
from link_utils import extract_links_from_text, classify_link

db = Database()

_clients = []
_running = False


async def start_collector(api_id: int, api_hash: str):
    global _clients, _running

    if _running:
        return

    _running = True
    _clients = load_all_clients(api_id, api_hash)

    for client in _clients:
        await client.start()

        @client.on(events.NewMessage)
        async def handler(event):
            text = event.raw_text or ""
            urls = set(extract_links_from_text(text))

            for ent in event.message.entities or []:
                if ent.url:
                    urls.add(ent.url)

            for url in urls:
                db.add_link(url, classify_link(url))

    await asyncio.gather(
        *[client.run_until_disconnected() for client in _clients]
    )
