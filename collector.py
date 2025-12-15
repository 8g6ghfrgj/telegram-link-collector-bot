# collector.py
import asyncio
from telethon import events
from telethon.tl.types import MessageEntityTextUrl
from session_manager import load_all_clients
from link_utils import extract_links_from_text, classify_link
from database import Database

db = Database()

# ===============================
# استخراج الروابط من رسالة واحدة
# ===============================
def extract_links_from_message(message):
    urls = set()

    # نص الرسالة
    if message.text:
        urls.update(extract_links_from_text(message.text))

    # روابط مخفية (text_url)
    if message.entities:
        for ent in message.entities:
            if isinstance(ent, MessageEntityTextUrl):
                urls.add(ent.url)

    return urls


# ===============================
# جمع كل الرسائل القديمة
# ===============================
async def collect_history(client):
    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        # نتجاهل البوتات
        if getattr(entity, "bot", False):
            continue

        try:
            async for message in client.iter_messages(entity, limit=None):
                urls = extract_links_from_message(message)
                for url in urls:
                    db.add_link(url, classify_link(url))
        except Exception:
            # أي قناة مغلقة أو خطأ يتم تجاوزها
            continue


# ===============================
# الاستماع للرسائل الجديدة
# ===============================
def attach_realtime_handler(client):
    @client.on(events.NewMessage)
    async def handler(event):
        urls = extract_links_from_message(event.message)
        for url in urls:
            db.add_link(url, classify_link(url))


# ===============================
# تشغيل الجامع الكامل
# ===============================
async def start_collector(api_id, api_hash):
    clients = load_all_clients(api_id, api_hash)

    if not clients:
        print("❌ لا توجد جلسات Telethon")
        return

    # تشغيل كل الجلسات
    for client in clients:
        await client.start()
        attach_realtime_handler(client)

    print("🔄 بدء جمع الروابط القديمة...")
    for client in clients:
        await collect_history(client)

    print("🟢 تم جمع كل الروابط القديمة")
    print("📡 الاستماع للروابط الجديدة الآن...")

    # إبقاء الجلسات شغالة
    await asyncio.gather(
        *(client.run_until_disconnected() for client in clients)
    )
