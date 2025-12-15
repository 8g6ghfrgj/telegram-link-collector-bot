# bot.py
import os
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from database import Database
from session_manager import SessionManager
from collector import start_collector

# ==============================
# الإعدادات من Render
# ==============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

db = Database()
sessions = SessionManager()
collector_task = None

# ==============================
# Keyboards
# ==============================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("👤 عرض الجلسات", callback_data="list_sessions")],
        [InlineKeyboardButton("🔗 تشغيل تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط المجمعة", callback_data="view_links")],
    ])


# ==============================
# /start
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 بوت تجميع الروابط\n\n"
        "➕ أضف الحساب عبر Session String فقط",
        reply_markup=main_keyboard()
    )


# ==============================
# Callbacks
# ==============================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global collector_task

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    if data == "add_session":
        context.user_data["await_session"] = True
        await query.edit_message_text(
            "📤 أرسل **Session String الآن**:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="back")]
            ])
        )

    elif data == "list_sessions":
        all_sessions = sessions.get_all_sessions()
        if not all_sessions:
            await query.edit_message_text("❌ لا توجد جلسات")
            return

        text = "👤 الجلسات المضافة:\n\n"
        for i, _ in enumerate(all_sessions, 1):
            text += f"{i}. Session\n"

        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif data == "start_collect":
        if collector_task and not collector_task.done():
            await query.answer("⚠️ التجميع يعمل بالفعل", show_alert=True)
            return

        collector_task = asyncio.create_task(start_collector())
        await query.edit_message_text(
            "🟢 تم تشغيل تجميع الروابط",
            reply_markup=main_keyboard()
        )

    elif data == "back":
        await query.edit_message_text("القائمة:", reply_markup=main_keyboard())


# ==============================
# استقبال Session String
# ==============================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.user_data.get("await_session"):
        session_string = update.message.text.strip()
        sessions.add_session(session_string)
        context.user_data["await_session"] = False

        await update.message.reply_text(
            "✅ تم إضافة الجلسة بنجاح",
            reply_markup=main_keyboard()
        )


# ==============================
# تشغيل البوت
# ==============================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 Bot started successfully")
    app.run_polling()


if __name__ == "__main__":
    main()
