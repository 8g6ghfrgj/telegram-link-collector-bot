import asyncio
import logging
import sys
from typing import List, Dict
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
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
    stream=sys.stdout  # مهم لـ Render
)
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
db = Database()

# ===== إعداد خادم ويب بسيط للـ Health Check =====
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # إخفاء سجلات HTTP

def run_health_check_server():
    """تشغيل خادم للـ Health Check"""
    server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
    print("🌐 Health check server running on port 8080")
    server.serve_forever()

# ===== الفئة الرئيسية للبوت =====
class TelegramLinksBot:
    def __init__(self):
        self.scraping_tasks = {}
        self.current_selections = {}
        self.application = None
        
        # تشغيل خادم Health Check على Render
        if IS_RENDER:
            health_thread = threading.Thread(target=run_health_check_server, daemon=True)
            health_thread.start()
    
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
        
        🌐 **يعمل على: Render.com**
        ⚡ **الحالة: {'🟢 نشط' if IS_RENDER else '🔴 محلي'}**
        
        ✨ **المميزات:**
        ✅ إضافة حسابات تيليجرام (Session String فقط)
        ✅ جمع الروابط من القنوات والجروبات
        ✅ عرض الروابط داخل البوت
        ✅ تصدير الروابط كملف
        
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
           - لا حاجة لـ API_ID أو API_HASH
        
        **2. تجميع الروابط:**
           - اختر جلسة من القائمة
           - البوت سيجمع الروابط من كل القنوات
        
        **3. عرض الروابط:**
           - اختر نوع الروابط (تيليجرام، واتساب، الخ)
           - اختر السنة
           - استعرض الرواقع بصفحات
        
        **4. تصدير الروابط:**
           - داخل صفحة العرض، اضغط زر "📤 تصدير"
        
        ⚠️ **ملاحظات خاصة بـ Render:**
        - العملية محدودة بـ 5 قنوات في المرة
        - وقت التشغيل محدود (للباقة المجانية)
        - يتم حفظ البيانات تلقائياً
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    # ===== إدارة الجلسات =====
    async def add_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إضافة جلسة جديدة"""
        await update.message.reply_text(
            "📱 **إضافة جلسة جديدة**\n\n"
            "أرسل لي `session_string` الخاص بحسابك.\n"
            "يمكنك الحصول عليه من:\n"
            "- بوتات إنشاء الجلسات مثل @genStr_robot\n\n"
            "❌ **تحذير:** لا تشارك الجلسة مع أحد!\n\n"
            "أرسل `session_string` الآن أو /cancel للإلغاء:"
        )
        
        context.user_data['awaiting_session'] = True
    
    async def handle_session_string(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة session_string"""
        if not context.user_data.get('awaiting_session'):
            return
        
        session_string = update.message.text.strip()
        
        # التحقق من الطول
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
                await update.message.reply_text(f"❌ خطأ في حفظ الجلسة: {str(e)[:100]}")
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
                f"   📅 أضيفت: {session['created_at'][:19]}\n"
                f"   {status}\n"
                f"   ──────────────\n"
            )
        
        message += f"\n📊 **المجموع: {len(sessions)} جلسة**"
        
        keyboard = [
            [InlineKeyboardButton("🗑 حذف جلسة", callback_data="delete_session")],
            [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_sessions")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
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
        
        keyboard.append([InlineKeyboardButton("📊 حالة العمليات", callback_data="scraping_status")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def start_scraping(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: int):
        """بدء عملية تجميع الروابط"""
        user_id = update.effective_user.id
        
        # التحقق من عدم وجود عملية جارية
        if user_id in self.scraping_tasks:
            try:
                if not self.scraping_tasks[user_id].done():
                    await update.callback_query.answer(
                        "⚠️ لديك عملية جمع قائمة بالفعل!",
                        show_alert=True
                    )
                    return
            except:
                pass
        
        await update.callback_query.edit_message_text(
            "⏳ **جاري بدء عملية تجميع الروابط...**\n\n"
            f"⚡ **يعمل على: Render.com**\n"
            f"📊 **حدود:** 5 قنوات × 5000 رسالة\n"
            "⏱️ **الوقت:** ~2-5 دقائق\n\n"
            "سأرسل لك التحديثات هنا...",
            parse_mode='Markdown'
        )
        
        # بدء العملية في الخلفية
        task = asyncio.create_task(
            self._run_scraping(update, context, session_id, user_id)
        )
        self.scraping_tasks[user_id] = task
    
    async def _run_scraping(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          session_id: int, user_id: int):
        """تشغيل عملية الجمع"""
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
                     "📥 جاري جمع القنوات..."
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
            
            # تحديد عدد القنوات (محدود على Render)
            max_chats = 5 if IS_RENDER else 10
            chats_to_scrape = chats[:max_chats]
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔍 **تم العثور على {len(chats)} قناة/جروب**\n"
                     f"📊 **سأجمع من:** {len(chats_to_scrape)} قناة\n\n"
                     f"بدء عملية المسح... ⏳"
            )
            
            # جمع الروابط من القنوات المحددة
            progress_msg = await context.bot.send_message(
                chat_id=chat_id,
                text="🔄 **جاري العمل...**\n"
                     "0% - بداية العملية"
            )
            
            results = []
            for i, chat in enumerate(chats_to_scrape, 1):
                # تحديث التقدم
                percent = int((i / len(chats_to_scrape)) * 100)
                await progress_msg.edit_text(
                    f"🔄 **جاري العمل...**\n"
                    f"{percent}% - جاري القناة {i}/{len(chats_to_scrape)}\n"
                    f"📍 {chat['title'][:30]}..."
                )
                
                result = await scraper.scrape_chat(chat['id'], session_id)
                results.append(result)
                
                # تأخير بين القنوات
                await asyncio.sleep(2)
            
            # إرسال النتائج
            successful = sum(1 for r in results if r['success'])
            total_msgs = sum(r.get('total_messages', 0) for r in results)
            total_links = sum(r.get('total_links', 0) for r in results)
            
            summary = (
                f"🎉 **اكتملت عملية تجميع الروابط!**\n\n"
                f"📊 **الإحصائيات:**\n"
                f"• عدد القنوات: {len(results)}\n"
                f"• نجح: {successful} | فشل: {len(results) - successful}\n"
                f"• إجمالي الرسائل: {total_msgs:,}\n"
                f"• إجمالي الروابط: {total_links:,}\n\n"
                f"✅ **تم حفظ جميع الروابط.**\n"
                f"يمكنك الآن عرضها من القائمة الرئيسية."
            )
            
            await progress_msg.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text=summary,
                parse_mode='Markdown'
            )
            
            await scraper.disconnect()
            
        except asyncio.CancelledError:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏹️ **تم إلغاء العملية!**"
            )
        except Exception as e:
            error_msg = f"❌ **حدث خطأ:**\n\n{str(e)[:200]}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=error_msg
            )
        finally:
            # تنظيف المهمة
            if user_id in self.scraping_tasks:
                try:
                    self.scraping_tasks[user_id].cancel()
                    del self.scraping_tasks[user_id]
                except:
                    pass
    
    # ===== عرض الروابط =====
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
            [
                InlineKeyboardButton("📂 الكل", callback_data="link_type_all"),
                InlineKeyboardButton("📊 إحصائيات", callback_data="links_stats")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        total_links = db.get_links_count()
        message = f"📊 **عرض الروابط المجمعة**\n\n"
        message += f"🔗 **إجمالي الروابط:** {total_links:,}\n"
        message += f"📅 **آخر تحديث:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        message += "**اختر نوع الروابط:**"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def show_links_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
        """عرض صفحة من الروابط"""
        user_id = update.effective_user.id
        
        if user_id not in self.current_selections:
            await update.callback_query.answer("❌ ابدأ من القائمة!", show_alert=True)
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
            await update.callback_query.edit_message_text(
                "📭 **لا توجد روابط!**\n\n"
                "إما أن:\n"
                "1. لم تجمع الروابط بعد\n"
                "2. لا توجد روابط من النوع المحدد\n"
                "3. جرب نوعاً أو سنة أخرى",
                parse_mode='Markdown'
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
            'all': 'الكل'
        }
        
        type_name = type_names.get(link_type, link_type)
        year_display = str(year) if year else "كل السنوات"
        
        message = f"📋 **الروابط ({type_name} - {year_display})**\n\n"
        message += f"📄 الصفحة: {page}/{total_pages}\n"
        message += f"🔗 المجموع: {total_count:,}\n"
        message += "─" * 30 + "\n\n"
        
        # عرض الروابط
        for i, link in enumerate(links, 1):
            index = (page - 1) * LINKS_PER_PAGE + i
            message += f"**{index}. {link['link']}**\n"
            if link['chat_title']:
                message += f"   📍 {link['chat_title'][:30]}\n"
            message += "\n"
        
        # أزرار إضافية
        extra_buttons = [
            [InlineKeyboardButton("📤 تصدير كملف", callback_data=f"export_{link_type}_{year or 'all'}_{page}")]
        ]
        
        reply_markup = self.create_pagination_keyboard(page, total_pages, extra_buttons)
        
        await update.callback_query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    
    # ===== باقي الدوال =====
    # (نفس دوال النسخة السابقة مع تعديلات بسيطة)
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة Callback Queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "back_to_menu":
                await self.send_main_menu(update, context)
            
            elif data == "refresh_sessions":
                sessions = db.get_all_sessions()
                if not sessions:
                    await query.edit_message_text("📭 لا توجد جلسات")
                    return
                
                message = "📱 **الجلسات المضافة:**\n\n"
                for i, session in enumerate(sessions, 1):
                    status = "🟢 نشط" if session['is_active'] else "🔴 غير نشط"
                    message += f"**{i}. {session['phone_number']}**\n"
                    message += f"   📅 {session['created_at'][:19]}\n"
                    message += f"   {status}\n   ─────\n"
                
                keyboard = [
                    [InlineKeyboardButton("🗑 حذف جلسة", callback_data="delete_session")],
                    [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_sessions")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]
                ]
                
                await query.edit_message_text(
                    message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            
            elif data.startswith("scrape_session_"):
                session_id = int(data.split("_")[2])
                await self.start_scraping(update, context, session_id)
            
            elif data.startswith("link_type_"):
                link_type = data.split("_")[2]
                user_id = update.effective_user.id
                self.current_selections[user_id] = {'type': link_type, 'year': None}
                
                # أزرار السنوات
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
                
                keyboard.append([InlineKeyboardButton("📆 الكل", callback_data="link_year_all")])
                keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="links_menu")])
                
                type_names = {
                    'telegram': 'تيليجرام', 'whatsapp': 'واتساب',
                    'website': 'مواقع', 'youtube': 'يوتيوب',
                    'instagram': 'انستجرام', 'twitter': 'تويتر',
                    'all': 'الكل'
                }
                
                await query.edit_message_text(
                    f"✅ **تم اختيار: {type_names.get(link_type, link_type)}**\n\n"
                    "**اختر السنة:**",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            
            elif data.startswith("link_year_"):
                year = data.split("_")[2]
                user_id = update.effective_user.id
                self.current_selections[user_id]['year'] = year if year != 'all' else None
                await self.show_links_page(update, context, 1)
            
            elif data.startswith("page_"):
                page = int(data.split("_")[1])
                await self.show_links_page(update, context, page)
            
            elif data.startswith("export_"):
                parts = data.split("_")
                link_type = parts[1]
                year = parts[2]
                year_int = int(year) if year != 'all' and year.isdigit() else None
                
                # الحصول على كل الروابط
                links, total_count = db.get_links(
                    link_type=link_type if link_type != 'all' else None,
                    year=year_int,
                    page=1,
                    per_page=10000
                )
                
                if not links:
                    await query.answer("❌ لا توجد روابط!", show_alert=True)
                    return
                
                # إنشاء ملف
                type_names = {
                    'telegram': 'تيليجرام', 'whatsapp': 'واتساب',
                    'website': 'مواقع', 'youtube': 'يوتيوب',
                    'instagram': 'انستجرام', 'twitter': 'تويتر',
                    'all': 'الكل'
                }
                
                type_name = type_names.get(link_type, link_type)
                year_display = year if year != 'all' else 'كل_السنوات'
                filename = f"links_{type_name}_{year_display}.txt"
                
                file_content = f"روابط {type_name} - {year_display}\n"
                file_content += f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                file_content += f"العدد: {len(links):,}\n"
                file_content += "="*50 + "\n\n"
                
                for i, link in enumerate(links, 1):
                    file_content += f"{i}. {link['link']}\n"
                
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=file_content.encode('utf-8'),
                    filename=filename,
                    caption=f"✅ تم تصدير {len(links):,} رابط"
                )
                
                await query.answer(f"📤 تم إرسال الملف")
            
            else:
                await query.edit_message_text(
                    "⚙️ **هذه الخاصية قيد التطوير...**\n\n"
                    "استخدم /start للعودة",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(
                f"❌ **خطأ:**\n\n{str(e)[:100]}",
                parse_mode='Markdown'
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
                "🤔 لم أفهم رسالتك.\n"
                "استخدم الأزرار أدناه أو /start"
            )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء أي عملية"""
        if 'awaiting_session' in context.user_data:
            context.user_data['awaiting_session'] = False
        
        await update.message.reply_text("✅ تم الإلغاء")
        await self.send_main_menu(update, context)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأخطاء"""
        logger.error(f"Error: {context.error}")
        
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id if update else None,
                text="❌ **حدث خطأ!**\n\nجرب مرة أخرى لاحقاً."
            )
        except:
            pass
    
    def run(self):
        """تشغيل البوت"""
        print(f"🚀 بدء تشغيل البوت على Render: {IS_RENDER}")
        print(f"🤖 البوت: {BOT_TOKEN[:15]}...")
        
        # إنشاء التطبيق
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة المعالجات
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel))
        
        # Callback Queries
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # الرسائل النصية
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # معالجة الأخطاء
        self.application.add_error_handler(self.error_handler)
        
        # بدء البوت
        print("✅ البوت يعمل الآن!")
        print("📡 في انتظار الرسائل...")
        
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

# تشغيل البوت
if __name__ == "__main__":
    # التحقق من وجود التوكن
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        print("❌ خطأ: لم يتم تعيين BOT_TOKEN!")
        print("📝 قم بإضافته في متغيرات Render")
        sys.exit(1)
    
    bot = TelegramLinksBot()
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 إيقاف البوت...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ خطأ فادح: {e}")
        sys.exit(1)
