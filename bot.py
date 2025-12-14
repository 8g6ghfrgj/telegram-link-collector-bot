# bot.py
import os
import asyncio
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
from session_manager import (
    save_uploaded_session,
    sessions_db,
    get_sessions_count,
    load_all_clients,
)
from collector import start_collector
from link_utils import extract_links_from_text, classify_link
from file_extractors import extract_links_from_pdf, extract_links_from_docx

# ==================================================
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

# ==================================================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("👤 عرض الجلسات", callback_data="view_sessions")],
        [InlineKeyboardButton("🔗 تشغيل تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط المجمعة", callback_data="view_links")],
    ])


# ==================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 **بوت إدارة الجلسات وتجميع الروابط**\n\n"
        f"👤 عدد الجلسات: {get_sessions_count()}\n\n"
        "اختر من القائمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )


# ==================================================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global collector_task

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    # رجوع
    if data == "back":
        await query.edit_message_text(
            "القائمة الرئيسية:",
            reply_markup=main_keyboard()
        )

    # إضافة جلسة
    elif data == "add_session":
        await query.edit_message_text(
            "📤 أرسل الآن ملف **.session**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )

    # عرض الجلسات
    elif data == "view_sessions":
        sessions = sessions_db.all()

        if not sessions:
            await query.edit_message_text(
                "❌ لا توجد جلسات مضافة.",
                reply_markup=main_keyboard()
            )
            return

        text = "👤 **الجلسات المضافة:**\n\n"
        for i, name in enumerate(sessions, 1):
            text += f"{i}. `{name}`\n"

        await query.edit_message_text(
            text,
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )

    # تشغيل التجميع
    elif data == "start_collect":
        if collector_task and not collector_task.done():
            await query.answer("⚠️ التجميع يعمل بالفعل", show_alert=True)
            return

        collector_task = asyncio.create_task(start_collector())

        await query.edit_message_text(
            "🟢 **تم تشغيل تجميع الروابط**\n\n"
            "• من كل الحسابات\n"
            "• بدون تكرار\n"
            "• يعمل في الخلفية",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )

    # عرض الروابط
    elif data == "view_links":
        buttons = [
            [InlineKeyboardButton(v, callback_data=f"cat:{k}")]
            for k, v in CATEGORIES.items()
        ]
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])

        await query.edit_message_text(
            "اختر التصنيف:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )


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
async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    urls = set()

    if msg.text:
        urls |= set(extract_links_from_text(msg.text))
    if msg.caption:
        urls |= set(extract_links_from_text(msg.caption))

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
                    urls |= set(extract_links_from_pdf(tmp.name))
                elif name.endswith(".docx"):
                    urls |= set(extract_links_from_docx(tmp.name))

                os.unlink(tmp.name)

    for url in urls:
        db.add_link(url, classify_link(url))


# ==================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_session_upload))
    app.add_handler(MessageHandler(filters.ALL, collect_links))

    print("🚀 Bot is running (final version)")
    app.run_polling()


if __name__ == "__main__":
    main()
