# collector.py
import asyncio
from telethon import events
from telethon.tl.functions.messages import GetHistoryRequest

from session_manager import load_all_clients
from database import Database
from link_utils import extract_links_from_text, classify_link

db = Database()

# عدد الرسائل التي تُجلب في كل دفعة (آمن)
HISTORY_LIMIT = 100


async def collect_old_messages(client):
    """
    يجمع كل الروابط القديمة من:
    - القنوات
    - الجروبات
    - السوبر جروب
    """
    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        # نتجاهل البوتات
        if getattr(entity, "bot", False):
            continue

        offset_id = 0

        while True:
            history = await client(GetHistoryRequest(
                peer=entity,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=HISTORY_LIMIT,
                max_id=0,
                min_id=0,
                hash=0
            ))

            if not history.messages:
                break

            for msg in history.messages:
                if not msg.message:
                    continue

                urls = set(extract_links_from_text(msg.message))

                for ent in msg.entities or []:
                    if ent.url:
                        urls.add(ent.url)

                for url in urls:
                    db.add_link(url, classify_link(url))

            offset_id = history.messages[-1].id


async def start_realtime_listener(client):
    """
    يستمع للرسائل الجديدة فقط
    """
    @client.on(events.NewMessage)
    async def handler(event):
        text = event.raw_text or ""
        urls = set(extract_links_from_text(text))

        for ent in event.message.entities or []:
            if ent.url:
                urls.add(ent.url)

        for url in urls:
            db.add_link(url, classify_link(url))


async def start_collector(api_id, api_hash):
    """
    المحرك الرئيسي:
    - يشغّل كل الجلسات
    - يجمع القديم
    - ثم يستمع للجديد
    """
    clients = load_all_clients(api_id, api_hash)

    if not clients:
        print("❌ لا توجد جلسات")
        return

    # تشغيل كل الجلسات
    for client in clients:
        await client.start()

    print(f"✅ تم تشغيل {len(clients)} جلسة")

    # 1️⃣ جمع الروابط القديمة
    for client in clients:
        print("📦 جمع الروابط القديمة...")
        try:
            await collect_old_messages(client)
        except Exception as e:
            print(f"⚠️ خطأ أثناء جمع القديم: {e}")

    print("✅ انتهى جمع الروابط القديمة")

    # 2️⃣ الاستماع للروابط الجديدة
    for client in clients:
        await start_realtime_listener(client)

    print("🟢 بدأ الاستماع للرسائل الجديدة")

    # إبقاء الجلسات تعمل
    await asyncio.gather(
        *(client.run_until_disconnected() for client in clients)
    )
