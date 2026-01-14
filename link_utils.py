import re
from typing import List, Set
from telethon.tl.types import Message

from telethon.tl.types import (
    MessageEntityTextUrl,
    MessageEntityUrl,
)


# ======================
# Regex عام لأي رابط
# ======================

URL_REGEX = re.compile(
    r"(https?://[^\s<>\"]+)",
    re.IGNORECASE
)

# روابط بدون http مثل www.example.com
BARE_URL_REGEX = re.compile(
    r"((?:www\.)[^\s<>\"]+)",
    re.IGNORECASE
)

# دومين بدون scheme: example.com/path
DOMAIN_URL_REGEX = re.compile(
    r"((?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"]*)?)",
    re.IGNORECASE
)


# ======================
# أنماط المنصات
# ======================

PLATFORM_PATTERNS = {
    "telegram": re.compile(r"(t\.me|telegram\.me)", re.IGNORECASE),
    "whatsapp": re.compile(r"(wa\.me|chat\.whatsapp\.com)", re.IGNORECASE),
    "instagram": re.compile(r"(instagram\.com)", re.IGNORECASE),
    "facebook": re.compile(r"(facebook\.com|fb\.me|fb\.watch)", re.IGNORECASE),
    "x": re.compile(r"(x\.com|twitter\.com)", re.IGNORECASE),
}


# ======================
# URL Normalize
# ======================

def _normalize_url(u: str) -> str:
    """
    توحيد الرابط:
    - لو بدأ بـ www. => https://www...
    - لو دومين بدون scheme => https://
    """
    if not u:
        return u

    u = u.strip()

    if u.startswith("www."):
        return "https://" + u

    if not u.startswith("http://") and not u.startswith("https://"):
        if "." in u and " " not in u:
            return "https://" + u

    return u


# ======================
# استخراج الروابط من الرسالة
# ======================

def extract_links_from_message(message: Message) -> List[str]:
    """
    استخراج الروابط من:
    - نص الرسالة
    - الروابط المخفية داخل entities (TextUrl)
    - روابط بدون https
    - أزرار Inline (اضغط/مشبك)
    """
    links: Set[str] = set()

    text = message.text or message.message or ""

    # 1) روابط صريحة https://
    if text:
        for u in URL_REGEX.findall(text):
            links.add(_normalize_url(u))

    # 2) روابط www.
    if text:
        for u in BARE_URL_REGEX.findall(text):
            links.add(_normalize_url(u))

    # 3) دومين بدون scheme
    if text:
        for u in DOMAIN_URL_REGEX.findall(text):
            if len(u) >= 6:
                links.add(_normalize_url(u))

    # 4) الروابط المخفية داخل entities
    if getattr(message, "entities", None) and text:
        for ent in message.entities:

            # رابط مخفي: "اضغط هنا" والرابط داخلها
            if isinstance(ent, MessageEntityTextUrl):
                if getattr(ent, "url", None):
                    links.add(_normalize_url(ent.url))

            # رابط مكتوب وقد يكون بدون https
            elif isinstance(ent, MessageEntityUrl):
                try:
                    start = ent.offset
                    end = ent.offset + ent.length
                    raw = text[start:end]
                    links.add(_normalize_url(raw))
                except Exception:
                    pass

    # 5) أزرار Inline buttons
    if message.reply_markup:
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if hasattr(button, "url") and button.url:
                    links.add(_normalize_url(button.url))

    return list(links)


# ======================
# تصنيف المنصة (عام)
# ======================

def classify_platform(url: str) -> str:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "other"


# =========================================================
# Telegram / WhatsApp classification & filtering
# =========================================================

# -------- Telegram --------
TG_GROUP_REGEX = re.compile(r"https?://t\.me/(joinchat/|\+)[A-Za-z0-9_-]+", re.I)

# قناة/مجموعة عامة
TG_CHANNEL_REGEX = re.compile(r"https?://t\.me/[A-Za-z0-9_]+", re.I)

# ✅ NEW: Telegram Message Link (عام + خاص)
# - https://t.me/name/123
# - https://t.me/c/123456789/55
TG_MESSAGE_REGEX = re.compile(r"https?://t\.me/(?:c/\d+|[A-Za-z0-9_]+)/\d+", re.I)

# -------- WhatsApp --------
WA_GROUP_REGEX = re.compile(r"https?://chat\.whatsapp\.com/[A-Za-z0-9]+", re.I)
WA_PHONE_REGEX = re.compile(r"https?://wa\.me/\d+", re.I)


def filter_and_classify_link(url: str):
    """
    فلترة الرابط قبل الحفظ

    Returns:
        (platform, chat_type)
        أو None إذا الرابط مرفوض
    """
    url = _normalize_url(url)

    # ===== Telegram =====
    if "t.me" in url:

        # ✅ رابط رسالة
        if TG_MESSAGE_REGEX.match(url):
            # نرجعه كمنصة مستقلة عشان نقدر نطبق عليه "واحد فقط لكل مجموعة"
            return ("telegram_message", "message")

        # ✅ رابط دخول مجموعة
        if TG_GROUP_REGEX.match(url):
            return ("telegram", "group")

        # ✅ قناة / مجموعة عامة
        if TG_CHANNEL_REGEX.match(url):
            return ("telegram", "channel")

        # ❌ حساب شخص
        return None

    # ===== WhatsApp =====
    if "whatsapp.com" in url or "wa.me" in url:
        if WA_GROUP_REGEX.match(url):
            return ("whatsapp", "group")

        # ❌ رقم هاتف
        return None

    # ===== باقي المنصات =====
    platform = classify_platform(url)
    return (platform, "other")
