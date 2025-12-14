# bot.py
import asyncio
import os
import re
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

from config import BOT_TOKEN, ADMIN_ID
from database import Database
from link_utils import extract_links_from_text, classify_link
from file_extractors import (
    extract_links_from_pdf,
    extract_links_from_docx,
)

# =========================
# تهيئة
# =========================
db = Database()

URL_REGEX = re.compile(r"(https?://[^\s]+|t\.me/[^\s]+|wa\.me/[^\s]+)")

# =========================
# واجهات
# =========================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 تجميع الروابط", callback_data="collect_links")],
        [InlineKeyboardButton("📊 عرض الروابط (قريباً)", callback_data="noop")],
    ])


# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 **بوت تجميع الروابط**\n\n"
        "البوت يعمل تلقائياً ويجمع كل الروابط بدون استثناء.\n\n"
        "اختر من القائمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )


# =========================
# أزرار
# =========================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if query.data == "collect_links":
        await query.edit_message_text(
            "✅ **التجميع يعمل تلقائياً**\n\n"
            "لا تحتاج لأي إجراء.\n"
            "أي رابط يتم نشره سيتم حفظه تلقائياً.",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )

    elif query.data == "noop":
        await query.answer("واجهة العرض ستكون في المرحلة 2", show_alert=True)


# =========================
# جامع الروابط (المرحلة 1)
# =========================
async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    urls = set()

    # ----------------------
    # 1️⃣ نص الرسائل
    # ----------------------
    if message.text:
        urls.update(extract_links_from_text(message.text))

    if message.caption:
        urls.update(extract_links_from_text(message.caption))

    # ----------------------
    # 2️⃣ Entities (روابط مخفية)
    # ----------------------
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_link":
                urls.add(ent.url)

    if message.caption_entities:
        for ent in message.caption_entities:
            if ent.type == "text_link":
                urls.add(ent.url)

    # ----------------------
    # 3️⃣ أزرار Inline
    # ----------------------
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.url:
                    urls.add(btn.url)

    # ----------------------
    # 4️⃣ ملفات PDF / Word
    # ----------------------
    if message.document:
        file_name = message.document.file_name.lower()
        file_size = message.document.file_size or 0

        # حد أمان 10MB
        if file_size <= 10 * 1024 * 1024:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tg_file = await context.bot.get_file(message.document.file_id)
                await tg_file.download_to_drive(tmp.name)

                if file_name.endswith(".pdf"):
                    urls.update(extract_links_from_pdf(tmp.name))

                elif file_name.endswith(".docx"):
                    urls.update(extract_links_from_docx(tmp.name))

                os.unlink(tmp.name)

    # ----------------------
    # حفظ الروابط بدون تكرار
    # ----------------------
    for url in urls:
        category = classify_link(url)
        db.add_link(url, category)


# =========================
# تشغيل البوت
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL, collect_links))

    print("🚀 Bot is running and collecting links...")
    app.run_polling()


if __name__ == "__main__":
    main()
