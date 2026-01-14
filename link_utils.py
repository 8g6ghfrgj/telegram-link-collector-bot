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

# ✅ NEW: link patterns بدون http مثل www.example.com
BARE_URL_REGEX = re.compile(
    r"((?:www\.)[^\s<>\"]+)",
    re.IGNORECASE
)

# ✅ NEW: domains with no scheme (example.com/path)
DOMAIN_URL_REGEX = re.compile(
    r"((?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"]*)?)",
    re.IGNORECASE
)


# ======================
# أنماط المنصات (القديمة - لا نلمسها)
# ======================

PLATFORM_PATTERNS = {
    "telegram": re.compile(r"(t\.me|telegram\.me)", re.IGNORECASE),
    "whatsapp": re.compile(r"(wa\.me|chat\.whatsapp\.com)", re.IGNORECASE),
    "instagram": re.compile(r"(instagram\.com)", re.IGNORECASE),
    "facebook": re.compile(r"(facebook\.com|fb\.me|fb\.watch)", re.IGNORECASE),
    "x": re.compile(r"(x\.com|twitter\.com)", re.IGNORECASE),
}


def _normalize_url(u: str) -> str:
    """
    ✅ توحيد الرابط:
    - لو بدأ بـ www. نحوله https://www...
    - لو رابط دومين بدون scheme نحوله https://
    """
    if not u:
        return u
    u = u.strip()

    if u.startswith("www."):
        return "https://" + u

    # لو شكله دومين بدون http
    if not u.startswith("http://") and not u.startswith("https://"):
        # نتأكد أنه مو شيء عشوائي
        if "." in u and " " not in u:
            return "https://" + u

    return u


# ======================
# استخراج الروابط من الرسالة (✅ تعديل شامل)
# ======================

def extract_links_from_message(message: Message) -> List[str]:
    """
    استخراج الروابط من:
    - نص الرسالة
    - الكابتشن
    - الروابط المخفية داخل entities (TextUrl)
    - الروابط غير المكتملة (بدون https مثل www.)
    - أزرار Inline
    """
    links: Set[str] = set()

    text = message.text or message.message or ""

    # 1) روابط صريحة https://
    if text:
        for u in URL_REGEX.findall(text):
            links.add(_normalize_url(u))

    # 2) روابط بدون http مثل www.example.com
    if text:
        for u in BARE_URL_REGEX.findall(text):
            links.add(_normalize_url(u))

    # 3) روابط دومين بدون scheme (example.com/xxx)
    # ملاحظة: هذا قد يلتقط أشياء ليست روابط أحياناً، لكن مفيد جداً للتعليقات
    if text:
        for u in DOMAIN_URL_REGEX.findall(text):
            # استثني كلمات قصيرة/ملخبطة
            if len(u) >= 6:
                links.add(_normalize_url(u))

    # 4) ✅ الروابط المخفية داخل entities
    # مثل: اضغط هنا (الرابط مخفي)
    if getattr(message, "entities", None) and text:
        for ent in message.entities:
            # رابط مخفي
            if isinstance(ent, MessageEntityTextUrl):
                if getattr(ent, "url", None):
                    links.add(_normalize_url(ent.url))

            # رابط “مرئي” ولكن قد يكون بدون https
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
# تصنيف المنصة (كما هو)
# ======================

def classify_platform(url: str) -> str:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "other"


# =========================================================
# ================== الإضافات الجديدة فقط ==================
# =========================================================

# -------- Telegram --------
TG_GROUP_REGEX = re.compile(r"https?://t\.me/(joinchat/|\+)[A-Za-z0-9_-]+", re.I)
TG_CHANNEL_REGEX = re.compile(r"https?://t\.me/[A-Za-z0-9_]+", re.I)

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
        if TG_GROUP_REGEX.match(url):
            return ("telegram", "group")

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
