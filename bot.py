import asyncio
import logging
import os

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
    get_links_by_platform_paginated,
    count_links_by_platform,
    export_links,
)

# ======================
# Logging
# ======================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================
# Constants
# ======================

PLATFORMS = [
    ("telegram", "📨 تيليجرام"),
    ("whatsapp", "📞 واتساب"),
    ("instagram", "📸 إنستغرام"),
    ("facebook", "📘 فيسبوك"),
    ("x", "❌ X"),
    ("other", "🌐 أخرى"),
]

PAGE_SIZE = 20


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


def platforms_keyboard():
    buttons = []
    for key, name in PLATFORMS:
        buttons.append(
            InlineKeyboardButton(name, callback_data=f"links:{key}:0")
        )

    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def pagination_keyboard(platform, page):
    buttons = []

    if page > 0:
        buttons.append(
            InlineKeyboardButton("⬅️ السابق", callback_data=f"links:{platform}:{page - 1}")
        )

    buttons.append(
        InlineKeyboardButton("➡️ التالي", callback_data=f"links:{platform}:{page + 1}")
    )

    return InlineKeyboardMarkup([buttons])


# ======================
# Commands
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Telegram Multi-Account Link Collector Bot*\n\n"
        "اختر أمراً من القائمة:",
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

    # ➕ إضافة حساب
    if data == "add_account":
        context.user_data["awaiting_session"] = True
        await query.message.reply_text("📥 أرسل Session String الآن:")

    # 👤 عرض الحسابات
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
                    callback_data=f"delete_account:{s['id']}"
                )
            ])

        await query.message.reply_text(
            "👤 الحسابات المضافة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("delete_account:"):
        session_id = int(data.split(":")[1])
        delete_session(session_id)
        await query.message.reply_text("✅ تم حذف الحساب.")

    # ▶️ بدء الجمع
    elif data == "start_collect":
        if is_collecting():
            await query.message.reply_text("⏳ الجمع يعمل بالفعل.")
            return

        asyncio.create_task(start_collection())
        await query.message.reply_text("⏳ جاري جمع الروابط...")

    # ⏹ إيقاف الجمع
    elif data == "stop_collect":
        stop_collection()
        await query.message.reply_text("⏹ تم إيقاف الاستماع للرسائل الجديدة.")

    # 📊 عرض الروابط
    elif data == "view_links":
        await query.message.reply_text(
            "📊 اختر المنصة:",
            reply_markup=platforms_keyboard()
        )

    # عرض روابط حسب المنصة + Pagination
    elif data.startswith("links:"):
        _, platform, page = data.split(":")
        page = int(page)

        links = get_links_by_platform_paginated(
            platform=platform,
            limit=PAGE_SIZE,
            offset=page * PAGE_SIZE
        )

        if not links and page == 0:
            await query.message.reply_text("❌ لا توجد روابط.")
            return

        text = f"🔗 روابط ({platform}) – صفحة {page + 1}\n\n"

        for url, date in links:
            year = date[:4] if date else "----"
            text += f"[{year}] {url}\n"

        await query.message.reply_text(
            text[:4000],
            reply_markup=pagination_keyboard(platform, page)
        )

    # 📤 تصدير الروابط
    elif data == "export_links":
        buttons = []
        for key, name in PLATFORMS:
            buttons.append(
                InlineKeyboardButton(
                    f"📄 {name}",
                    callback_data=f"export:{key}"
                )
            )
        buttons.append(
            InlineKeyboardButton("📄 تصدير الكل", callback_data="export:all")
        )

        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

        await query.message.reply_text(
            "📤 اختر نوع التصدير:",
            reply_markup=InlineKeyboardMarkup(rows)
        )

    elif data.startswith("export:"):
        platform = data.split(":")[1]
        path = export_links(platform)

        if not path or not os.path.exists(path):
            await query.message.reply_text("❌ لا توجد روابط للتصدير.")
            return

        with open(path, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=os.path.basename(path)
            )


# ======================
# Messages
# ======================

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_session"):
        try:
            add_session(update.message.text.strip())
            await update.message.reply_text("✅ تم إضافة الحساب بنجاح.")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
        finally:
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

    logger.info("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
