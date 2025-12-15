# config.py
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# قيم ثابتة (لا نستخدم OTP)
API_ID = 123456
API_HASH = "dummy_api_hash"
