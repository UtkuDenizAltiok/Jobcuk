"""The user's CV and cover letter: saving uploads and reading their text.

Documents are kept only in the data folder (documents/), and their text is never
written to the log. Jobcu reads them fresh at the start of every search.
"""

import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from jobcu.paths import ensure_data_dir

DocumentKind = Literal["cv", "cover_letter"]

ALLOWED_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "cv": (".pdf", ".docx"),
    "cover_letter": (".pdf", ".docx", ".txt"),
}
KIND_NAMES = {"cv": "CV", "cover_letter": "cover letter"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Far longer than any CV or cover letter. Longer text is refused rather than cut,
# so nothing is silently left out.
MAX_TEXT_CHARS = 60_000
MIN_TEXT_CHARS = 80


class DocumentError(Exception):
    """A plain-language problem with an uploaded document."""


@dataclass
class DocumentInfo:
    kind: DocumentKind
    original_name: str
    extension: str
    uploaded_at: str
    size_bytes: int


def documents_dir() -> Path:
    folder = ensure_data_dir() / "documents"
    folder.mkdir(exist_ok=True)
    return folder


def _index_path() -> Path:
    return documents_dir() / "documents.json"


def _load_index() -> dict:
    try:
        return json.loads(_index_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save_index(index: dict) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=documents_dir(), prefix=".documents-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as tmp:
        json.dump(index, tmp, indent=2)
    os.replace(tmp_name, _index_path())


def get_info(kind: DocumentKind) -> DocumentInfo | None:
    entry = _load_index().get(kind)
    if not entry or not stored_path(kind, entry["extension"]).exists():
        return None
    return DocumentInfo(kind=kind, **entry)


def stored_path(kind: DocumentKind, extension: str) -> Path:
    return documents_dir() / f"{kind}{extension}"


def save_upload(kind: DocumentKind, filename: str, content: bytes) -> DocumentInfo:
    """Check an uploaded file, make sure its text can be read, then keep it."""
    name = Path(filename or "").name
    extension = Path(name).suffix.lower()
    allowed = ALLOWED_EXTENSIONS[kind]
    if extension not in allowed:
        raise DocumentError(
            f"Please upload your {KIND_NAMES[kind]} as "
            + " or ".join(ext.lstrip(".").upper() for ext in allowed)
            + " file."
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentError("This file is larger than 10 MB. Please upload a smaller version.")
    # Reading it now means problems show up at upload, not in the middle of a search.
    extract_text_from_bytes(content, extension)

    for old in documents_dir().glob(f"{kind}.*"):
        old.unlink()
    path = stored_path(kind, extension)
    path.write_bytes(content)
    if os.name == "posix":
        path.chmod(0o600)
    entry = {
        "original_name": name,
        "extension": extension,
        "uploaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "size_bytes": len(content),
    }
    index = _load_index()
    index[kind] = entry
    _save_index(index)
    return DocumentInfo(kind=kind, **entry)


def delete(kind: DocumentKind) -> None:
    for old in documents_dir().glob(f"{kind}.*"):
        old.unlink()
    index = _load_index()
    if index.pop(kind, None) is not None:
        _save_index(index)


def read_text(kind: DocumentKind) -> str:
    info = get_info(kind)
    if info is None:
        raise DocumentError(f"Please upload your {KIND_NAMES[kind]} first.")
    return extract_text_from_bytes(stored_path(kind, info.extension).read_bytes(), info.extension)


# ---------------------------------------------------------------------------
# Reading text
# ---------------------------------------------------------------------------


def extract_text_from_bytes(content: bytes, extension: str) -> str:
    if extension == ".pdf":
        text = _pdf_text(content)
    elif extension == ".docx":
        text = _docx_text(content)
    elif extension == ".txt":
        text = _plain_text(content)
    else:
        raise DocumentError("Jobcu can't read this type of file.")
    text = tidy(text)
    if len(text) < MIN_TEXT_CHARS:
        raise DocumentError(
            "Jobcu couldn't find readable text in this file. If it's a scanned picture of a "
            "document, please upload a version saved directly from Word, Pages or Google Docs."
        )
    if len(text) > MAX_TEXT_CHARS:
        raise DocumentError(
            "This document is much longer than a usual CV or cover letter. Please upload a "
            "shorter version."
        )
    return text


def _pdf_text(content: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not content.startswith(b"%PDF"):
        raise DocumentError("This file doesn't look like a real PDF. Please save it again as PDF.")
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentError(
                "This PDF is password-protected. Please save a copy without a password."
            )
        # PDF programs store text very differently. Reading it two ways and keeping
        # the cleaner result handles both "one word per line" and "scattered layout" files.
        plain = "\n".join(page.extract_text() or "" for page in reader.pages)
        layout = "\n".join(
            page.extract_text(extraction_mode="layout") or "" for page in reader.pages
        )
    except DocumentError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise DocumentError(
            "Jobcu couldn't open this PDF. It may be damaged. Please save it again as PDF."
        ) from exc
    if _fragmentation(tidy(plain)) <= _fragmentation(tidy(layout)) + 0.1:
        return plain
    return layout


def _fragmentation(text: str) -> float:
    """Share of lines holding a single word: high when a PDF stores words separately."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return 1.0
    return sum(1 for line in lines if len(line.split()) <= 1) / len(lines)


def _docx_text(content: bytes) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(content))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise DocumentError(
            "Jobcu couldn't open this Word file. Please save it again as DOCX."
        ) from exc
    parts: list[str] = []
    for section in document.sections:
        parts.extend(p.text for p in section.header.paragraphs)
    # Paragraphs and tables in reading order: CVs often use tables for layout.
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            parts.append(block.text)
        elif isinstance(block, Table):
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:
                    if cell.text not in cells:  # merged cells repeat their text
                        cells.append(cell.text)
                parts.append("  ".join(cells))
    return "\n".join(parts)


def _plain_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentError("Jobcu couldn't read this text file.")


def tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
