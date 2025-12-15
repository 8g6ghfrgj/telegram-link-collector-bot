import asyncio
import logging
import sys
import signal
from typing import List, Dict
from datetime import datetime
from aiohttp import web
import threading

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import BOT_TOKEN, LINKS_PER_PAGE, IS_RENDER
from database import Database
from telegram_client import TelegramScraper

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
db = Database()

# ===== خادم ويب للـ Health Check =====
async def health_check(request):
    """Endpoint للـ Health Check"""
    return web.Response(text='OK')

async def start_web_server():
    """تشغيل خادم ويب بسيط"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    # الحصول على البورت من متغير البيئة أو استخدام 8080
    port = int(os.environ.get('PORT', 8080))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    print(f"🌐 خادم الويب يعمل على port {port}")
    await site.start()
    
    # إبقاء الخادم يعمل
    await asyncio.Event().wait()

# ===== الفئة الرئيسية للبوت =====
class TelegramLinksBot:
    def __init__(self):
        self.scraping_tasks = {}
        self.current_selections = {}
        self.application = None
        
        # تشغيل خادم الويب في thread منفصل إذا كنا على Render
        if IS_RENDER:
            print("🚀 بدء تشغيل خادم الويب للـ Health Check...")
            threading.Thread(target=self.run_web_server, daemon=True).start()
    
    def run_web_server(self):
        """تشغيل خادم الويب في thread منفصل"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_web_server())
    
    # ===== مساعدات الواجهة =====
    async def send_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           message: str = "📱 **القائمة الرئيسية**"):
        """إرسال القائمة الرئيسية"""
        keyboard = [
            [KeyboardButton("➕ إضافة جلسة"), KeyboardButton("👥 الجلسات المضافة")],
            [KeyboardButton("🔍 تجميع الروابط"), KeyboardButton("📊 الروابط المجمعة")],
            [KeyboardButton("📈 إحصائيات"), KeyboardButton("❓ المساعدة")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=None
            )
            await update.callback_query.message.reply_text(
                text="اختر من القائمة:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text="اختر من القائمة:",
                reply_markup=reply_markup
            )
    
    # ===== معالجات الأوامر =====
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بدء البوت"""
        user = update.effective_user
        welcome_msg = f"""
        🎉 أهلاً بك {user.first_name}!
        
        **بوت جمع الروابط من التليجرام**
        
        🌐 **السيرفر:** Render.com
        ✅ **الحالة:** نشط
        
        ✨ **المميزات:**
        ✅ إضافة حسابات تيليجرام
        ✅ جمع الروابط من القنوات
        ✅ عرض وتصدير الروابط
        
        🚀 **لتبدأ، اختر من القائمة:**
        """
        
        await self.send_main_menu(update, context, welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مساعدة"""
        help_text = """
        📖 **دليل استخدام البوت:**
        
        **1. ➕ إضافة جلسة:**
           - احصل على session_string من @genStr_robot
           - أرسله للبوت
        
        **2. 🔍 تجميع الروابط:**
           - اختر جلسة
           - البوت يجمع الروابط تلقائياً
        
        **3. 📊 الروابط المجمعة:**
           - اختر النوع والسنة
           - استعرض الروابط
           - اضغط 📤 لتصدير الملف
        
        ⚡ **يعمل على Render.com**
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    # ===== إدارة الجلسات =====
    async def add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إضافة جلسة جديدة"""
        await update.message.reply_text(
            "📱 **إضافة جلسة جديدة**\n\n"
            "أرسل لي `session_string` الخاص بحسابك.\n"
            "يمكنك الحصول عليه من @genStr_robot\n\n"
            "❌ **تحذير:** لا تشارك الجلسة مع أحد!\n\n"
            "أرسل `session_string` الآن أو /cancel للإلغاء:"
        )
        context.user_data['awaiting_session'] = True
    
    async def handle_session_string(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة session_string"""
        if not context.user_data.get('awaiting_session'):
            return
        
        session_string = update.message.text.strip()
        
        if len(session_string) < 50:
            await update.message.reply_text("❌ هذا لا يبدو session string صالح!")
            context.user_data['awaiting_session'] = False
            return
        
        await update.message.reply_text("🔍 جاري اختبار الجلسة...")
        
        scraper = TelegramScraper(session_string)
        connected = await scraper.connect()
        
        if connected:
            try:
                me = await scraper.client.get_me()
                phone_number = me.phone
                
                if db.add_session(session_string, phone_number):
                    await update.message.reply_text(
                        f"✅ **تم إضافة الجلسة بنجاح!**\n\n"
                        f"📞 الرقم: `{phone_number}`\n"
                        f"👤 الاسم: {me.first_name or ''}\n\n"
                        "يمكنك الآن استخدام الجلسة لتجميع الروابط.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("⚠️ هذه الجلسة مضافه مسبقاً!")
            except Exception as e:
                await update.message.reply_text(f"❌ خطأ: {str(e)[:100]}")
            finally:
                await scraper.disconnect()
        else:
            await update.message.reply_text("❌ **الجلسة غير صالحة!**")
        
        context.user_data['awaiting_session'] = False
        await self.send_main_menu(update, context)
    
    async def show_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الجلسات المضافة"""
        sessions = db.get_all_sessions()
        
        if not sessions:
            await update.message.reply_text("📭 لا توجد جلسات مضافة بعد.")
            return
        
        message = "📱 **الجلسات المضافة:**\n\n"
        for i, session in enumerate(sessions, 1):
            status = "🟢 نشط" if session['is_active'] else "🔴 غير نشط"
            message += f"**{i}. {session['phone_number']}**\n"
            message += f"   📅 {session['created_at'][:19]}\n"
            message += f"   {status}\n   ─────\n"
        
        message += f"\n📊 **المجموع: {len(sessions)} جلسة**"
        
        keyboard = [
            [InlineKeyboardButton("🗑 حذف جلسة", callback_data="delete_session")],
            [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_sessions")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
        ]
        
        await update.message.reply_text(
            message, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ===== باقي الدوال (مختصرة) =====
    async def start_scraping_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة تجميع الروابط"""
        sessions = db.get_all_sessions()
        
        if not sessions:
            await update.message.reply_text("❌ **لا توجد جلسات!**")
            return
        
        keyboard = []
        for session in sessions:
            if session['is_active']:
                btn_text = f"📱 {session['phone_number']}"
                callback_data = f"scrape_session_{session['id']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        
        if not keyboard:
            await update.message.reply_text("❌ لا توجد جلسات نشطة!")
            return
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")])
        
        await update.message.reply_text(
            "🔍 **تجميع الروابط**\n\nاختر الجلسة:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_links_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة عرض الروابط"""
        user_id = update.effective_user.id
        self.current_selections[user_id] = {'type': None, 'year': None}
        
        keyboard = [
            [
                InlineKeyboardButton("📢 تيليجرام", callback_data="link_type_telegram"),
                InlineKeyboardButton("💬 واتساب", callback_data="link_type_whatsapp")
            ],
            [
                InlineKeyboardButton("🌐 مواقع", callback_data="link_type_website"),
                InlineKeyboardButton("📺 يوتيوب", callback_data="link_type_youtube")
            ],
            [
                InlineKeyboardButton("📷 انستجرام", callback_data="link_type_instagram"),
                InlineKeyboardButton("🐦 تويتر", callback_data="link_type_twitter")
            ],
            [InlineKeyboardButton("📂 الكل", callback_data="link_type_all")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
        ]
        
        total_links = db.get_links_count()
        message = f"📊 **عرض الروابط المجمعة**\n\n🔗 **الإجمالي:** {total_links:,}\n\n**اختر نوع الروابط:**"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة Callback Queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "back_to_menu":
                await self.send_main_menu(update, context)
            
            elif data == "refresh_sessions":
                await self.show_sessions(update, context)
            
            elif data.startswith("scrape_session_"):
                session_id = int(data.split("_")[2])
                await query.edit_message_text(
                    "⏳ **جاري بدء عملية تجميع الروابط...**\n\n"
                    "هذه العملية قد تستغرق بضع دقائق.\n"
                    "سأرسل لك التحديثات عند الانتهاء.",
                    parse_mode='Markdown'
                )
                # هنا سيتم بدء عملية الجمع
            
            elif data.startswith("link_type_"):
                link_type = data.split("_")[2]
                user_id = update.effective_user.id
                self.current_selections[user_id] = {'type': link_type, 'year': None}
                
                # عرض الروابط مباشرة (بدون اختيار سنة للمساعدة)
                await self.show_links_page(update, context, 1)
            
            else:
                await query.edit_message_text(
                    "⚙️ **جاري العمل...**\n\nاستخدم /start للعودة",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(
                f"❌ **خطأ:**\n\n{str(e)[:100]}",
                parse_mode='Markdown'
            )
    
    async def show_links_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
        """عرض صفحة من الروابط"""
        user_id = update.effective_user.id
        
        if user_id not in self.current_selections:
            await update.callback_query.answer("❌ ابدأ من القائمة!")
            return
        
        link_type = self.current_selections[user_id]['type']
        
        # الحصول على الروابط
        links, total_count = db.get_links(
            link_type=link_type if link_type != 'all' else None,
            year=None,
            page=page,
            per_page=LINKS_PER_PAGE
        )
        
        if not links:
            await update.callback_query.edit_message_text(
                "📭 **لا توجد روابط!**\n\nجرب جمع الروابط أولاً.",
                parse_mode='Markdown'
            )
            return
        
        # حساب عدد الصفحات
        total_pages = max(1, (total_count + LINKS_PER_PAGE - 1) // LINKS_PER_PAGE)
        
        # بناء الرسالة
        type_names = {
            'telegram': 'تيليجرام',
            'whatsapp': 'واتساب',
            'website': 'مواقع',
            'youtube': 'يوتيوب',
            'instagram': 'انستجرام',
            'twitter': 'تويتر',
            'all': 'الكل'
        }
        
        type_name = type_names.get(link_type, link_type)
        
        message = f"📋 **الروابط ({type_name})**\n\n"
        message += f"📄 الصفحة: {page}/{total_pages}\n"
        message += f"🔗 المجموع: {total_count:,}\n"
        message += "─" * 30 + "\n\n"
        
        for i, link in enumerate(links, 1):
            index = (page - 1) * LINKS_PER_PAGE + i
            message += f"**{index}. {link['link']}**\n"
            if link['chat_title']:
                message += f"   📍 {link['chat_title'][:30]}\n"
            message += "\n"
        
        # أزرار التصفح
        keyboard = []
        if page > 1:
            keyboard.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{page-1}"))
        
        keyboard.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="current_page"))
        
        if page < total_pages:
            keyboard.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page_{page+1}"))
        
        nav_row = keyboard if keyboard else []
        
        reply_markup = InlineKeyboardMarkup([
            nav_row,
            [InlineKeyboardButton("📤 تصدير", callback_data=f"export_{link_type}_all_{page}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="links_menu")]
        ])
        
        await update.callback_query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل النصية"""
        message_text = update.message.text
        
        if message_text == "➕ إضافة جلسة":
            await self.add_session(update, context)
        
        elif message_text == "👥 الجلسات المضافة":
            await self.show_sessions(update, context)
        
        elif message_text == "🔍 تجميع الروابط":
            await self.start_scraping_menu(update, context)
        
        elif message_text == "📊 الروابط المجمعة":
            await self.show_links_menu(update, context)
        
        elif message_text == "📈 إحصائيات":
            total_links = db.get_links_count()
            total_sessions = len(db.get_all_sessions())
            
            stats = (
                f"📈 **إحصائيات البوت**\n\n"
                f"🔗 **الروابط:** {total_links:,}\n"
                f"👥 **الجلسات:** {total_sessions}\n"
                f"🌐 **السيرفر:** Render.com\n"
                f"🕒 **الوقت:** {datetime.now().strftime('%H:%M:%S')}\n"
            )
            await update.message.reply_text(stats, parse_mode='Markdown')
        
        elif message_text == "❓ المساعدة":
            await self.help_command(update, context)
        
        elif context.user_data.get('awaiting_session'):
            await self.handle_session_string(update, context)
        
        else:
            await update.message.reply_text(
                "🤔 لم أفهم رسالتك.\nاستخدم الأزرار أدناه أو /start",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("➕ إضافة جلسة"), KeyboardButton("👥 الجلسات المضافة")],
                    [KeyboardButton("🔍 تجميع الروابط"), KeyboardButton("📊 الروابط المجمعة")],
                    [KeyboardButton("📈 إحصائيات"), KeyboardButton("❓ المساعدة")]
                ], resize_keyboard=True)
            )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء أي عملية"""
        if 'awaiting_session' in context.user_data:
            context.user_data['awaiting_session'] = False
        
        await update.message.reply_text("✅ تم الإلغاء")
        await self.send_main_menu(update, context)
    
    def run(self):
        """تشغيل البوت"""
        print(f"🚀 بدء تشغيل البوت على Render...")
        
        # إنشاء التطبيق
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة المعالجات
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # بدء البوت
        print("✅ البوت يعمل الآن!")
        print("📡 في انتظار الرسائل...")
        
        # تشغيل البوت مع Polling
        self.application.run_polling(
            poll_interval=0.5,
            timeout=30,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

# ===== التهيئة والتشغيل =====
if __name__ == "__main__":
    import os
    
    # إضافة os إلى config
    import config
    config.os = os
    
    # التحقق من التوكن
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        print("❌ خطأ: لم يتم تعيين BOT_TOKEN!")
        print("📝 قم بإضافته في متغيرات Render")
        print("💡 في Render: Environment → Add Environment Variable")
        sys.exit(1)
    
    # إعداد معالجة الإشارات
    def signal_handler(signum, frame):
        print(f"\n⚠️ تم استقبال إشارة {signum}، إيقاف البوت...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # تشغيل البوت
    try:
        bot = TelegramLinksBot()
        bot.run()
    except Exception as e:
        print(f"❌ خطأ فادح: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
