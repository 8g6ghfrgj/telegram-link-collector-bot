import re
from typing import List, Set
from telethon.tl.types import Message


# ======================
# Regex عام لأي رابط
# ======================

URL_REGEX = re.compile(
    r"(https?://[^\s<>\"]+)",
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
# استخراج الروابط من الرسالة
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

    # 1️⃣ النص أو الكابتشن
    text = message.text or message.message or ""
    if text:
        links.update(URL_REGEX.findall(text))

    # 2️⃣ الأزرار (Inline Buttons)
    if message.reply_markup:
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if hasattr(button, "url") and button.url:
                    links.add(button.url)

    return list(links)


# ======================
# تصنيف المنصة
# ======================

def classify_platform(url: str) -> str:
    """
    تحديد المنصة من الرابط
    """
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform

    return "other"
