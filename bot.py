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
    disable_session,
    enable_session,
)
from collector import (
    start_collection,
    stop_collection,
    is_collecting,
)
from database import (
    init_db,
    export_links,
    get_links_by_platform_and_type,
    create_backup_zip,   # ✅ NEW
)

# ======================
# Logging
# ======================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================
# Constants
# ======================

PAGE_SIZE = 20


# ======================
# Keyboards
# ======================

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة حساب", callback_data="add_account")],
        [InlineKeyboardButton("👤 عرض الحسابات", callback_data="list_accounts")],
        [InlineKeyboardButton("⚠️ الحسابات المعطلة", callback_data="list_inactive_accounts")],
        [InlineKeyboardButton("▶️ بدء الجمع", callback_data="start_collect")],
        [InlineKeyboardButton("⏹ إيقاف الجمع", callback_data="stop_collect")],
        [InlineKeyboardButton("📊 عرض الروابط", callback_data="view_links")],
        [InlineKeyboardButton("📤 تصدير الروابط", callback_data="export_links")],
        [InlineKeyboardButton("📦 نسخة احتياطية الآن", callback_data="backup_now")],
    ])


def platforms_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 تيليجرام", callback_data="choose:telegram")],
        [InlineKeyboardButton("📞 واتساب", callback_data="choose:whatsapp")],
        [InlineKeyboardButton("📸 إنستغرام", callback_data="links:instagram:other:0")],
        [InlineKeyboardButton("❌ X / تويتر", callback_data="links:x:other:0")],
        [InlineKeyboardButton("📘 فيسبوك", callback_data="links:facebook:other:0")],
        [InlineKeyboardButton("🌐 مواقع أخرى", callback_data="links:other:other:0")],
    ])


def telegram_types_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 القنوات", callback_data="links:telegram:channel:0"),
            InlineKeyboardButton("👥 المجموعات", callback_data="links:telegram:group:0"),
        ]
    ])


def whatsapp_types_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 مجموعات واتساب", callback_data="links:whatsapp:group:0"),
        ]
    ])


