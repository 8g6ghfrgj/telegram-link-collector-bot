# config.py
import os

# ===============================
# Telegram Bot
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ===============================
# Telethon (اختياري – للجلسات)
# ===============================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# ===============================
# تحقق بسيط (اختياري)
# ===============================
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN is not set in environment variables")

if ADMIN_ID == 0:
    print("⚠️ ADMIN_ID is not set correctly")
