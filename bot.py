# bot.py
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

from config import BOT_TOKEN, ADMIN_ID, API_ID, API_HASH
from session_manager import add_session_string
from collector import start_collector
from database import Database

db = Database()
collector_task = None


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة (Session String)", callback_data="add_session")],
        [InlineKeyboardButton("🔗 تشغيل تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط المجمعة", callback_data="view_links")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 بوت تجميع الروابط\nاختر:",
        reply_markup=main_keyboard()
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global collector_task

    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    if q.data == "add_session":
        context.user_data["await_session"] = True
        await q.edit_message_text("📤 أرسل Session String الآن:")

    elif q.data == "start_collect":
        if collector_task and not collector_task.done():
            await q.answer("⚠️ التجميع يعمل بالفعل", show_alert=True)
            return

        collector_task = asyncio.create_task(
            start_collector(API_ID, API_HASH)
        )

        await q.edit_message_text(
            "🟢 تم تشغيل تجميع الروابط\n"
            "سيتم جمع أي رابط يظهر في الحسابات تلقائياً.",
            reply_markup=main_keyboard()
        )

    elif q.data == "view_links":
        years = db.get_years()
        if not years:
            await q.edit_message_text("❌ لا توجد روابط بعد", reply_markup=main_keyboard())
            return

        text = "📊 الروابط المجمعة:\n\n"
        for y in years:
            count = db.count_links("telegram", y)
            text += f"• {y}: {count} رابط\n"

        await q.edit_message_text(text, reply_markup=main_keyboard())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("await_session"):
        add_session_string(update.message.text.strip())
        context.user_data["await_session"] = False
        await update.message.reply_text(
            "✅ تم إضافة الجلسة بنجاح",
            reply_markup=main_keyboard()
        )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
