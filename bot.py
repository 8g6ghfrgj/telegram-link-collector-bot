# bot.py
import os
import asyncio
import tempfile
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, ADMIN_ID, API_ID, API_HASH
from database import Database
from session_manager import (
    add_string_session,
    sessions_db,
    get_sessions_count,
)
from collector import start_collector
from link_utils import extract_links_from_text, classify_link
from file_extractors import extract_links_from_pdf, extract_links_from_docx

# =================================
db = Database()
collector_task = None

CATEGORIES = {
    "whatsapp": "📱 واتساب",
    "telegram": "✈️ تليجرام",
    "instagram": "📸 إنستغرام",
    "facebook": "📘 فيسبوك",
    "x": "🐦 X",
    "other": "📦 أخرى",
}

PAGE_SIZE = 30

# =================================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("👤 عرض الجلسات", callback_data="view_sessions")],
        [InlineKeyboardButton("🔗 تشغيل تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط المجمعة", callback_data="view_links")],
    ])


def back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back")]
    ])


# =================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 **بوت إدارة الجلسات وتجميع الروابط**\n\n"
        f"👤 الجلسات الحالية: {get_sessions_count()}\n"
        "اختر من القائمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )


# =================================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global collector_task

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    # رجوع
    if data == "back":
        await query.edit_message_text("القائمة الرئيسية:", reply_markup=main_keyboard())
        return

    # =============================
    # إضافة جلسة
    # =============================
    if data == "add_session":
        context.user_data["add_session"] = True
        await query.edit_message_text(
            "📤 أرسل **StringSession** أو ملف `.session`",
            reply_markup=back(),
            parse_mode="Markdown"
        )

    # =============================
    # عرض الجلسات
    # =============================
    elif data == "view_sessions":
        sessions = sessions_db.all()
        if not sessions:
            await query.edit_message_text("❌ لا توجد جلسات", reply_markup=back())
            return

        text = "👤 **الجلسات:**\n\n"
        buttons = []

        for phone, path in sessions:
            name = os.path.basename(path)
            text += f"• {phone} — `{name}`\n"
            buttons.append([
                InlineKeyboardButton(f"🗑 حذف {phone}", callback_data=f"del:{path}")
            ])

        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )

    elif data.startswith("del:"):
        path = data.split(":", 1)[1]
        if os.path.exists(path):
            os.remove(path)
        sessions_db.delete(path)
        await query.edit_message_text("✅ تم حذف الجلسة", reply_markup=back())

    # =============================
    # تشغيل التجميع
    # =============================
    elif data == "start_collect":
        if collector_task and not collector_task.done():
            await query.answer("⚠️ يعمل بالفعل", show_alert=True)
            return

        collector_task = asyncio.create_task(
            start_collector(API_ID, API_HASH)
        )

        await query.edit_message_text(
            "🟢 **تم تشغيل تجميع الروابط**\n\n"
            "• من كل الحسابات\n"
            "• بدون تكرار\n"
            "• يعمل في الخلفية",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )

    # =============================
    # عرض الروابط
    # =============================
    elif data == "view_links":
        buttons = [
            [InlineKeyboardButton(v, callback_data=f"cat:{k}")]
            for k, v in CATEGORIES.items()
        ]
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])
        await query.edit_message_text("اختر التصنيف:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("cat:"):
        cat = data.split(":")[1]
        years = db.get_years()

        buttons = [
            [InlineKeyboardButton(str(y), callback_data=f"year:{cat}:{y}:0")]
            for y in years
        ]
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="view_links")])

        await query.edit_message_text(
            f"{CATEGORIES[cat]} — اختر السنة",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("year:"):
        _, cat, year, offset = data.split(":")
        year, offset = int(year), int(offset)

        links = db.get_links_paginated(cat, year, PAGE_SIZE, offset)

        text = f"{CATEGORIES[cat]} — {year}\n\n"
        for i, l in enumerate(links, start=offset + 1):
            text += f"{i}. {l}\n"

        nav = []
        if offset > 0:
            nav.append(InlineKeyboardButton("⏮", callback_data=f"year:{cat}:{year}:{offset-PAGE_SIZE}"))
        if len(links) == PAGE_SIZE:
            nav.append(InlineKeyboardButton("⏭", callback_data=f"year:{cat}:{year}:{offset+PAGE_SIZE}"))

        kb = []
        if nav:
            kb.append(nav)
        kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"cat:{cat}")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))


# =================================
async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    urls = set()

    if msg.text:
        urls |= extract_links_from_text(msg.text)
    if msg.caption:
        urls |= extract_links_from_text(msg.caption)

    for ent in (msg.entities or []) + (msg.caption_entities or []):
        if ent.type == "text_link":
            urls.add(ent.url)

    if msg.reply_markup:
        for row in msg.reply_markup.inline_keyboard:
            for btn in row:
                if btn.url:
                    urls.add(btn.url)

    if msg.document:
        name = msg.document.file_name.lower()
        if msg.document.file_size <= 10 * 1024 * 1024:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                f = await context.bot.get_file(msg.document.file_id)
                await f.download_to_drive(tmp.name)

                if name.endswith(".pdf"):
                    urls |= extract_links_from_pdf(tmp.name)
                elif name.endswith(".docx"):
                    urls |= extract_links_from_docx(tmp.name)

                os.unlink(tmp.name)

    for url in urls:
        db.add_link(url, classify_link(url))


# =================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL, collect_links))

    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
