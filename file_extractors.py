import os
import re
import tempfile
from typing import List, Set

from telethon import TelegramClient
from telethon.tl.types import Message

from link_utils import find_urls


# ======================
# Public API
# ======================

async def extract_links_from_file(
    client: TelegramClient,
    message: Message
) -> List[str]:
    """
    تحميل الملف مؤقتاً ثم استخراج الروابط منه
    يدعم:
    - PDF
    - DOCX
    """
    links: Set[str] = set()

    if not message.file:
        return []

    mime = message.file.mime_type or ""
    filename = message.file.name or ""

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, filename)

        await client.download_media(message, file_path)

        if mime == "application/pdf" or filename.lower().endswith(".pdf"):
            links.update(extract_from_pdf(file_path))

        elif (
            mime
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or filename.lower().endswith(".docx")
        ):
            links.update(extract_from_docx(file_path))

    return list(links)


# ======================
# PDF
# ======================

def extract_from_pdf(path: str) -> List[str]:
    links: Set[str] = set()

    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(path)
        for page in reader.pages:
            text = page.extract_text() or ""
            links.update(find_urls(text))

    except Exception:
        pass

    return list(links)


# ======================
# DOCX
# ======================

def extract_from_docx(path: str) -> List[str]:
    links: Set[str] = set()

    try:
        from docx import Document

        doc = Document(path)

        for para in doc.paragraphs:
            links.update(find_urls(para.text))

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    links.update(find_urls(cell.text))

    except Exception:
        pass

    return list(links)
