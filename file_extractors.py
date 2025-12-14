import re
from pypdf import PdfReader
from docx import Document


URL_PATTERN = re.compile(
    r"(https?://[^\s]+|t\.me/[^\s]+|wa\.me/[^\s]+)"
)


def extract_links_from_pdf(file_path: str) -> set:
    links = set()
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            text = page.extract_text() or ""
            links.update(URL_PATTERN.findall(text))
    except:
        pass
    return links


def extract_links_from_docx(file_path: str) -> set:
    links = set()
    try:
        doc = Document(file_path)

        # النص العادي
        for para in doc.paragraphs:
            links.update(URL_PATTERN.findall(para.text))

        # الروابط المضمّنة (Hyperlinks)
        for rel in doc.part.rels.values():
            if "hyperlink" in rel.reltype:
                links.add(rel.target_ref)
    except:
        pass

    return links
