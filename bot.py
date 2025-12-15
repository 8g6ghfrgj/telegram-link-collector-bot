# bot.py
import os
import asyncio

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

from database import Database
from collector import start_collector
from session_manager import (
    add_session_string,
    sessions_db,
    get_sessions_count,
)

# =========================
# Environment Variables
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# =========================
db = Database()
collector_task = None

# =========================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("👤 عرض الجلسات", callback_data="list_sessions")],
        [InlineKeyboardButton("🔗 تشغيل تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط المجمعة", callback_data="view_links")],
    ])

# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 بوت تجميع الروابط\n\n"
        f"👤 الجلسات: {get_sessions_count()}\n\n"
        "اختر:",
        reply_markup=main_keyboard()
    )

# =========================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global collector_task

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    # رجوع
    if data == "back":
        await query.edit_message_text("القائمة:", reply_markup=main_keyboard())

    # إضافة جلسة
    elif data == "add_session":
        context.user_data["await_session"] = True
        await query.edit_message_text(
            "📥 أرسل **Session String** الآن:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )

    # عرض الجلسات
    elif data == "list_sessions":
        sessions = sessions_db.all()
        if not sessions:
            await query.edit_message_text("❌ لا توجد جلسات", reply_markup=main_keyboard())
            return

        text = "👤 الجلسات:\n\n"
        for i, (phone, _) in enumerate(sessions, 1):
            text += f"{i}. {phone}\n"

        await query.edit_message_text(text, reply_markup=main_keyboard())

    # تشغيل التجميع
    elif data == "start_collect":
        if collector_task and not collector_task.done():
            await query.answer("⚠️ التجميع يعمل بالفعل", show_alert=True)
            return

        collector_task = asyncio.create_task(start_collector())

        await query.edit_message_text(
            "🟢 تم تشغيل تجميع الروابط\n"
            "يعمل الآن من كل الجلسات",
            reply_markup=main_keyboard()
        )

# =========================
# استقبال Session String
# =========================
async def receive_session_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.user_data.get("await_session"):
        return

    session_string = update.message.text.strip()

    if not session_string.startswith("1"):
        await update.message.reply_text("❌ Session String غير صالح")
        return

    add_session_string(session_string)
    context.user_data["await_session"] = False

    await update.message.reply_text(
        "✅ تم إضافة الجلسة بنجاح",
        reply_markup=main_keyboard()
    )

# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_session_string))

    print("🚀 Bot started")
    app.run_polling(drop_pending_updates=True)

# =========================
if __name__ == "__main__":
    main()
