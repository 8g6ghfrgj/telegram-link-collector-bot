import asyncio
import logging
from typing import List, Dict
from datetime import datetime

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

from config import BOT_TOKEN, LINKS_PER_PAGE
from database import Database
from telegram_client import TelegramScraper

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
db = Database()

class TelegramLinksBot:
    def __init__(self):
        self.scraping_tasks = {}  # لتتبع المهام الجارية
        self.current_selections = {}  # لتخزين اختيارات المستخدمين
    
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
    
    def create_pagination_keyboard(self, page: int, total_pages: int, 
                                 extra_buttons: List = None) -> InlineKeyboardMarkup:
        """إنشاء أزرار التصفح"""
        keyboard = []
        
        if extra_buttons:
            keyboard.extend(extra_buttons)
        
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="current_page"))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")])
        
        return InlineKeyboardMarkup(keyboard)
    
    # ===== معالجات الأوامر =====
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بدء البوت"""
        user = update.effective_user
        welcome_msg = f"""
        🎉 أهلاً بك {user.first_name}!
        
        **بوت جمع الروابط من التليجرام**
        
        ✨ **المميزات:**
        ✅ إضافة حسابات تيليجرام
        ✅ جمع الروابط من القنوات والجروبات
        ✅ عرض الروابط داخل البوت
        ✅ تصدير الروابط كملف
        
        📌 **طريقة العمل:**
        1. أضف جلسة حسابك (Session String)
        2. ابدأ عملية تجميع الروابط
        3. استعرض الروابط المجمعة
        
        🚀 **لتبدأ، اختر من القائمة:**
        """
        
        await self.send_main_menu(update, context, welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مساعدة"""
        help_text = """
        📖 **دليل استخدام البوت:**
        
        **1. إضافة جلسة:**
           - احصل على `session_string` من حسابك
           - أرسله للبوت عند طلبه
        
        **2. تجميع الروابط:**
           - اختر جلسة من القائمة
           - البوت سيجمع الروابط تلقائياً
        
        **3. عرض الروابط:**
           - اختر نوع الروابط (تيليجرام، واتساب، الخ)
           - اختر السنة
           - استعرض الرواقع بصفحات
        
        **4. تصدير الروابط:**
           - داخل صفحة العرض، اضغط زر "📤 تصدير"
        
        ⚠️ **ملاحظات:**
        - العملية قد تستغرق وقتاً طويلاً للقنوات الكبيرة
        - تأكد من أن الحساب منضم للقنوات المطلوبة
        - يمكنك إيقاف البوت بأي وقت
        
        للمساعدة: @username
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    # ===== إدارة الجلسات =====
    async def add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إضافة جلسة جديدة"""
        await update.message.reply_text(
            "📱 **إضافة جلسة جديدة**\n\n"
            "أرسل لي `session_string` الخاص بحسابك.\n"
            "يمكنك الحصول عليه من:\n"
            "1. تطبيقات الطرف الثالث\n"
            "2. أو من بوتات إنشاء الجلسات\n\n"
            "❌ **تحذير:** لا تشارك الجلسة مع أحد!\n\n"
            "أرسل `session_string` الآن أو /cancel للإلغاء:"
        )
        
        context.user_data['awaiting_session'] = True
    
    async def handle_session_string(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة session_string"""
        if not context.user_data.get('awaiting_session'):
            return
        
        session_string = update.message.text.strip()
        user_id = update.effective_user.id
        
        # اختبار الجلسة
        await update.message.reply_text("🔍 جاري اختبار الجلسة...")
        
        scraper = TelegramScraper(session_string)
        connected = await scraper.connect()
        
        if connected:
            # الحصول على رقم الهاتف
            try:
                me = await scraper.client.get_me()
                phone_number = me.phone
                
                # حفظ الجلسة
                if db.add_session(session_string, phone_number):
                    await update.message.reply_text(
                        f"✅ **تم إضافة الجلسة بنجاح!**\n\n"
                        f"📞 الرقم: `{phone_number}`\n"
                        f"🆔 ID: `{me.id}`\n"
                        f"👤 الاسم: {me.first_name or ''} {me.last_name or ''}\n\n"
                        "يمكنك الآن استخدام الجلسة لتجميع الروابط.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("⚠️ هذه الجلسة مضافه مسبقاً!")
            except Exception as e:
                await update.message.reply_text(f"❌ خطأ في حفظ الجلسة: {e}")
            finally:
                await scraper.disconnect()
        else:
            await update.message.reply_text(
                "❌ **الجلسة غير صالحة!**\n\n"
                "تأكد من:\n"
                "1. صحة `session_string`\n"
                "2. أن الحساب مفعل\n"
                "3. حاول الحصول على جلسة جديدة"
            )
        
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
            message += (
                f"**{i}. {session['phone_number']}**\n"
                f"   📅 أضيفت: {session['created_at']}\n"
                f"   {status}\n"
                f"   ──────────────\n"
            )
        
        message += f"\n📊 **المجموع: {len(sessions)} جلسة**"
        
        # أزرار إدارة الجلسات
        keyboard = [
            [InlineKeyboardButton("🗑 حذف جلسة", callback_data="delete_session")],
            [InlineKeyboardButton("🔄 تحديث القائمة", callback_data="refresh_sessions")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def delete_session_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض قائمة حذف الجلسات"""
        sessions = db.get_all_sessions()
        
        if not sessions:
            await update.callback_query.answer("لا توجد جلسات للحذف!", show_alert=True)
            return
        
        keyboard = []
        for session in sessions:
            btn_text = f"🗑 {session['phone_number']}"
            callback_data = f"confirm_delete_{session['id']}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_sessions")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "**اختر الجلسة المراد حذفها:**\n⚠️ سيتم حذف جميع روابط هذه الجلسة أيضاً!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def confirm_delete_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: int):
        """تأكيد حذف الجلسة"""
        keyboard = [
            [
                InlineKeyboardButton("✅ نعم، احذف", callback_data=f"execute_delete_{session_id}"),
                InlineKeyboardButton("❌ لا، إلغاء", callback_data="back_to_sessions")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "⚠️ **هل أنت متأكد من حذف هذه الجلسة؟**\n"
            "سيتم حذف جميع الروابط المرتبطة بها أيضاً!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def execute_delete_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: int):
        """تنفيذ حذف الجلسة"""
        if db.delete_session(session_id):
            await update.callback_query.edit_message_text(
                "✅ **تم حذف الجلسة بنجاح!**",
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ **فشل في حذف الجلسة!**",
                parse_mode='Markdown'
            )
        
        await asyncio.sleep(2)
        await self.show_sessions_callback(update, context)
    
    # ===== تجميع الروابط =====
    async def start_scraping_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة تجميع الروابط"""
        sessions = db.get_all_sessions()
        
        if not sessions:
            await update.message.reply_text(
                "❌ **لا توجد جلسات!**\n\n"
                "أضف جلسة أولاً من القائمة الرئيسية."
            )
            return
        
        message = "🔍 **تجميع الروابط**\n\n"
        message += "اختر الجلسة التي تريد جمع الروابط منها:\n\n"
        
        keyboard = []
        for session in sessions:
            if session['is_active']:
                btn_text = f"📱 {session['phone_number']}"
                callback_data = f"scrape_session_{session['id']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        
        if not keyboard:
            await update.message.reply_text("❌ لا توجد جلسات نشطة!")
            return
        
        keyboard.append([InlineKeyboardButton("📊 حالة العمليات السابقة", callback_data="scraping_status")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def start_scraping(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: int):
        """بدء عملية تجميع الروابط"""
        user_id = update.effective_user.id
        
        # التحقق من عدم وجود عملية جارية
        if user_id in self.scraping_tasks and not self.scraping_tasks[user_id].done():
            await update.callback_query.answer(
                "⚠️ لديك عملية جمع قائمة بالفعل!",
                show_alert=True
            )
            return
        
        await update.callback_query.edit_message_text(
            "⏳ **جاري بدء عملية تجميع الروابط...**\n\n"
            "هذه العملية قد تستغرق وقتاً طويلاً حسب عدد القنوات والرسائل.\n"
            "سأرسل لك تحديثات أثناء العملية.",
            parse_mode='Markdown'
        )
        
        # بدء العملية في الخلفية
        task = asyncio.create_task(
            self._run_scraping(update, context, session_id, user_id)
        )
        self.scraping_tasks[user_id] = task
    
    async def _run_scraping(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          session_id: int, user_id: int):
        """تشغيل عملية الجمع (في الخلفية)"""
        chat_id = update.effective_chat.id
        
        try:
            # الحصول على session_string
            session_string = db.get_session_string(session_id)
            if not session_string:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ **خطأ:** لم أجد session_string للجلسة!"
                )
                return
            
            # الاتصال
            scraper = TelegramScraper(session_string)
            connected = await scraper.connect()
            
            if not connected:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ **فشل الاتصال بالجلسة!**\nتحقق من صحة الجلسة."
                )
                return
            
            # إعلام البدء
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ **تم الاتصال بنجاح!**\n\n"
                     "📥 بدء جمع الروابط من جميع القنوات والجروبات...\n"
                     "⏳ قد تستغرق العملية عدة دقائق."
            )
            
            # جمع القنوات أولاً
            chats = await scraper.get_all_chats()
            
            if not chats:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="📭 **لا توجد قنوات أو جروبات في هذه الجلسة!**"
                )
                await scraper.disconnect()
                return
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔍 **تم العثور على {len(chats)} قناة/جروب**\n\n"
                     "بدء عملية المسح..."
            )
            
            # جمع الروابط من كل القنوات
            result = await scraper.scrape_all_chats(session_id)
            
            # إرسال النتائج
            summary = (
                f"🎉 **اكتملت عملية تجميع الروابط!**\n\n"
                f"📊 **الإحصائيات:**\n"
                f"• عدد القنوات: {result['total_chats']}\n"
                f"• نجح: {result['successful']} | فشل: {result['failed']}\n"
                f"• إجمالي الرسائل: {result['total_messages']:,}\n"
                f"• إجمالي الروابط: {result['total_links']:,}\n\n"
                f"✅ **تم حفظ جميع الروابط في قاعدة البيانات.**\n"
                f"يمكنك الآن عرضها من القائمة الرئيسية."
            )
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=summary,
                parse_mode='Markdown'
            )
            
            # إرسال تفاصيل القنوات
            details = "📋 **تفاصيل القنوات:**\n\n"
            for res in result['results']:
                status = "✅" if res['success'] else "❌"
                details += f"{status} {res.get('chat_title', 'Unknown')}\n"
                details += f"   📨 {res.get('total_messages', 0):,} رسالة | "
                details += f"🔗 {res.get('total_links', 0):,} رابط\n"
                if not res['success']:
                    details += f"   ⚠️ {res.get('error', '')}\n"
                details += "\n"
            
            # تقسيم الرسالة إذا كانت طويلة
            if len(details) > 4000:
                parts = [details[i:i+4000] for i in range(0, len(details), 4000)]
                for part in parts:
                    await context.bot.send_message(chat_id=chat_id, text=part)
            else:
                await context.bot.send_message(chat_id=chat_id, text=details)
            
            await scraper.disconnect()
            
        except Exception as e:
            error_msg = f"❌ **حدث خطأ غير متوقع:**\n\n{str(e)}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=error_msg
            )
        finally:
            # تنظيف المهمة
            if user_id in self.scraping_tasks:
                del self.scraping_tasks[user_id]
    
    async def show_scraping_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض حالة عمليات الجمع السابقة"""
        logs = db.get_last_scraping_status()
        
        if not logs:
            await update.callback_query.edit_message_text(
                "📭 **لا توجد عمليات جمع سابقة.**",
                parse_mode='Markdown'
            )
            return
        
        message = "📊 **آخر 10 عمليات جمع:**\n\n"
        
        for log in logs:
            status_icon = "✅" if log['status'] == 'completed' else "❌"
            message += (
                f"{status_icon} **{log['phone']}**\n"
                f"   📍 {log['chat_title'] or 'Unknown'}\n"
                f"   📨 {log['total_messages']:,} رسالة\n"
                f"   🔗 {log['links_found']:,} رابط\n"
                f"   🕒 {log['started_at']}\n"
            )
            
            if log['status'] == 'failed':
                message += f"   ⚠️ {log['error'][:50]}...\n"
            
            message += "   ──────────────\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="scraping_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    # ===== عرض الروابط =====
    async def show_links_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة عرض الروابط"""
        user_id = update.effective_user.id
        self.current_selections[user_id] = {'type': None, 'year': None}
        
        # أزرار أنواع الروابط
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
            [
                InlineKeyboardButton("📂 كل الأنواع", callback_data="link_type_all"),
                InlineKeyboardButton("📊 إحصائيات", callback_data="links_stats")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إحصائيات سريعة
        total_links = db.get_links_count()
        message = f"📊 **عرض الروابط المجمعة**\n\n"
        message += f"🔗 **إجمالي الروابط:** {total_links:,}\n"
        message += f"📅 **آخر تحديث:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        message += "**اختر نوع الروابط:**"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def select_link_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE, link_type: str):
        """اختيار نوع الروابط"""
        user_id = update.effective_user.id
        
        # حفظ الاختيار
        if user_id not in self.current_selections:
            self.current_selections[user_id] = {}
        
        self.current_selections[user_id]['type'] = link_type
        
        # أزرار السنوات (آخر 5 سنوات + كل السنوات)
        current_year = datetime.now().year
        years = list(range(current_year, current_year - 6, -1))
        
        keyboard = []
        row = []
        for year in years:
            row.append(InlineKeyboardButton(str(year), callback_data=f"link_year_{year}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("📆 كل السنوات", callback_data="link_year_all")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="links_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # نوع الرابط بالعربية
        type_names = {
            'telegram': 'تيليجرام',
            'whatsapp': 'واتساب', 
            'website': 'مواقع',
            'youtube': 'يوتيوب',
            'instagram': 'انستجرام',
            'twitter': 'تويتر',
            'all': 'كل الأنواع'
        }
        
        type_name = type_names.get(link_type, link_type)
        
        await update.callback_query.edit_message_text(
            f"✅ **تم اختيار: {type_name}**\n\n"
            "**الآن اختر السنة:**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def select_year(self, update: Update, context: ContextTypes.DEFAULT_TYPE, year):
        """اختيار السنة"""
        user_id = update.effective_user.id
        
        if user_id not in self.current_selections:
            await update.callback_query.answer("❌ حدث خطأ، ابدأ من جديد!", show_alert=True)
            await self.show_links_menu(update, context)
            return
        
        self.current_selections[user_id]['year'] = year if year != 'all' else None
        
        # عرض الصفحة الأولى
        await self.show_links_page(update, context, page=1)
    
    async def show_links_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
        """عرض صفحة من الروابط"""
        user_id = update.effective_user.id
        
        if user_id not in self.current_selections:
            await update.callback_query.answer("❌ ابدأ من القائمة!", show_alert=True)
            await self.show_links_menu(update, context)
            return
        
        link_type = self.current_selections[user_id]['type']
        year = self.current_selections[user_id]['year']
        
        # الحصول على الروابط
        links, total_count = db.get_links(
            link_type=link_type,
            year=year,
            page=page,
            per_page=LINKS_PER_PAGE
        )
        
        if not links:
            message = "📭 **لا توجد روابط!**\n\n"
            message += "إما أن:\n"
            message += "1. لم تجمع الروابط بعد\n"
            message += "2. لا توجد روابط من النوع المحدد\n"
            message += "3. جرب نوعاً أو سنة أخرى"
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="links_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
        
        # حساب عدد الصفحات
        total_pages = (total_count + LINKS_PER_PAGE - 1) // LINKS_PER_PAGE
        
        # بناء الرسالة
        type_names = {
            'telegram': 'تيليجرام',
            'whatsapp': 'واتساب',
            'website': 'مواقع',
            'youtube': 'يوتيوب',
            'instagram': 'انستجرام',
            'twitter': 'تويتر',
            'all': 'جميع الأنواع'
        }
        
        type_name = type_names.get(link_type, link_type)
        year_display = str(year) if year else "كل السنوات"
        
        message = f"📋 **الروابط ({type_name} - {year_display})**\n\n"
        message += f"📄 الصفحة: {page}/{total_pages}\n"
        message += f"🔗 إجمالي الروابط: {total_count:,}\n"
        message += "─" * 30 + "\n\n"
        
        # عرض الروابط
        for i, link in enumerate(links, 1):
            index = (page - 1) * LINKS_PER_PAGE + i
            message += f"**{index}. {link['link']}**\n"
            message += f"   📍 {link['chat_title'] or 'غير معروف'}\n"
            message += f"   📅 {link['found_at']}\n"
            message += f"   👤 {link['phone'] or 'غير معروف'}\n"
            message += "\n"
        
        # أزرار إضافية
        extra_buttons = [
            [InlineKeyboardButton("📤 تصدير كملف", callback_data=f"export_{link_type}_{year or 'all'}_{page}")]
        ]
        
        # إنشاء أزرار التصفح
        reply_markup = self.create_pagination_keyboard(page, total_pages, extra_buttons)
        
        await update.callback_query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    
    async def export_links(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         link_type: str, year: str, page: int):
        """تصدير الروابط كملف"""
        user_id = update.effective_user.id
        
        # تحويل year
        year_int = int(year) if year != 'all' and year.isdigit() else None
        
        # الحصول على كل الروابط (بدون صفحة)
        links, total_count = db.get_links(
            link_type=link_type if link_type != 'all' else None,
            year=year_int,
            page=1,
            per_page=1000000  # عدد كبير للحصول على كل الروابط
        )
        
        if not links:
            await update.callback_query.answer("❌ لا توجد روابط للتصدير!", show_alert=True)
            return
        
        # إنشاء ملف TXT
        type_names = {
            'telegram': 'تيليجرام',
            'whatsapp': 'واتساب',
            'website': 'مواقع',
            'youtube': 'يوتيوب',
            'instagram': 'انستجرام',
            'twitter': 'تويتر',
            'all': 'جميع_الأنواع'
        }
        
        type_name = type_names.get(link_type, link_type)
        year_display = year if year != 'all' else 'كل_السنوات'
        filename = f"telegram_links_{type_name}_{year_display}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        
        # بناء محتوى الملف
        file_content = f"📋 روابط {type_name} - {year_display}\n"
        file_content += f"📅 تاريخ التصدير: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        file_content += f"🔗 إجمالي الروابط: {len(links):,}\n"
        file_content += "=" * 50 + "\n\n"
        
        for i, link in enumerate(links, 1):
            file_content += f"{i}. {link['link']}\n"
            file_content += f"   📍 المصدر: {link['chat_title'] or 'غير معروف'}\n"
            file_content += f"   📅 التاريخ: {link['found_at']}\n"
            file_content += f"   👤 الحساب: {link['phone'] or 'غير معروف'}\n\n"
        
        # إرسال الملف
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=file_content.encode('utf-8'),
            filename=filename,
            caption=f"✅ **تم تصدير {len(links):,} رابط**\n\n"
                   f"📁 الملف: `{filename}`\n"
                   f"📊 النوع: {type_name}\n"
                   f"📅 السنة: {year_display}",
            parse_mode='Markdown'
        )
        
        await update.callback_query.answer(f"✅ تم إرسال الملف بـ {len(links):,} رابط")
    
    async def show_links_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إحصائيات الروابط"""
        # إحصائيات حسب النوع
        from config import SUPPORTED_LINK_TYPES
        
        stats_text = "📊 **إحصائيات الروابط**\n\n"
        
        for link_type in SUPPORTED_LINK_TYPES.keys():
            count = db.get_links_count(link_type)
            if count > 0:
                stats_text += f"• {link_type}: {count:,} رابط\n"
        
        # إحصائيات حسب السنة
        stats_text += "\n📅 **حسب السنة:**\n"
        
        # استعلام للحصول على السنوات المميزة
        db.cursor.execute("SELECT year, COUNT(*) FROM links GROUP BY year ORDER BY year DESC")
        year_stats = db.cursor.fetchall()
        
        for year, count in year_stats:
            stats_text += f"• {year}: {count:,} رابط\n"
        
        # الإجمالي
        total = db.get_links_count()
        stats_text += f"\n📈 **الإجمالي: {total:,} رابط**\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="links_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            stats_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    # ===== معالجة Callback Queries =====
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة كل Callback Queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "back_to_menu":
                await self.send_main_menu(update, context)
            
            elif data == "refresh_sessions":
                await self.show_sessions(update, context)
            
            elif data == "back_to_sessions":
                await self.show_sessions_callback(update, context)
            
            elif data == "delete_session":
                await self.delete_session_prompt(update, context)
            
            elif data.startswith("confirm_delete_"):
                session_id = int(data.split("_")[2])
                await self.confirm_delete_session(update, context, session_id)
            
            elif data.startswith("execute_delete_"):
                session_id = int(data.split("_")[2])
                await self.execute_delete_session(update, context, session_id)
            
            elif data == "scraping_menu":
                await self.start_scraping_menu(update, context)
            
            elif data == "scraping_status":
                await self.show_scraping_status(update, context)
            
            elif data.startswith("scrape_session_"):
                session_id = int(data.split("_")[2])
                await self.start_scraping(update, context, session_id)
            
            elif data == "links_menu":
                await self.show_links_menu(update, context)
            
            elif data == "links_stats":
                await self.show_links_stats(update, context)
            
            elif data.startswith("link_type_"):
                link_type = data.split("_")[2]
                await self.select_link_type(update, context, link_type)
            
            elif data.startswith("link_year_"):
                year = data.split("_")[2]
                await self.select_year(update, context, year)
            
            elif data.startswith("page_"):
                page = int(data.split("_")[1])
                await self.show_links_page(update, context, page)
            
            elif data.startswith("export_"):
                parts = data.split("_")
                if len(parts) >= 4:
                    link_type = parts[1]
                    year = parts[2]
                    page = int(parts[3]) if len(parts) > 3 else 1
                    await self.export_links(update, context, link_type, year, page)
            
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            await query.edit_message_text(
                f"❌ **حدث خطأ:**\n\n{str(e)[:200]}",
                parse_mode='Markdown'
            )
    
    async def show_sessions_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض الجلسات (لـ callback)"""
        sessions = db.get_all_sessions()
        
        if not sessions:
            await update.callback_query.edit_message_text(
                "📭 لا توجد جلسات مضافة بعد.",
                parse_mode='Markdown'
            )
            return
        
        message = "📱 **الجلسات المضافة:**\n\n"
        
        for i, session in enumerate(sessions, 1):
            status = "🟢 نشط" if session['is_active'] else "🔴 غير نشط"
            message += (
                f"**{i}. {session['phone_number']}**\n"
                f"   📅 أضيفت: {session['created_at']}\n"
                f"   {status}\n"
                f"   ──────────────\n"
            )
        
        message += f"\n📊 **المجموع: {len(sessions)} جلسة**"
        
        # أزرار إدارة الجلسات
        keyboard = [
            [InlineKeyboardButton("🗑 حذف جلسة", callback_data="delete_session")],
            [InlineKeyboardButton("🔄 تحديث القائمة", callback_data="refresh_sessions")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            message, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
    
    # ===== معالجة الرسائل النصية =====
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
            # إحصائيات سريعة
            total_links = db.get_links_count()
            total_sessions = len(db.get_all_sessions())
            total_chats = len(db.get_all_chats())
            
            stats = (
                f"📈 **إحصائيات البوت**\n\n"
                f"🔗 **الروابط:** {total_links:,}\n"
                f"👥 **الجلسات:** {total_sessions}\n"
                f"📢 **القنوات:** {total_chats}\n\n"
                f"🕒 **آخر تحديث:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            )
            
            await update.message.reply_text(stats, parse_mode='Markdown')
        
        elif message_text == "❓ المساعدة":
            await self.help_command(update, context)
        
        elif context.user_data.get('awaiting_session'):
            await self.handle_session_string(update, context)
        
        else:
            await update.message.reply_text(
                "🤔 لم أفهم رسالتك.\n"
                "استخدم القائمة أدناه أو /start للبدء."
            )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء أي عملية"""
        if 'awaiting_session' in context.user_data:
            context.user_data['awaiting_session'] = False
        
        await update.message.reply_text(
            "✅ تم الإلغاء.",
            reply_markup=None
        )
        await self.send_main_menu(update, context)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأخطاء"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ **حدث خطأ غير متوقع!**\n\n"
                     "الخطأ تم تسجيله. جرب مرة أخرى لاحقاً."
            )
        except:
            pass
    
    def run(self):
        """تشغيل البوت"""
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة المعالجات
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("cancel", self.cancel))
        
        # Callback Queries
        application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # الرسائل النصية
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # معالجة الأخطاء
        application.add_error_handler(self.error_handler)
        
        # بدء البوت
        print("🤖 البوت يعمل الآن...")
        print("📱 اضغط Ctrl+C لإيقافه")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)

# تشغيل البوت
if __name__ == "__main__":
    bot = TelegramLinksBot()
    bot.run()
