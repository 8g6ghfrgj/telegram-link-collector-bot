import os

# ======================
# Telegram Bot
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ======================
# Telegram API (Telethon)
# ======================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# ======================
# Database
# ======================

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/database.db")

# ======================
# Runtime
# ======================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EXPORT_DIR = os.getenv("EXPORT_DIR", "exports")

# ======================
# Validation
# ======================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not API_ID or not API_HASH:
    raise RuntimeError("API_ID / API_HASH are not set")
