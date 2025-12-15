import os

# هذه القيم تأخذ تلقائياً من Environment Variables في Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

# إعدادات أخرى (ثابتة)
DB_NAME = "telegram_links_bot.db"
LINKS_PER_PAGE = 20
IS_RENDER = os.getenv("RENDER", "false").lower() == "true"

# أنواع الروابط المدعومة
SUPPORTED_LINK_TYPES = {
    'telegram': ['t.me', 'telegram.me'],
    'whatsapp': ['wa.me', 'whatsapp.com'],
    'website': ['http://', 'https://'],
    'youtube': ['youtube.com', 'youtu.be'],
    'instagram': ['instagram.com'],
    'twitter': ['twitter.com', 'x.com']
}
