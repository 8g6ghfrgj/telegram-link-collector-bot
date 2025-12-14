# bot.py
import os
import tempfile

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
from sessions_db import SessionsDB
from session_manager import save_uploaded_session

from link_utils import extract_links_from_text, classify_link
from file_extractors import extract_links_from_pdf, extract_links_from_docx

# ==================================================
# قواعد البيانات
# ==================================================
db = Database()
sessions_db = SessionsDB()

# ==================================================
# إعدادات
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
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("👤 عرض الجلسات", callback_data="list_sessions")],
        [InlineKeyboardButton("🔗 تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط المجمعة", callback_data="view_links")],
    ])


def back_keyboard(cb="back"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data=cb)]
    ])

# ==================================================
# /start
# ==================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 **بوت إدارة الجلسات وتجميع الروابط**\n\n"
        "اختر من القائمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ==================================================
# Callbacks (الأزرار)
# ==================================================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    # ------------------ رجوع ------------------
    if data == "back":
        await query.edit_message_text(
            "القائمة الرئيسية:",
            reply_markup=main_keyboard()
        )

    # ------------------ إضافة جلسة ------------------
    elif data == "add_session":
        kb = [
            [InlineKeyboardButton("📂 رفع جلسة Telethon", callback_data="upload_session")],
            [InlineKeyboardButton("📱 إدخال رقم (قريباً)", callback_data="otp_disabled")],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back")]
        ]
        await query.edit_message_text(
            "اختر طريقة إضافة الجلسة:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data == "otp_disabled":
        await query.answer(
            "تسجيل الرقم يتطلب API_ID و API_HASH",
            show_alert=True
        )

    # ------------------ عرض الجلسات ------------------
    elif data == "list_sessions":
        sessions = sessions_db.get_sessions()

        if not sessions:
            await query.edit_message_text(
                "❌ لا توجد جلسات مضافة.",
                reply_markup=main_keyboard()
            )
            return

        text = "👤 **الجلسات المضافة:**\n\n"
        for i, (phone, name) in enumerate(sessions, 1):
            text += f"{i}. `{name}` ({phone})\n"

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    # ------------------ تجميع الروابط ------------------
    elif data == "start_collect":
        await query.edit_message_text(
            "🔗 **تجميع الروابط يعمل تلقائياً**\n\n"
            "أي رابط يظهر في الحسابات سيتم حفظه بدون تكرار.",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )

    # ------------------ عرض الروابط ------------------
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

    elif data.startswith("year:"):
        _, category, year, offset = data.split(":")
        year = int(year)
        offset = int(offset)

        total = db.count_links(category, year)
        links = db.get_links_paginated(category, year, PAGE_SIZE, offset)

        if not links:
            await query.answer("لا توجد روابط", show_alert=True)
            return

        text = (
            f"{CATEGORIES[category]} — {year}\n"
            f"عرض {min(offset + PAGE_SIZE, total)} من {total} رابط\n\n"
        )

        for i, link in enumerate(links, start=offset + 1):
            text += f"{i}. {link}\n"

        nav = []
        if offset > 0:
            nav.append(
                InlineKeyboardButton(
                    "⏮ السابق",
                    callback_data=f"year:{category}:{year}:{offset-PAGE_SIZE}"
                )
            )
        if offset + PAGE_SIZE < total:
            nav.append(
                InlineKeyboardButton(
                    "⏭ التالي",
                    callback_data=f"year:{category}:{year}:{offset+PAGE_SIZE}"
                )
            )

        keyboard = []
        if nav:
            keyboard.append(nav)

        keyboard.append([
            InlineKeyboardButton("⬅️ رجوع", callback_data=f"cat:{category}")
        ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ==================================================
# رفع جلسة Telethon
# ==================================================
async def handle_session_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.document:
        return

    doc = update.message.document
    if not doc.file_name.endswith(".session"):
        await update.message.reply_text("❌ أرسل ملف .session فقط")
        return

    tg_file = await context.bot.get_file(doc.file_id)
    temp_path = os.path.join(tempfile.gettempdir(), doc.file_name)
    await tg_file.download_to_drive(temp_path)

    name = save_uploaded_session(temp_path, doc.file_name)
    await update.message.reply_text(f"✅ تم إضافة الجلسة: `{name}`", parse_mode="Markdown")

# ==================================================
# جامع الروابط (من البوت نفسه حالياً)
# ==================================================
async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    urls = set()

    if message.text:
        urls.update(extract_links_from_text(message.text))
    if message.caption:
        urls.update(extract_links_from_text(message.caption))

    for ent in (message.entities or []):
        if ent.type == "text_link":
            urls.add(ent.url)
    for ent in (message.caption_entities or []):
        if ent.type == "text_link":
            urls.add(ent.url)

    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.url:
                    urls.add(btn.url)

    if message.document:
        name = message.document.file_name.lower()
        size = message.document.file_size or 0

        if size <= 10 * 1024 * 1024:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                f = await context.bot.get_file(message.document.file_id)
                await f.download_to_drive(tmp.name)

                if name.endswith(".pdf"):
                    urls.update(extract_links_from_pdf(tmp.name))
                elif name.endswith(".docx"):
                    urls.update(extract_links_from_docx(tmp.name))

                os.unlink(tmp.name)

    for url in urls:
        db.add_link(url, classify_link(url))

# ==================================================
# تشغيل البوت
# ==================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_session_upload))
    app.add_handler(MessageHandler(filters.ALL, collect_links))

    print("🚀 Bot is running with sessions + link collection")
    app.run_polling()


if __name__ == "__main__":
    main()
