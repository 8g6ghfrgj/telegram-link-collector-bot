import os

# ======================
# Telegram Bot
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# ======================
# Admin Notifications
# ======================
# ✅ ضع ايدي حسابك (أو قناة خاصة) لاستلام روابط "الجديد فقط"
# الأفضل على Render: تحطه ENV باسم ADMIN_CHAT_ID

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ======================
# Telegram API (Telethon)
# ثوابت داخل الكود كما طلبت
# ======================

API_ID = 12345678          # ← ضع API_ID الحقيقي هنا
API_HASH = "API_HASH_HERE" # ← ضع API_HASH الحقيقي هنا

# ======================
# Database
# ======================

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "data/database.db"
)

# ======================
# Runtime Directories
# ======================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

# ======================
# Validation
# ======================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not API_ID or not API_HASH:
    raise RuntimeError("API_ID / API_HASH are missing")

if not ADMIN_CHAT_ID:
    raise RuntimeError("ADMIN_CHAT_ID is not set")
