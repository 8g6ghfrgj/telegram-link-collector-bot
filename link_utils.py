# link_utils.py
import re


# -------------------------
# استخراج الروابط من النص
# -------------------------
def extract_links_from_text(text: str):
    if not text:
        return []

    pattern = r"(https?://[^\s]+|t\.me/[^\s]+|wa\.me/[^\s]+)"
    return re.findall(pattern, text)


# -------------------------
# تصنيف الرابط
# -------------------------
def classify_link(url: str) -> str:
    url = url.lower()

    if "wa.me" in url or "whatsapp.com" in url:
        return "whatsapp"
    if "t.me" in url or "telegram.me" in url:
        return "telegram"
    if "instagram.com" in url:
        return "instagram"
    if "facebook.com" in url or "fb.com" in url:
        return "facebook"
    if "twitter.com" in url or "x.com" in url:
        return "x"

    return "other"
