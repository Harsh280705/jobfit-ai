"""Document parsers: PDF (PyMuPDF) / DOCX / plain text -> common representation."""
from __future__ import annotations
import io
import re
import uuid


def _pages_from_text(text: str) -> list[str]:
    # naive page split; real PDFs return per-page text
    return [text] if text else []


class DocumentParser:
    def parse(self, data: bytes, filename: str, mime: str) -> dict:
        name = (filename or "").lower()
        if name.endswith(".pdf") or mime == "application/pdf":
            return PDFParser().parse(data, filename)
        if name.endswith(".docx") or mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",):
            return DOCXParser().parse(data, filename)
        return TextParser().parse(data, filename)


class PDFParser:
    def parse(self, data: bytes, filename: str) -> dict:
        text = ""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=data, filetype="pdf")
            pages = []
            for page in doc:
                pages.append(page.get_text())
            text = "\n".join(pages)
        except Exception:
            # fallback: try pypdf if available, else empty
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(data))
                text = "\n".join([(p.extract_text() or "") for p in reader.pages])
            except Exception as e:
                from app.core.logging import DocumentParseError

                raise DocumentParseError(f"Unable to extract text from document: {e}")
        if not text.strip():
            from app.core.logging import DocumentParseError

            raise DocumentParseError("Unable to extract text from document.")
        return {
            "document_id": str(uuid.uuid4()),
            "document_type": "unknown",
            "text": text,
            "pages": _pages_from_text(text),
            "sections": [],
            "metadata": {"filename": filename, "parser": "pdf"},
        }


class DOCXParser:
    def parse(self, data: bytes, filename: str) -> dict:
        try:
            import docx

            d = docx.Document(io.BytesIO(data))
            text = "\n".join([p.text for p in d.paragraphs])
        except Exception as e:
            from app.core.logging import DocumentParseError

            raise DocumentParseError(f"Unable to extract text from document: {e}")
        return {
            "document_id": str(uuid.uuid4()),
            "document_type": "unknown",
            "text": text,
            "pages": _pages_from_text(text),
            "sections": [],
            "metadata": {"filename": filename, "parser": "docx"},
        }


class TextParser:
    def parse(self, data: bytes, filename: str) -> dict:
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        return {
            "document_id": str(uuid.uuid4()),
            "document_type": "unknown",
            "text": text,
            "pages": _pages_from_text(text),
            "sections": [],
            "metadata": {"filename": filename, "parser": "text"},
        }


SECTION_HEADINGS = [
    "contact", "summary", "objective", "skills", "technical skills", "experience",
    "work experience", "employment", "education", "projects", "certifications",
    "certificates", "achievements", "awards", "publications", "other",
]


def segment_sections(text: str) -> list[dict]:
    """Heuristic section segmentation robust to formatting variance."""
    lines = text.splitlines()
    sections: list[dict] = []
    current = {"name": "Other", "lines": []}
    pattern = re.compile(r"^\s*(#{0,3}\s*)?([A-Za-z &/]{3,40})\s*:?\s*$")
    for line in lines:
        m = pattern.match(line.strip())
        key = (line.strip().lower().rstrip(":") if m else "")
        if key in SECTION_HEADINGS:
            if current["lines"]:
                sections.append({"name": current["name"], "text": "\n".join(current["lines"])})
            pretty = key.title() if key != "work experience" else "Experience"
            if key == "technical skills":
                pretty = "Skills"
            current = {"name": pretty, "lines": []}
        else:
            current["lines"].append(line)
    if current["lines"]:
        sections.append({"name": current["name"], "text": "\n".join(current["lines"])})
    if not sections:
        sections = [{"name": "Other", "text": text}]
    return sections
