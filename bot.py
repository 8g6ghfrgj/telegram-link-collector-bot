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
    save_admin_target,
    get_admin_target,
)

# ======================
# Logging
# ======================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        [InlineKeyboardButton("📞 تعيين قناة روابط واتساب", callback_data="set_target:whatsapp")],
        [InlineKeyboardButton("📨 تعيين قناة روابط تليجرام", callback_data="set_target:telegram")],
    ])


def collect_choice_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 واتساب فقط", callback_data="collect:whatsapp")],
        [InlineKeyboardButton("📨 تليجرام فقط", callback_data="collect:telegram")],
    ])

# ======================
# Commands
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Link Collector Bot*\n\n"
        "• لكل مشرف قناة خاصة به\n"
        "• القناة = قاعدة البيانات\n"
        "• لا يوجد تكرار روابط\n\n"
        "اختر من القائمة:",
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
    admin_id = query.from_user.id

    # ➕ إضافة حساب
    if data == "add_account":
        context.user_data["awaiting_session"] = True
        await query.message.reply_text("📥 أرسل Session String:")

    # 👤 عرض الحسابات
    elif data == "list_accounts":
        sessions = get_all_sessions(include_inactive=False)

        if not sessions:
            await query.message.reply_text("❌ لا توجد حسابات.")
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
            "👤 الحسابات:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ⚠️ الحسابات المعطلة
    elif data == "list_inactive_accounts":
        sessions = get_all_sessions(include_inactive=True)
        inactive = [s for s in sessions if int(s.get("active", 1)) == 0]

        if not inactive:
            await query.message.reply_text("✅ لا توجد حسابات معطلة.")
            return

        buttons = []
        for s in inactive:
            buttons.append([
                InlineKeyboardButton(
                    f"✅ تفعيل {s['name']}",
                    callback_data=f"enable_account:{s['id']}"
                )
            ])

        await query.message.reply_text(
            "⚠️ الحسابات المعطلة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("disable_account:"):
        disable_session(int(data.split(":")[1]))
        await query.message.reply_text("✅ تم تعطيل الحساب.")

    elif data.startswith("enable_account:"):
        enable_session(int(data.split(":")[1]))
        await query.message.reply_text("✅ تم تفعيل الحساب.")

    elif data.startswith("delete_account:"):
        delete_session(int(data.split(":")[1]))
        await query.message.reply_text("🗑 تم حذف الحساب.")

    # 🎯 تعيين قناة كمخزن
    elif data.startswith("set_target:"):
        link_type = data.split(":")[1]
        context.user_data["awaiting_target"] = link_type
        await query.message.reply_text(
            f"📥 أرسل رابط القناة أو القروب لحفظ روابط {link_type.upper()}:"
        )

    # ▶️ بدء الجمع
    elif data == "start_collect":
        if is_collecting():
            await query.message.reply_text("⏳ الجمع يعمل بالفعل.")
            return

        await query.message.reply_text(
            "اختر نوع الروابط:",
            reply_markup=collect_choice_keyboard()
        )

    elif data.startswith("collect:"):
        if is_collecting():
            await query.message.reply_text("⏳ الجمع يعمل بالفعل.")
            return

        platform = data.split(":")[1]
        asyncio.create_task(start_collection(platform=platform))
        await query.message.reply_text(f"▶️ بدأ تجميع روابط {platform.upper()}")

    # ⏹ إيقاف الجمع
    elif data == "stop_collect":
        stop_collection()
        await query.message.reply_text("⏹ تم إيقاف الجمع.")

# ======================
# Messages
# ======================

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.message.from_user.id
    text = update.message.text.strip()

    # إضافة Session
    if context.user_data.get("awaiting_session"):
        try:
            add_session(text)
            await update.message.reply_text("✅ تم إضافة الحساب.")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
        finally:
            context.user_data["awaiting_session"] = False
        return

    # تعيين قناة كمخزن
    if context.user_data.get("awaiting_target"):
        link_type = context.user_data["awaiting_target"]
        save_admin_target(admin_id, link_type, text)
        context.user_data["awaiting_target"] = None

        await update.message.reply_text(
            f"✅ تم حفظ قناة {link_type.upper()} بنجاح.\n"
            "سيتم استخدامها كقاعدة بيانات ومنع التكرار."
        )
        return

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
