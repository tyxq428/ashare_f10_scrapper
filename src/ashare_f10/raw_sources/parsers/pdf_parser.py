from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from ashare_f10.raw_sources.models import ParsedText


def extract_pdf_metadata(path: Path) -> dict[str, object]:
    reader = PdfReader(str(path))
    metadata = reader.metadata or {}
    return {
        "page_count": len(reader.pages),
        "title": metadata.get("/Title"),
        "author": metadata.get("/Author"),
        "creator": metadata.get("/Creator"),
        "producer": metadata.get("/Producer"),
        "encrypted": reader.is_encrypted,
    }


def parse_pdf(path: Path, document_id: str, output_dir: Path | None = None) -> ParsedText:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"ENCRYPTED_PDF: {path}: {exc}") from exc
    page_map: list[dict[str, object]] = []
    text_parts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        page_map.append({"page": index, "text": text})
        if text:
            text_parts.append(f"[PAGE {index}]\n{text}")
    text = "\n\n".join(text_parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    text_path: str | None = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{document_id}.txt"
        target.write_text(text, encoding="utf-8")
        text_path = str(target)
    return ParsedText(
        document_id=document_id,
        text_path=text_path,
        text=text,
        text_sha256=digest,
        extractor="pdf_text",
        page_map=page_map,
        quality="good" if len(text) >= 100 else "partial" if text else "failed",
    )
