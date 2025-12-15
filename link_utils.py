import re
from typing import List, Set, Optional, Tuple
from telethon.tl.types import Message


# ======================
# Regex عام لأي رابط
# ======================

URL_REGEX = re.compile(
    r"(https?://[^\s<>\"]+)",
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


# ======================
# استخراج الروابط من الرسالة (كما هو)
# ======================

def extract_links_from_message(message: Message) -> List[str]:
    """
    استخراج الروابط من:
    - نص الرسالة
    - الكابتشن
    - الروابط المخفية
    - أزرار Inline
    """
    links: Set[str] = set()

    text = message.text or message.message or ""
    if text:
        links.update(URL_REGEX.findall(text))

    if message.reply_markup:
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if hasattr(button, "url") and button.url:
                    links.add(button.url)

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


def filter_and_classify_link(url: str) -> Optional[Tuple[str, str]]:
    """
    فلترة الرابط قبل الحفظ

    Returns:
        (platform, chat_type)
        أو None إذا الرابط غير مرغوب
    """

    # ===== Telegram =====
    if "t.me" in url:
        if TG_GROUP_REGEX.match(url):
            return ("telegram", "group")

        if TG_CHANNEL_REGEX.match(url):
            # حسابات أشخاص تُستبعد لاحقاً في collector
            return ("telegram", "channel")

        return None

    # ===== WhatsApp =====
    if "whatsapp.com" in url or "wa.me" in url:
        if WA_GROUP_REGEX.match(url):
            return ("whatsapp", "group")

        # ❌ روابط أرقام
        return None

    # ===== Other =====
    return ("other", "other")