def pagination_keyboard(platform, chat_type, page):
    buttons = []

    if page > 0:
        buttons.append(
            InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"links:{platform}:{chat_type}:{page - 1}"
            )
        )

    buttons.append(
        InlineKeyboardButton(
            "➡️ التالي",
            callback_data=f"links:{platform}:{chat_type}:{page + 1}"
        )
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
# Internal Helpers
# ======================

async def _send_backup_to_user(query):
    """
    ينشئ Backup ZIP ويرسله للمستخدم
    """
    backup_path = create_backup_zip(max_keep=15)

    if not backup_path or not os.path.exists(backup_path):
        await query.message.reply_text("❌ تعذر إنشاء نسخة احتياطية (لا يوجد قاعدة بيانات).")
        return

    with open(backup_path, "rb") as f:
        await query.message.reply_document(
            document=f,
            filename=os.path.basename(backup_path),
            caption="✅ نسخة احتياطية للروابط + exports"
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

    # 👤 عرض الحسابات (الفعالة)
    elif data == "list_accounts":
        sessions = get_all_sessions(include_inactive=False)
        if not sessions:
            await query.message.reply_text("❌ لا يوجد حسابات فعالة.")
            return

        buttons = []
        for s in sessions:
            buttons.append([
                InlineKeyboardButton(
                    f"🛑 تعطيل {s['name']}",
                    callback_data=f"disable_account:{s['id']}"
                ),
                InlineKeyboardButton(
                    f"🗑 حذف {s['name']}",
                    callback_data=f"delete_account:{s['id']}"
                )
            ])

        await query.message.reply_text(
            "👤 الحسابات الفعالة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ⚠️ الحسابات المعطلة
    elif data == "list_inactive_accounts":
        sessions = get_all_sessions(include_inactive=True)
        inactive = [s for s in sessions if int(s.get("active", 1)) == 0]

        if not inactive:
            await query.message.reply_text("✅ لا توجد حسابات معطلة حالياً.")
            return

        buttons = []
        for s in inactive:
            reason = s.get("disabled_reason") or "بدون سبب"
            buttons.append([
                InlineKeyboardButton(
                    f"✅ تفعيل {s['name']}",
                    callback_data=f"enable_account:{s['id']}"
                )
            ])
            await query.message.reply_text(f"⚠️ {s['name']}\nالسبب: {reason}")

        await query.message.reply_text(
            "⚠️ الحسابات المعطلة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # تعطيل حساب
    elif data.startswith("disable_account:"):
        session_id = int(data.split(":")[1])
        disable_session(session_id, reason="Disabled manually from bot UI")
        await query.message.reply_text("✅ تم تعطيل الحساب (بدون حذف).")

    # تفعيل حساب
    elif data.startswith("enable_account:"):
        session_id = int(data.split(":")[1])
        enable_session(session_id)
        await query.message.reply_text("✅ تم تفعيل الحساب.")

    # حذف حساب (يدوي فقط)
    elif data.startswith("delete_account:"):
        session_id = int(data.split(":")[1])
        delete_session(session_id)
        await query.message.reply_text("✅ تم حذف الحساب نهائياً.")

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
        await query.message.reply_text("⏹ تم إيقاف الاستماع.")

        # ✅ NEW: backup automatically on stop (مفيد جداً على Render)
        try:
            await _send_backup_to_user(query)
        except Exception as e:
            logger.error(f"Backup failed on stop_collect: {e}")

    # 📦 نسخة احتياطية الآن
    elif data == "backup_now":
        await query.message.reply_text("⏳ جاري إنشاء النسخة الاحتياطية...")
        await _send_backup_to_user(query)

    # 📊 عرض الروابط
    elif data == "view_links":
        await query.message.reply_text(
            "📊 اختر المنصة:",
            reply_markup=platforms_keyboard()
        )

    # اختيار منصة
    elif data == "choose:telegram":
        await query.message.reply_text(
            "📨 روابط تيليجرام:",
            reply_markup=telegram_types_keyboard()
        )

    elif data == "choose:whatsapp":
        await query.message.reply_text(
            "📞 روابط واتساب:",
            reply_markup=whatsapp_types_keyboard()
        )

    # عرض روابط (منصة + نوع + Pagination)
    elif data.startswith("links:"):
        _, platform, chat_type, page = data.split(":")
        page = int(page)

        links = get_links_by_platform_and_type(
            platform=platform,
            chat_type=chat_type,
            limit=PAGE_SIZE,
            offset=page * PAGE_SIZE
        )

        if not links and page == 0:
            await query.message.reply_text("❌ لا توجد روابط.")
            return

        title = f"{platform.upper()} / {chat_type.upper()}"
        text = f"🔗 روابط {title} – صفحة {page + 1}\n\n"

        for url, date in links:
            year = date[:4] if date else "----"
            text += f"[{year}] {url}\n"

        await query.message.reply_text(
            text[:4000],
            reply_markup=pagination_keyboard(platform, chat_type, page)
        )

    # 📤 تصدير الروابط
    elif data == "export_links":
        await query.message.reply_text(
            "📤 التصدير:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 تصدير الكل", callback_data="export:all")],
                [InlineKeyboardButton("📄 تيليجرام", callback_data="export:telegram")],
                [InlineKeyboardButton("📄 واتساب", callback_data="export:whatsapp")],
                [InlineKeyboardButton("📄 إنستغرام", callback_data="export:instagram")],
                [InlineKeyboardButton("📄 تويتر / X", callback_data="export:x")],
                [InlineKeyboardButton("📄 فيسبوك", callback_data="export:facebook")],
                [InlineKeyboardButton("📄 مواقع أخرى", callback_data="export:other")],
            ])
        )

    elif data.startswith("export:"):
        platform = data.split(":")[1]
        path = export_links(platform)

        if not path or not os.path.exists(path):
            await query.message.reply_text("❌ لا توجد روابط.")
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
            await update.message.reply_text("✅ تم إضافة الحساب.")
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
