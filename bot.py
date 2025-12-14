# bot.py
import asyncio
import re
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

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import BOT_TOKEN, ADMIN_ID
from database import Database


# =========================
# تهيئة
# =========================
db = Database()

URL_REGEX = re.compile(r"(https?://[^\s]+|t\.me/[^\s]+)")


# =========================
# أدوات مساعدة
# =========================
def classify_link(url: str) -> str:
    u = url.lower()
    if "wa.me" in u or "whatsapp" in u:
        return "واتساب"
    if "t.me" in u or "telegram" in u:
        return "تليجرام"
    if "instagram" in u:
        return "إنستغرام"
    if "facebook" in u or "fb.com" in u:
        return "فيسبوك"
    if "twitter.com" in u or "x.com" in u:
        return "تويتر / X"
    if u.startswith("http"):
        return "مواقع"
    return "أخرى"


def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("📂 إدارة الجلسات", callback_data="manage_sessions")],
        [InlineKeyboardButton("🔗 تجميع الروابط", callback_data="collect_links")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back")]
    ])


# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🤖 **بوت تجميع الروابط**\n\n"
        "اختر الخدمة:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )


# =========================
# Callback Queries
# =========================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    # رجوع للقائمة الرئيسية
    if data == "back":
        context.user_data.clear()
        await query.edit_message_text(
            "🏠 القائمة الرئيسية",
            reply_markup=main_keyboard()
        )

    # إضافة جلسة
    elif data == "add_session":
        context.user_data["state"] = "WAIT_SESSION"
        await query.edit_message_text(
            "➕ **إضافة جلسة**\n\n"
            "أرسل Session String الآن:",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )

    # إدارة الجلسات
    elif data == "manage_sessions":
        sessions = db.get_sessions_with_id()

        if not sessions:
            await query.edit_message_text(
                "📂 لا توجد جلسات مضافة",
                reply_markup=back_keyboard()
            )
            return

        text = "📂 **الجلسات المضافة:**\n\n"
        buttons = []

        for sid, sess in sessions:
            short = sess[:18] + "..."
            text += f"• `{short}`\n"
            buttons.append([
                InlineKeyboardButton("❌ حذف", callback_data=f"del_session:{sid}")
            ])

        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )

    # حذف جلسة
    elif data.startswith("del_session:"):
        session_id = int(data.split(":")[1])
        db.delete_session(session_id)

        await query.edit_message_text(
            "✅ تم حذف الجلسة",
            reply_markup=main_keyboard()
        )

    # تجميع الروابط
    elif data == "collect_links":
        await query.edit_message_text(
            "🔄 **جاري تجميع الروابط...**\n\n"
            "العملية تعمل بهدوء، الرجاء الانتظار ⏳",
            reply_markup=back_keyboard(),
            parse_mode="Markdown"
        )

        context.application.create_task(
            collect_links_task(query)
        )


# =========================
# استقبال الرسائل
# =========================
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    state = context.user_data.get("state")

    if state == "WAIT_SESSION":
        session_string = update.message.text.strip()
        context.user_data.clear()

        ok = db.add_session(session_string)

        if ok:
            await update.message.reply_text(
                "✅ تم حفظ الجلسة بنجاح",
                reply_markup=main_keyboard()
            )
        else:
            await update.message.reply_text(
                "⚠️ هذه الجلسة مضافة مسبقاً",
                reply_markup=main_keyboard()
            )


# =========================
# منطق تجميع الروابط
# =========================
async def collect_links_task(query):
    sessions = db.get_sessions()
    total = 0

    for session in sessions:
        try:
            client = TelegramClient(
                StringSession(session),
                1,
                "a"
            )
            await client.connect()

            async for dialog in client.iter_dialogs():
                if not (dialog.is_group or dialog.is_channel):
                    continue

                async for msg in client.iter_messages(dialog.id, limit=100):
                    if not msg.text:
                        continue

                    urls = URL_REGEX.findall(msg.text)
                    for url in urls:
                        category = classify_link(url)
                        year = msg.date.year if msg.date else datetime.utcnow().year
                        db.add_link(url, category, year)
                        total += 1

                await asyncio.sleep(3)  # أمان

            await client.disconnect()

        except Exception:
            continue

    await query.edit_message_text(
        f"✅ **انتهى التجميع**\n\n"
        f"🔗 الروابط المضافة: {total}",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )


# =========================
# تشغيل البوت
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))

    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
