from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from ashare_f10.raw_sources.models import ParsedText


class _TextAndLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self.canonical_url: str | None = None
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value for key, value in attrs}
        lower = tag.lower()
        if lower in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if lower == "title":
            self._in_title = True
        href = attributes.get("href")
        if lower == "a" and href:
            self.links.append(urljoin(self.base_url, href))
        rel = (attributes.get("rel") or "").lower()
        if lower == "link" and "canonical" in rel and href:
            self.canonical_url = urljoin(self.base_url, href)
        if lower in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        if lower == "title":
            self._in_title = False
        if lower in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        clean = html.unescape(data)
        if self._in_title:
            self.title_parts.append(clean)
        self.text_parts.append(clean)


def _clean_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\u3000", " ")
    lines: list[str] = []
    for line in value.splitlines():
        compact = re.sub(r"[ \t]+", " ", line).strip()
        if compact:
            lines.append(compact)
    return "\n".join(lines)


def extract_main_text(html_text: str, source_url: str = "") -> str:
    parser = _TextAndLinkParser(source_url)
    parser.feed(html_text)
    return _clean_text("".join(parser.text_parts))


def extract_links(html_text: str, base_url: str) -> list[str]:
    parser = _TextAndLinkParser(base_url)
    parser.feed(html_text)
    return list(dict.fromkeys(link for link in parser.links if link.startswith(("http://", "https://"))))


def parse_html_document(
    path_or_text: Path | str,
    source_url: str,
    *,
    document_id: str,
    output_dir: Path | None = None,
) -> ParsedText:
    if isinstance(path_or_text, Path):
        raw = path_or_text.read_bytes()
        html_text = raw.decode("utf-8", errors="replace")
    else:
        html_text = str(path_or_text)
    parser = _TextAndLinkParser(source_url)
    parser.feed(html_text)
    text = _clean_text("".join(parser.text_parts))
    title = _clean_text("".join(parser.title_parts)) or None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    text_path: str | None = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{document_id}.txt"
        path.write_text(text, encoding="utf-8")
        text_path = str(path)
    links = list(dict.fromkeys(link for link in parser.links if link.startswith(("http://", "https://"))))
    attachments = [
        link for link in links if re.search(r"\.(pdf|docx?|xlsx?|zip)(?:$|[?#])", link, flags=re.I)
    ]
    return ParsedText(
        document_id=document_id,
        text_path=text_path,
        text=text,
        text_sha256=digest,
        extractor="html_text",
        quality="good" if len(text) >= 40 else "partial" if text else "failed",
        title=title,
        canonical_url=parser.canonical_url,
        links=links,
        attachments=attachments,
    )
