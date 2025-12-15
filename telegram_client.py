import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import re
from typing import List, Dict
from datetime import datetime
import aiohttp

from database import Database

class TelegramScraper:
    def __init__(self, session_string: str):
        self.session_string = session_string
        self.client = None
        self.db = Database()
        self.link_pattern = re.compile(
            r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.\-?=&%#+!@$*]*', 
            re.IGNORECASE
        )
    
    async def connect(self) -> bool:
        """الاتصال بالعميل بدون API"""
        try:
            # استخدام session string فقط
            self.client = TelegramClient(
                StringSession(self.session_string),
                api_id=2040,  # قيمة ثابتة للتوافق
                api_hash='b18441a1ff607e10a989891a5462e627'  # قيمة ثابتة
            )
            
            # إعدادات خاصة لـ Render
            self.client.session.set_dc(2, '149.154.167.40', 443)
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                print("❌ الجلسة غير مصرح بها")
                return False
            
            # اختبار الاتصال
            try:
                me = await self.client.get_me()
                print(f"✅ Connected as: {me.phone}")
                return True
            except Exception as e:
                print(f"❌ Error getting user: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    async def get_all_chats(self) -> List[Dict]:
        """الحصول على كل القنوات والجروبات"""
        if not self.client:
            return []
        
        chats = []
        try:
            async for dialog in self.client.iter_dialogs(limit=200):
                if dialog.is_channel or dialog.is_group:
                    chats.append({
                        'id': dialog.id,
                        'title': dialog.title,
                        'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None,
                        'participants_count': getattr(dialog.entity, 'participants_count', 0)
                    })
        except Exception as e:
            print(f"Error getting chats: {e}")
        
        return chats
    
    async def scrape_chat(self, chat_id: int, session_id: int) -> Dict:
        """جمع الروابط من قناة/جروب معين"""
        if not self.client:
            return {'success': False, 'error': 'Client not connected'}
        
        total_links = 0
        total_messages = 0
        
        try:
            # الحصول على معلومات القناة
            chat = await self.client.get_entity(chat_id)
            chat_title = chat.title
            
            # تسجيل بداية العملية
            self.db.add_scraping_log(chat_id, session_id, 'started', 0, 0)
            
            print(f"📥 بدء جمع الروابط من: {chat_title}")
            
            # جمع الرسائل (من القديم إلى الجديد)
            async for message in self.client.iter_messages(
                chat, 
                reverse=True,
                limit=10000  # حد للحماية
            ):
                total_messages += 1
                
                if message.text:
                    links = self.link_pattern.findall(message.text)
                    
                    for link in links:
                        if message.date:
                            year = message.date.year
                        else:
                            year = datetime.now().year
                        
                        # إضافة الرابط
                        if self.db.add_link(link, year, chat_id, message.id, session_id):
                            total_links += 1
                
                # تحديث كل 100 رسالة
                if total_messages % 100 == 0:
                    print(f"   ↳ معالجة {total_messages} رسالة، وجد {total_links} رابط")
                    
                # تحقق من الوقت المستغرق على Render
                if total_messages > 5000:  # حد آمن
                    break
            
            # إضافة القناة إلى قاعدة البيانات
            self.db.add_chat(chat_id, chat_title, 
                            getattr(chat, 'username', None), 
                            session_id)
            
            # تسجيل اكتمال العملية
            self.db.add_scraping_log(chat_id, session_id, 'completed', 
                                   total_messages, total_links)
            
            print(f"✅ اكتمل جمع {chat_title}: {total_messages} رسالة، {total_links} رابط")
            
            return {
                'success': True,
                'chat_title': chat_title,
                'total_messages': total_messages,
                'total_links': total_links
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ خطأ في جمع {chat_id}: {error_msg}")
            
            self.db.add_scraping_log(chat_id, session_id, 'failed', 
                                   total_messages, total_links, error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'total_messages': total_messages,
                'total_links': total_links
            }
    
    async def scrape_all_chats(self, session_id: int) -> Dict:
        """جمع الروابط من كل القنوات"""
        chats = await self.get_all_chats()
        results = []
        
        print(f"🔍 بدء جمع الروابط من {len(chats)} قناة/جروب")
        
        for chat in chats[:5]:  # حد 5 قنوات على Render للحماية
            result = await self.scrape_chat(chat['id'], session_id)
            results.append(result)
            
            # تأخير بين القنوات
            await asyncio.sleep(3)
        
        # حساب الإحصائيات
        successful = sum(1 for r in results if r['success'])
        total_msgs = sum(r.get('total_messages', 0) for r in results)
        total_links = sum(r.get('total_links', 0) for r in results)
        
        return {
            'total_chats': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'total_messages': total_msgs,
            'total_links': total_links,
            'results': results
        }
    
    async def disconnect(self):
        """قطع الاتصال"""
        if self.client:
            try:
                await self.client.disconnect()
            except:
                pass
