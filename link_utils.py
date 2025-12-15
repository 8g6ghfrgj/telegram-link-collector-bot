import re
from typing import List, Set
from telethon.tl.types import Message


# ======================
# Regex Patterns
# ======================

URL_REGEX = re.compile(
    r"(https?://[^\s<>\"]+)",
    re.IGNORECASE
)

PLATFORM_PATTERNS = {
    "telegram": re.compile(r"(t\.me|telegram\.me)", re.IGNORECASE),
    "whatsapp": re.compile(r"(wa\.me|chat\.whatsapp\.com)", re.IGNORECASE),
    "instagram": re.compile(r"(instagram\.com)", re.IGNORECASE),
    "facebook": re.compile(r"(facebook\.com|fb\.watch|fb\.me)", re.IGNORECASE),
    "x": re.compile(r"(x\.com|twitter\.com)", re.IGNORECASE),
}


# ======================
# Public API
# ======================

def extract_links_from_message(message: Message) -> List[str]:
    """
    استخراج الروابط من:
    - نص الرسالة
    - الكابتشن
    - الأزرار (Inline Buttons)
    """
    links: Set[str] = set()

    # 1️⃣ النص / الكابتشن
    text = message.text or message.message or ""
    links.update(find_urls(text))

    # 2️⃣ الأزرار
    if message.reply_markup:
        for row in message.reply_markup.rows:
            for button in row.buttons:
                if hasattr(button, "url") and button.url:
                    links.add(button.url)

    return list(links)


def classify_platform(url: str) -> str:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "other"


# ======================
# Helpers
# ======================

def find_urls(text: str) -> List[str]:
    if not text:
        return []
    return URL_REGEX.findall(text)
