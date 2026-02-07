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

BARE_URL_REGEX = re.compile(
    r"((?:www\.)[^\s<>\"]+)",
    re.IGNORECASE
)

DOMAIN_URL_REGEX = re.compile(
    r"((?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"]*)?)",
    re.IGNORECASE
)

# ======================
# URL Normalize
# ======================

def _normalize_url(u: str) -> str:
    return u.strip() if u else u


# ======================
# استخراج الروابط من الرسالة
# ======================

def extract_links_from_message(message: Message) -> List[str]:
    links: Set[str] = set()
    text = message.text or message.message or ""

    # 1) روابط https
    for u in URL_REGEX.findall(text):
        links.add(_normalize_url(u))

    # 2) روابط www.
    for u in BARE_URL_REGEX.findall(text):
        links.add(_normalize_url(u))

    # 3) دومين بدون scheme
    for u in DOMAIN_URL_REGEX.findall(text):
        if len(u) >= 6:
            links.add(_normalize_url(u))

    # 4) entities
    if getattr(message, "entities", None) and text:
        for ent in message.entities:
            if isinstance(ent, MessageEntityTextUrl) and ent.url:
                links.add(_normalize_url(ent.url))

            elif isinstance(ent, MessageEntityUrl):
                try:
                    raw = text[ent.offset : ent.offset + ent.length]
                    links.add(_normalize_url(raw))
                except Exception:
                    pass

    # 5) Inline buttons (آمن)
    try:
        rm = getattr(message, "reply_markup", None)
        if rm and getattr(rm, "rows", None):
            for row in rm.rows:
                for btn in getattr(row, "buttons", []):
                    if getattr(btn, "url", None):
                        links.add(_normalize_url(btn.url))
    except Exception:
        pass

    return list(links)


# =========================================================
# Telegram / WhatsApp classification
# =========================================================

# -------- Telegram --------

TG_GROUP_REGEX = re.compile(r"https?://t\.me/(joinchat/|\+)[A-Za-z0-9_-]+", re.I)
TG_CHANNEL_REGEX = re.compile(r"https?://t\.me/[A-Za-z0-9_]+$", re.I)
TG_MESSAGE_REGEX = re.compile(r"https?://t\.me/(?:c/\d+|[A-Za-z0-9_]+)/\d+", re.I)
TG_ADDLIST_REGEX = re.compile(r"https?://t\.me/addlist/[A-Za-z0-9_-]+", re.I)

# -------- WhatsApp --------

WA_GROUP_REGEX = re.compile(r"https?://chat\.whatsapp\.com/[A-Za-z0-9]+", re.I)


def filter_and_classify_link(url: str):
    """
    Returns:
        (platform, chat_type)
        platform ∈ {telegram, whatsapp}
    """
    url = _normalize_url(url)

    # ===== Telegram =====
    if "t.me" in url:

        if TG_ADDLIST_REGEX.match(url):
            return ("telegram", "addlist")

        if TG_MESSAGE_REGEX.match(url):
            return ("telegram", "message")

        if TG_GROUP_REGEX.match(url):
            return ("telegram", "group")

        if TG_CHANNEL_REGEX.match(url):
            return ("telegram", "channel")

        return None

    # ===== WhatsApp =====
    if "whatsapp.com" in url or "wa.me" in url:
        if WA_GROUP_REGEX.match(url):
            return ("whatsapp", "group")
        return None

    return None
