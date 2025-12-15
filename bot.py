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
    sessions_count,
)

# =============================
# إعدادات من Render (ENV)
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود في Environment Variables")

# =============================
db = Database()
collector_task = None

# =============================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("👤 عرض الجلسات", callback_data="list_sessions")],
        [InlineKeyboardButton("🔗 تشغيل تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط المجمعة", callback_data="view_links")],
    ])

# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        f"🤖 **بوت تجميع الروابط**\n\n"
        f"👤 عدد الجلسات: {sessions_count()}\n\n"
        "اختر من القائمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# =============================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global collector_task

    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    data = q.data

    if data == "add_session":
        context.user_data["waiting_session"] = True
        await q.edit_message_text(
            "➕ **إضافة جلسة**\n\n"
            "📤 أرسل الآن **Session String** فقط:",
            parse_mode="Markdown"
        )

    elif data == "list_sessions":
        sessions = sessions_db.all()
        if not sessions:
            await q.edit_message_text("❌ لا توجد جلسات")
            return

        text = "👤 **الجلسات المضافة:**\n\n"
        for i, s in enumerate(sessions, 1):
            text += f"{i}. `{s[:25]}...`\n"

        await q.edit_message_text(text, parse_mode="Markdown")

    elif data == "start_collect":
        if collector_task and not collector_task.done():
            await q.answer("⚠️ التجميع يعمل بالفعل", show_alert=True)
            return

        collector_task = asyncio.create_task(start_collector())
        await q.edit_message_text(
            "🟢 **تم تشغيل تجميع الروابط**\n\n"
            "• من كل الحسابات\n"
            "• بدون تكرار",
            parse_mode="Markdown"
        )

    elif data == "view_links":
        await q.edit_message_text(
            "📊 عرض الروابط جاهز (كما تم سابقاً)\n\n"
            "يمكنك التصفح من الأقسام.",
        )

# =============================
async def receive_session_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.user_data.get("waiting_session"):
        return

    session_string = update.message.text.strip()
    context.user_data["waiting_session"] = False

    if len(session_string) < 50:
        await update.message.reply_text("❌ Session String غير صالح")
        return

    add_session_string(session_string)
    await update.message.reply_text("✅ تم إضافة الجلسة بنجاح")

# =============================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_session_string))

    print("🚀 Bot is running (Session String only)")
    app.run_polling()

# =============================
if __name__ == "__main__":
    main()
