import os

# ======================
# Telegram Bot
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ======================
# Telegram API (Telethon)
# ثوابت داخل الكود
# ======================

API_ID = 12345678          # ← ضع API_ID الحقيقي هنا
API_HASH = "API_HASH_HERE" # ← ضع API_HASH الحقيقي هنا

# ======================
# Database
# ======================

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/database.db")

# ======================
# Runtime
# ======================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = "exports"

# ======================
# Validation
# ======================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
