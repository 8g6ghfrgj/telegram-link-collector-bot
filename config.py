import os

# إعدادات البوت - توكن فقط
BOT_TOKEN = os.getenv("BOT_TOKEN")  # من متغيرات Render

# إعدادات قاعدة البيانات
DB_NAME = "telegram_links_bot.db"

# إعدادات أخرى
LINKS_PER_PAGE = 20
SUPPORTED_LINK_TYPES = {
    'telegram': ['t.me', 'telegram.me'],
    'whatsapp': ['wa.me', 'whatsapp.com'],
    'website': ['http://', 'https://'],
    'youtube': ['youtube.com', 'youtu.be'],
    'instagram': ['instagram.com'],
    'twitter': ['twitter.com', 'x.com']
}

# للتحقق من أننا على Render
IS_RENDER = os.getenv("RENDER", "false").lower() == "true"
