# bot.py
import os
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

# ==================================================
# تهيئة قاعدة البيانات
# ==================================================
db = Database()

# ==================================================
# التصنيفات
# ==================================================
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
# لوحات المفاتيح
# ==================================================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 عرض الروابط", callback_data="view_links")],
    ])


def back_keyboard(callback="back"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data=callback)]
    ])

# ==================================================
# /start
# ==================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 **بوت تجميع الروابط**\n\n"
        "• يجمع كل الروابط تلقائياً بدون أي استثناء\n"
        "• من الرسائل، الأزرار، PDF، Word\n"
        "• بدون تكرار\n\n"
        "اختر من القائمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ==================================================
# Callback Queries (الواجهة)
# ==================================================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    # --------------------------
    # رجوع للقائمة الرئيسية
    # --------------------------
    if data == "back":
        await query.edit_message_text(
            "القائمة الرئيسية:",
            reply_markup=main_keyboard()
        )

    # --------------------------
    # عرض التصنيفات
    # --------------------------
    elif data == "view_links":
        buttons = [
            [InlineKeyboardButton(name, callback_data=f"cat:{key}")]
            for key, name in CATEGORIES.items()
        ]
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])

        await query.edit_message_text(
            "اختر نوع الروابط:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # --------------------------
    # عرض السنوات
    # --------------------------
    elif data.startswith("cat:"):
        category = data.split(":")[1]
        years = db.get_years()

        if not years:
            await query.answer("لا توجد روابط بعد", show_alert=True)
            return

        buttons = [
            [InlineKeyboardButton(str(y), callback_data=f"year:{category}:{y}:0")]
            for y in years
        ]
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="view_links")])

        await query.edit_message_text(
            f"اختر السنة ({CATEGORIES[category]}):",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # --------------------------
    # عرض الروابط مع Pagination
    # --------------------------
    elif data.startswith("year:"):
        _, category, year, offset = data.split(":")
        year = int(year)
        offset = int(offset)

        links = db.get_links_paginated(
            category=category,
            year=year,
            limit=PAGE_SIZE,
            offset=offset
        )

        if not links:
            await query.answer("لا توجد روابط", show_alert=True)
            return

        text = f"{CATEGORIES[category]} — {year}\n\n"
        for i, link in enumerate(links, start=offset + 1):
            text += f"{i}. {link}\n"

        nav_buttons = []
        if offset > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    "⏮ السابق",
                    callback_data=f"year:{category}:{year}:{offset-PAGE_SIZE}"
                )
            )
        if len(links) == PAGE_SIZE:
            nav_buttons.append(
                InlineKeyboardButton(
                    "⏭ التالي",
                    callback_data=f"year:{category}:{year}:{offset+PAGE_SIZE}"
                )
            )

        keyboard = []
        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"cat:{category}")
        ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ==================================================
# جامع الروابط (تلقائي دائماً)
# ==================================================
async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    urls = set()

    # --------------------------
    # النص والكابتشن
    # --------------------------
    if message.text:
        urls.update(extract_links_from_text(message.text))

    if message.caption:
        urls.update(extract_links_from_text(message.caption))

    # --------------------------
    # الروابط المخفية (Entities)
    # --------------------------
    if message.entities:
        for ent in message.entities:
            if ent.type == "text_link":
                urls.add(ent.url)

    if message.caption_entities:
        for ent in message.caption_entities:
            if ent.type == "text_link":
                urls.add(ent.url)

    # --------------------------
    # أزرار Inline
    # --------------------------
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.url:
                    urls.add(btn.url)

    # --------------------------
    # ملفات PDF و Word
    # --------------------------
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

    # --------------------------
    # حفظ الروابط بدون تكرار
    # --------------------------
    for url in urls:
        category = classify_link(url)
        db.add_link(url, category)

# ==================================================
# تشغيل البوت
# ==================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL, collect_links))

    print("🚀 Bot is running and collecting links...")
    app.run_polling()


if __name__ == "__main__":
    main()
