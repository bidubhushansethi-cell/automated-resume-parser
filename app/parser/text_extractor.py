"""Raw text extraction from PDF and DOCX files."""
import re
from pathlib import Path

import pdfplumber
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


class ExtractionError(Exception):
    """Raised when a file cannot be read or contains no text."""


BULLET_CHARS = "•●▪■◦○▫►➢✓✔❖◆‣∙·"


def clean_text(text: str) -> str:
    text = re.sub(r"[\x0b\x0c]", "\n", re.sub(r"[\x00-\x08\x0e-\x1f\x7f]", "", text))  # NUL breaks PostgreSQL
    text = text.replace("\xa0", " ").replace("\u200b", "").replace("\r", "\n")
    for ch in BULLET_CHARS:
        text = text.replace(ch, "• ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def extract_pdf(path: Path) -> str:
    pages = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
    except Exception as exc:  # corrupt / encrypted PDFs raise many exception types
        raise ExtractionError(f"The PDF could not be read ({exc.__class__.__name__}). "
                              "It may be corrupted or password protected.") from exc
    return "\n".join(pages)


def extract_docx(path: Path) -> str:
    try:
        doc = Document(str(path))
    except Exception as exc:
        raise ExtractionError(f"The DOCX file could not be read ({exc.__class__.__name__}). "
                              "It may be corrupted.") from exc
    lines = []
    for section in doc.sections:  # names are often placed in the page header
        for p in section.header.paragraphs:
            if p.text.strip():
                lines.append(p.text)
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            lines.append(Paragraph(child, doc).text)
        elif child.tag.endswith("}tbl"):
            seen = set()
            for row in Table(child, doc).rows:
                cells = []
                for cell in row.cells:
                    if id(cell._tc) in seen:  # merged cells repeat
                        continue
                    seen.add(id(cell._tc))
                    if cell.text.strip():
                        cells.append(cell.text.strip().replace("\n", " "))
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_text(path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw = extract_pdf(path)
    elif suffix == ".docx":
        raw = extract_docx(path)
    else:
        raise ExtractionError("Unsupported file type. Only PDF and DOCX are supported.")
    text = clean_text(raw)
    if len(text) < 30:
        raise ExtractionError("No readable text was found. Scanned or image-only resumes "
                              "are not supported (no OCR).")
    return text
