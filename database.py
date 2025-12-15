import sqlite3
import json
from datetime import datetime
import hashlib
from typing import List, Dict, Optional, Tuple

class Database:
    def __init__(self, db_name="telegram_links_bot.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        """إنشاء الجداول الأساسية"""
        # جدول الجلسات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_string TEXT UNIQUE NOT NULL,
                phone_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # جدول القنوات/الجروبات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                title TEXT NOT NULL,
                username TEXT,
                session_id INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        
        # جدول الروابط
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_hash TEXT UNIQUE NOT NULL,
                original_link TEXT NOT NULL,
                link_type TEXT NOT NULL,
                year INTEGER NOT NULL,
                chat_id INTEGER,
                message_id INTEGER,
                session_id INTEGER,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats (chat_id),
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        
        # جدول سجل العمليات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraping_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                session_id INTEGER,
                status TEXT,
                total_messages INTEGER,
                links_found INTEGER,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                error_message TEXT
            )
        ''')
        
        self.conn.commit()
    
    # === إدارة الجلسات ===
    def add_session(self, session_string: str, phone_number: str = None) -> bool:
        """إضافة جلسة جديدة"""
        try:
            self.cursor.execute(
                "INSERT INTO sessions (session_string, phone_number) VALUES (?, ?)",
                (session_string, phone_number)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_all_sessions(self) -> List[Dict]:
        """الحصول على كل الجلسات"""
        self.cursor.execute(
            "SELECT id, phone_number, created_at, is_active FROM sessions ORDER BY created_at DESC"
        )
        sessions = self.cursor.fetchall()
        return [
            {
                'id': s[0],
                'phone_number': s[1],
                'created_at': s[2],
                'is_active': bool(s[3])
            }
            for s in sessions
        ]
    
    def delete_session(self, session_id: int) -> bool:
        """حذف جلسة"""
        try:
            self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except:
            return False
    
    def get_session_string(self, session_id: int) -> Optional[str]:
        """الحصول على session string"""
        self.cursor.execute(
            "SELECT session_string FROM sessions WHERE id = ?",
            (session_id,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    # === إدارة القنوات ===
    def add_chat(self, chat_id: int, title: str, username: str, session_id: int):
        """إضافة قناة/جروب"""
        try:
            self.cursor.execute(
                """INSERT OR IGNORE INTO chats (chat_id, title, username, session_id) 
                   VALUES (?, ?, ?, ?)""",
                (chat_id, title, username, session_id)
            )
            self.conn.commit()
        except:
            pass
    
    def get_chats_by_session(self, session_id: int) -> List[Dict]:
        """الحصول على قنوات جلسة معينة"""
        self.cursor.execute(
            "SELECT chat_id, title, username FROM chats WHERE session_id = ?",
            (session_id,)
        )
        chats = self.cursor.fetchall()
        return [
            {'chat_id': c[0], 'title': c[1], 'username': c[2]}
            for c in chats
        ]
    
    def get_all_chats(self) -> List[Dict]:
        """الحصول على كل القنوات"""
        self.cursor.execute(
            "SELECT c.chat_id, c.title, c.username, s.phone_number FROM chats c LEFT JOIN sessions s ON c.session_id = s.id"
        )
        chats = self.cursor.fetchall()
        return [
            {'chat_id': c[0], 'title': c[1], 'username': c[2], 'phone': c[3]}
            for c in chats
        ]
    
    # === إدارة الروابط ===
    @staticmethod
    def generate_link_hash(link: str) -> str:
        """توليد هاش للرابط لمنع التكرار"""
        return hashlib.md5(link.encode()).hexdigest()
    
    @staticmethod
    def detect_link_type(link: str) -> str:
        """تحديد نوع الرابط"""
        from config import SUPPORTED_LINK_TYPES
        
        for link_type, domains in SUPPORTED_LINK_TYPES.items():
            for domain in domains:
                if domain in link.lower():
                    return link_type
        return 'other'
    
    def add_link(self, link: str, year: int, chat_id: int, message_id: int, session_id: int) -> bool:
        """إضافة رابط جديد (بمنع التكرار)"""
        link_hash = self.generate_link_hash(link)
        link_type = self.detect_link_type(link)
        
        try:
            self.cursor.execute(
                """INSERT OR IGNORE INTO links 
                   (link_hash, original_link, link_type, year, chat_id, message_id, session_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (link_hash, link, link_type, year, chat_id, message_id, session_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except:
            return False
    
    def get_links_count(self, link_type: str = None, year: int = None) -> int:
        """عدد الروابط مع فلتر"""
        query = "SELECT COUNT(*) FROM links WHERE 1=1"
        params = []
        
        if link_type and link_type != 'all':
            query += " AND link_type = ?"
            params.append(link_type)
        
        if year:
            query += " AND year = ?"
            params.append(year)
        
        self.cursor.execute(query, params)
        return self.cursor.fetchone()[0]
    
    def get_links(self, link_type: str = None, year: int = None, 
                  page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """الحصول على الروابط مع صفحة"""
        query = """
            SELECT l.original_link, l.link_type, l.year, l.found_at, 
                   c.title, s.phone_number 
            FROM links l
            LEFT JOIN chats c ON l.chat_id = c.chat_id
            LEFT JOIN sessions s ON l.session_id = s.id
            WHERE 1=1
        """
        params = []
        
        if link_type and link_type != 'all':
            query += " AND l.link_type = ?"
            params.append(link_type)
        
        if year:
            query += " AND l.year = ?"
            params.append(year)
        
        query += " ORDER BY l.found_at DESC LIMIT ? OFFSET ?"
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        
        self.cursor.execute(query, params)
        links = self.cursor.fetchall()
        
        return [
            {
                'link': l[0],
                'type': l[1],
                'year': l[2],
                'found_at': l[3],
                'chat_title': l[4],
                'phone': l[5]
            }
            for l in links
        ], self.get_links_count(link_type, year)
    
    # === سجل العمليات ===
    def add_scraping_log(self, chat_id: int, session_id: int, status: str, 
                         total_messages: int = 0, links_found: int = 0,
                         error_message: str = None):
        """إضافة سجل عملية جمع"""
        started_at = datetime.now().isoformat()
        
        if status == 'completed':
            finished_at = started_at
        else:
            finished_at = None
        
        self.cursor.execute(
            """INSERT INTO scraping_logs 
               (chat_id, session_id, status, total_messages, links_found, 
                started_at, finished_at, error_message) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, session_id, status, total_messages, links_found,
             started_at, finished_at, error_message)
        )
        self.conn.commit()
    
    def get_last_scraping_status(self, session_id: int = None) -> List[Dict]:
        """الحصول على آخر عمليات الجمع"""
        query = """
            SELECT s.phone_number, c.title, l.status, l.total_messages, 
                   l.links_found, l.started_at, l.finished_at, l.error_message
            FROM scraping_logs l
            LEFT JOIN sessions s ON l.session_id = s.id
            LEFT JOIN chats c ON l.chat_id = c.chat_id
            WHERE 1=1
        """
        params = []
        
        if session_id:
            query += " AND l.session_id = ?"
            params.append(session_id)
        
        query += " ORDER BY l.started_at DESC LIMIT 10"
        
        self.cursor.execute(query, params)
        logs = self.cursor.fetchall()
        
        return [
            {
                'phone': log[0],
                'chat_title': log[1],
                'status': log[2],
                'total_messages': log[3],
                'links_found': log[4],
                'started_at': log[5],
                'finished_at': log[6],
                'error': log[7]
            }
            for log in logs
        ]
    
    def close(self):
        """إغلاق الاتصال"""
        self.conn.close()
