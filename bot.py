import asyncio
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from session_manager import add_session, get_all_sessions
from collector import start_collection, stop_collection, is_collecting
from database import (
    init_db,
    count_links_by_platform,
    export_links,
    get_links
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ======================
# Keyboards
# ======================

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة حساب", callback_data="add")],
        [InlineKeyboardButton("👤 عرض الحسابات", callback_data="accounts")],
        [InlineKeyboardButton("▶️ بدء الجمع", callback_data="start")],
        [InlineKeyboardButton("⏹ إيقاف الجمع", callback_data="stop")],
        [InlineKeyboardButton("📊 عرض الروابط", callback_data="links")],
        [InlineKeyboardButton("📤 تصدير الروابط", callback_data="export")],
    ])


# ======================
# Commands
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Link Collector Bot",
        reply_markup=main_keyboard()
    )


# ======================
# Callbacks
# ======================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "add":
        context.user_data["awaiting_session"] = True
        await q.message.reply_text("📥 أرسل Session String")

    elif q.data == "accounts":
        sessions = get_all_sessions()
        if not sessions:
            await q.message.reply_text("❌ لا توجد حسابات")
            return

        text = "👤 الحسابات:\n\n"
        for s in sessions:
            text += f"- {s['name']}\n"

        await q.message.reply_text(text)

    elif q.data == "start":
        if is_collecting():
            await q.message.reply_text("⏳ الجمع يعمل بالفعل")
            return
        asyncio.create_task(start_collection())
        await q.message.reply_text("⏳ بدأ جمع الروابط")

    elif q.data == "stop":
        stop_collection()
        await q.message.reply_text("⏹ تم إيقاف الاستماع")

    elif q.data == "links":
        links = get_links(limit=30, offset=0)
        if not links:
            await q.message.reply_text("❌ لا توجد روابط")
            return

        text = "🔗 آخر الروابط:\n\n"
        for url, date in links:
            year = date[:4] if date else "----"
            text += f"[{year}] {url}\n"

        await q.message.reply_text(text[:4000])

    elif q.data == "export":
        path = export_links("all")

        if not path or not os.path.exists(path):
            await q.message.reply_text("❌ لا توجد روابط للتصدير")
            return

        with open(path, "rb") as f:
            await q.message.reply_document(
                document=f,
                filename="links_all.txt"
            )


# ======================
# Messages
# ======================

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_session"):
        try:
            add_session(update.message.text.strip())
            await update.message.reply_text("✅ تم إضافة الحساب")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
        context.user_data["awaiting_session"] = False


# ======================
# Main
# ======================

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))

    app.run_polling()


if __name__ == "__main__":
    main()
