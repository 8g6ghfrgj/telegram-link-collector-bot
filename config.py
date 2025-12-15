import os
from dotenv import load_dotenv

load_dotenv()

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN")  # حرك BotFather فقط

# إعدادات أخرى
DB_NAME = "telegram_links_bot.db"
LINKS_PER_PAGE = 20
SUPPORTED_LINK_TYPES = {
    'telegram': ['t.me', 'telegram.me'],
    'whatsapp': ['wa.me', 'whatsapp.com'],
    'website': ['http://', 'https://'],
    'youtube': ['youtube.com', 'youtu.be'],
    'instagram': ['instagram.com'],
    'twitter': ['twitter.com', 'x.com']
}
