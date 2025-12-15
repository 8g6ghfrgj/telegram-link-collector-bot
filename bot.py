import asyncio
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from session_manager import (
    add_session,
    get_all_sessions,
    delete_session,
)
from collector import (
    start_collection,
    stop_collection,
    is_collecting,
)
from database import (
    init_db,
    get_links_paginated,
    count_links_by_platform,
    export_links,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ======================
# Keyboards
# ======================

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة حساب", callback_data="add_account")],
        [InlineKeyboardButton("👤 عرض الحسابات", callback_data="list_accounts")],
        [InlineKeyboardButton("▶️ بدء الجمع", callback_data="start_collect")],
        [InlineKeyboardButton("⏹ إيقاف الجمع", callback_data="stop_collect")],
        [InlineKeyboardButton("📊 عرض الروابط", callback_data="view_links")],
        [InlineKeyboardButton("📤 تصدير الروابط", callback_data="export_links")],
    ])


# ======================
# Commands
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Telegram Multi-Account Link Collector*\n\n"
        "اختر ما تريد من القائمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )


# ======================
# Callbacks
# ======================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "add_account":
        context.user_data["awaiting_session"] = True
        await query.message.reply_text(
            "📥 أرسل *Session String* الآن:",
            parse_mode="Markdown"
        )

    elif data == "list_accounts":
        sessions = get_all_sessions()
        if not sessions:
            await query.message.reply_text("❌ لا يوجد حسابات مضافة.")
            return

        buttons = []
        for s in sessions:
            buttons.append([
                InlineKeyboardButton(
                    f"🗑 حذف {s['name']}",
                    callback_data=f"delete_session:{s['id']}"
                )
            ])

        await query.message.reply_text(
            "👤 الحسابات المضافة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("delete_session:"):
        session_id = int(data.split(":")[1])
        delete_session(session_id)
        await query.message.reply_text("✅ تم حذف الحساب.")

    elif data == "start_collect":
        if is_collecting():
            await query.message.reply_text("⏳ الجمع يعمل بالفعل.")
            return

        asyncio.create_task(start_collection())
        await query.message.reply_text("⏳ جاري جمع الروابط...")

    elif data == "stop_collect":
        stop_collection()
        await query.message.reply_text("⏹ تم إيقاف الاستماع للرسائل الجديدة.")

    elif data == "view_links":
        stats = count_links_by_platform()
        text = "📊 *إحصائيات الروابط:*\n\n"
        for platform, count in stats.items():
            text += f"• {platform}: {count}\n"

        await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "export_links":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 تصدير الكل", callback_data="export:all")],
            [InlineKeyboardButton("📄 تيليجرام", callback_data="export:telegram")],
            [InlineKeyboardButton("📄 واتساب", callback_data="export:whatsapp")],
            [InlineKeyboardButton("📄 إنستغرام", callback_data="export:instagram")],
            [InlineKeyboardButton("📄 فيسبوك", callback_data="export:facebook")],
            [InlineKeyboardButton("📄 X", callback_data="export:x")],
            [InlineKeyboardButton("📄 أخرى", callback_data="export:other")],
        ])
        await query.message.reply_text(
            "📤 اختر نوع التصدير:",
            reply_markup=keyboard
        )

    elif data.startswith("export:"):
        platform = data.split(":")[1]
        file_path = export_links(platform)
        await query.message.reply_document(
            document=open(file_path, "rb"),
            filename=file_path.split("/")[-1]
        )


# ======================
# Messages
# ======================

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_session"):
        session_string = update.message.text.strip()
        try:
            add_session(session_string)
            await update.message.reply_text("✅ تم إضافة الحساب بنجاح.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ:\n{e}")
        finally:
            context.user_data["awaiting_session"] = False


# ======================
# Main
# ======================

def main():
    init_db()

    app = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))

    logger.info("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
