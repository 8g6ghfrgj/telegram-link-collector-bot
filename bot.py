# bot.py
import os
import tempfile

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, ADMIN_ID
from database import Database
from link_utils import extract_links_from_text, classify_link
from file_extractors import extract_links_from_pdf, extract_links_from_docx

# ==================================================
db = Database()

CATEGORIES = {
    "whatsapp": "📱 واتساب",
    "telegram": "✈️ تليجرام",
    "instagram": "📸 إنستغرام",
    "facebook": "📘 فيسبوك",
    "x": "🐦 X",
    "other": "📦 أخرى",
}

PAGE_SIZE = 30

# ==================================================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 عرض الروابط", callback_data="view_links")],
        [InlineKeyboardButton("🔍 بحث", callback_data="search")],
    ])

# ==================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 **بوت أرشفة الروابط**\n\n"
        "• تجميع تلقائي\n"
        "• عرض – بحث – تصدير\n\n"
        "اختر:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ==================================================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID:
        return

    d = q.data

    if d == "back":
        await q.edit_message_text("القائمة:", reply_markup=main_keyboard())

    elif d == "view_links":
        kb = [[InlineKeyboardButton(v, callback_data=f"cat:{k}")]
              for k, v in CATEGORIES.items()]
        kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])
        await q.edit_message_text("اختر النوع:", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("cat:"):
        cat = d.split(":")[1]
        years = db.get_years()
        kb = [[InlineKeyboardButton(str(y), callback_data=f"year:{cat}:{y}:0")] for y in years]
        kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data="view_links")])
        await q.edit_message_text("اختر السنة:", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("year:"):
        _, cat, year, offset = d.split(":")
        year, offset = int(year), int(offset)

        total = db.count_links(cat, year)
        links = db.get_links_paginated(cat, year, PAGE_SIZE, offset)

        text = f"{CATEGORIES[cat]} — {year}\n"
        text += f"عرض {min(offset+PAGE_SIZE, total)} من {total}\n\n"

        for i, l in enumerate(links, start=offset+1):
            text += f"{i}. {l}\n"

        nav = []
        if offset > 0:
            nav.append(InlineKeyboardButton("⏮", callback_data=f"year:{cat}:{year}:{offset-PAGE_SIZE}"))
        if offset + PAGE_SIZE < total:
            nav.append(InlineKeyboardButton("⏭", callback_data=f"year:{cat}:{year}:{offset+PAGE_SIZE}"))

        kb = []
        if nav:
            kb.append(nav)

        kb.append([
            InlineKeyboardButton("📤 تصدير", callback_data=f"export:{cat}:{year}"),
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"cat:{cat}")
        ])

        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("export:"):
        _, cat, year = d.split(":")
        year = int(year)

        links = db.export_links(cat, year)

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as f:
            for l in links:
                f.write(l + "\n")

        await q.message.reply_document(
            document=InputFile(f.name),
            caption=f"📤 تصدير {CATEGORIES[cat]} — {year}"
        )
        os.unlink(f.name)

    elif d == "search":
        context.user_data["search"] = True
        await q.edit_message_text("✍️ أرسل كلمة البحث:")

# ==================================================
async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("search"):
        return

    keyword = update.message.text
    context.user_data["search"] = False

    results = db.search_links(keyword)

    if not results:
        await update.message.reply_text("❌ لا نتائج")
        return

    text = f"🔍 نتائج البحث ({len(results)}):\n\n"
    for i, r in enumerate(results, 1):
        text += f"{i}. {r}\n"

    await update.message.reply_text(text)

# ==================================================
async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    urls = set()

    if msg.text:
        urls.update(extract_links_from_text(msg.text))
    if msg.caption:
        urls.update(extract_links_from_text(msg.caption))

    for e in (msg.entities or []):
        if e.type == "text_link":
            urls.add(e.url)
    for e in (msg.caption_entities or []):
        if e.type == "text_link":
            urls.add(e.url)

    if msg.reply_markup:
        for row in msg.reply_markup.inline_keyboard:
            for b in row:
                if b.url:
                    urls.add(b.url)

    if msg.document:
        name = msg.document.file_name.lower()
        if msg.document.file_size <= 10 * 1024 * 1024:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                f = await context.bot.get_file(msg.document.file_id)
                await f.download_to_drive(tmp.name)
                if name.endswith(".pdf"):
                    urls.update(extract_links_from_pdf(tmp.name))
                elif name.endswith(".docx"):
                    urls.update(extract_links_from_docx(tmp.name))
                os.unlink(tmp.name)

    for u in urls:
        db.add_link(u, classify_link(u))

# ==================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))
    app.add_handler(MessageHandler(filters.ALL, collect_links))

    print("🚀 Bot fully ready (Stage 3)")
    app.run_polling()


if __name__ == "__main__":
    main()
