# bot.py
import os
import asyncio
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
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
from session_manager import add_session_string, list_sessions
from collector import start_collector

# =========================
# الإعدادات
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

db = Database()
collector_task = None

PAGE_SIZE = 20

CATEGORIES = {
    "telegram": "✈️ تليجرام",
    "whatsapp": "📱 واتساب",
    "instagram": "📸 إنستغرام",
    "facebook": "📘 فيسبوك",
    "x": "🐦 X",
    "other": "📦 أخرى",
}

# =========================
# Keyboards
# =========================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data="add_session")],
        [InlineKeyboardButton("👤 عرض الجلسات", callback_data="list_sessions")],
        [InlineKeyboardButton("🔗 تشغيل تجميع الروابط", callback_data="start_collect")],
        [InlineKeyboardButton("📊 عرض الروابط", callback_data="view_links")],
        [InlineKeyboardButton("📤 تصدير الروابط", callback_data="export_links")],
    ])


def back_kb():
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
        "• من كل القنوات والجروبات\n"
        "• روابط قديمة + جديدة\n"
        "• بدون تكرار\n\n"
        "اختر:",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# =========================
# Callbacks
# =========================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global collector_task

    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    data = q.data

    # رجوع
    if data == "back":
        await q.edit_message_text("القائمة الرئيسية:", reply_markup=main_keyboard())
        return

    # إضافة جلسة
    if data == "add_session":
        context.user_data["wait_session"] = True
        await q.edit_message_text(
            "📥 أرسل **Session String** الآن:",
            reply_markup=back_kb(),
            parse_mode="Markdown"
        )
        return

    # عرض الجلسات
    if data == "list_sessions":
        sessions = list_sessions()
        if not sessions:
            await q.edit_message_text("❌ لا توجد جلسات", reply_markup=main_keyboard())
            return

        text = "👤 **الجلسات:**\n\n"
        for i, s in enumerate(sessions, 1):
            text += f"{i}. {s}\n"

        await q.edit_message_text(text, reply_markup=main_keyboard())
        return

    # تشغيل التجميع
    if data == "start_collect":
        if collector_task and not collector_task.done():
            await q.answer("⚠️ التجميع يعمل بالفعل", show_alert=True)
            return

        collector_task = asyncio.create_task(start_collector())

        await q.edit_message_text(
            "🟢 **تم تشغيل تجميع الروابط**\n\n"
            "• سيتم جمع كل الروابط القديمة والجديدة\n"
            "• من كل القنوات والجروبات\n"
            "• بدون تكرار\n\n"
            "⏳ العملية تعمل في الخلفية",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )
        return

    # عرض الروابط
    if data == "view_links":
        buttons = [
            [InlineKeyboardButton(v, callback_data=f"cat:{k}")]
            for k, v in CATEGORIES.items()
        ]
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="back")])
        await q.edit_message_text(
            "اختر التصنيف:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("cat:"):
        cat = data.split(":")[1]
        years = db.get_years()

        buttons = [
            [InlineKeyboardButton(str(y), callback_data=f"year:{cat}:{y}:0")]
            for y in years
        ]
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="view_links")])

        await q.edit_message_text(
            f"{CATEGORIES.get(cat, cat)} — اختر السنة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("year:"):
        _, cat, year, offset = data.split(":")
        year = int(year)
        offset = int(offset)

        total = db.count_links(cat, year)
        links = db.get_links(cat, year, PAGE_SIZE, offset)

        if not links:
            await q.answer("لا توجد روابط", show_alert=True)
            return

        text = f"{CATEGORIES.get(cat, cat)} — {year}\n"
        text += f"عرض {min(offset+PAGE_SIZE, total)} من {total}\n\n"

        for i, link in enumerate(links, start=offset + 1):
            text += f"{i}. {link}\n"

        nav = []
        if offset > 0:
            nav.append(
                InlineKeyboardButton("⏮ السابق", callback_data=f"year:{cat}:{year}:{offset-PAGE_SIZE}")
            )
        if offset + PAGE_SIZE < total:
            nav.append(
                InlineKeyboardButton("⏭ التالي", callback_data=f"year:{cat}:{year}:{offset+PAGE_SIZE}")
            )

        kb = []
        if nav:
            kb.append(nav)
        kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"cat:{cat}")])

        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    # تصدير
    if data == "export_links":
        path = db.export_to_txt()
        await q.message.reply_document(
            document=InputFile(path),
            caption="📤 تصدير كل الروابط"
        )
        os.remove(path)
        return

# =========================
# Messages
# =========================
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # إضافة Session String
    if context.user_data.get("wait_session"):
        session_string = update.message.text.strip()
        add_session_string(session_string)
        context.user_data["wait_session"] = False

        await update.message.reply_text(
            "✅ تم إضافة الجلسة بنجاح",
            reply_markup=main_keyboard()
        )

# =========================
# Main
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))

    print("🚀 Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
