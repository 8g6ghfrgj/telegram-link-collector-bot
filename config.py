import os
from dotenv import load_dotenv

load_dotenv()

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN")  # حرك BotFather
API_ID = int(os.getenv("API_ID", 123456))  # من my.telegram.org
API_HASH = os.getenv("API_HASH", "your_api_hash")

# إعدادات قاعدة البيانات
DB_NAME = "telegram_links_bot.db"

# إعدادات أخرى
LINKS_PER_PAGE = 20  # عدد الروابط في كل صفحة
SCRAPE_LIMIT = None  # عدد الرسائل المسحوبة (None = كل الرسائل)
SUPPORTED_LINK_TYPES = {
    'telegram': ['t.me', 'telegram.me'],
    'whatsapp': ['wa.me', 'whatsapp.com'],
    'website': ['http://', 'https://'],
    'youtube': ['youtube.com', 'youtu.be'],
    'instagram': ['instagram.com'],
    'twitter': ['twitter.com', 'x.com']
}
