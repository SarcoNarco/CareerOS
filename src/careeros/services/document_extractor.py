from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


def extract_text_from_bytes(
    *,
    file_name: str,
    content_type: str | None,
    content: bytes,
) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        text = _extract_text_from_pdf(content)
        if text.strip():
            return text

    return _decode_text(content)


def extract_text_from_path(storage_path: Path) -> str:
    content = storage_path.read_bytes()
    content_type = "application/pdf" if storage_path.suffix.lower() == ".pdf" else None
    return extract_text_from_bytes(
        file_name=storage_path.name,
        content_type=content_type,
        content=content,
    )


def _extract_text_from_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
    except Exception:
        return _decode_text(content)

    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")

