import os
import tempfile
from typing import List, Set

from telethon import TelegramClient
from telethon.tl.types import Message

from link_utils import URL_REGEX


# ======================
# Public API
# ======================

async def extract_links_from_file(
    client: TelegramClient,
    message: Message
) -> List[str]:
    """
    تحميل الملف مؤقتاً
    ثم استخراج الروابط منه
    يدعم:
    - PDF
    - DOCX
    """
    if not message.file:
        return []

    links: Set[str] = set()

    filename = message.file.name or "file"
    mime = message.file.mime_type or ""

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, filename)

        # تحميل الملف
        await client.download_media(message, path)

        # PDF
        if filename.lower().endswith(".pdf") or mime == "application/pdf":
            links.update(_extract_from_pdf(path))

        # DOCX
        elif (
            filename.lower().endswith(".docx")
            or mime
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            links.update(_extract_from_docx(path))

    return list(links)


# ======================
# PDF
# ======================

def _extract_from_pdf(path: str) -> List[str]:
    """
    استخراج الروابط من ملفات PDF
    """
    links: Set[str] = set()

    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(path)
        for page in reader.pages:
            text = page.extract_text() or ""
            links.update(URL_REGEX.findall(text))

    except Exception:
        # لا نكسر البوت أبداً
        pass

    return list(links)


# ======================
# DOCX
# ======================

def _extract_from_docx(path: str) -> List[str]:
    """
    استخراج الروابط من ملفات DOCX
    """
    links: Set[str] = set()

    try:
        from docx import Document

        doc = Document(path)

        # فقرات
        for para in doc.paragraphs:
            links.update(URL_REGEX.findall(para.text))

        # جداول
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    links.update(URL_REGEX.findall(cell.text))

    except Exception:
        # لا نكسر البوت أبداً
        pass

    return list(links)
