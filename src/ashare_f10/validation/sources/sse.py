from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from ashare_f10.validation.models import OfficialDocument

SSE_QUERY_URL = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"
SSE_HOME = "https://www.sse.com.cn/"
SSE_ANNOUNCEMENT_PAGE = "http://www.sse.com.cn/disclosure/listedinfo/announcement/"
REPORT_TYPE_CODES = ("YEARLY", "QUATER1", "QUATER2", "QUATER3")
_ACW_PERMUTATION = (
    0x0F,
    0x23,
    0x1D,
    0x18,
    0x21,
    0x10,
    0x01,
    0x26,
    0x0A,
    0x09,
    0x13,
    0x1F,
    0x28,
    0x1B,
    0x16,
    0x17,
    0x19,
    0x0D,
    0x06,
    0x0B,
    0x27,
    0x12,
    0x14,
    0x08,
    0x0E,
    0x15,
    0x20,
    0x1A,
    0x02,
    0x1E,
    0x07,
    0x04,
    0x11,
    0x05,
    0x03,
    0x1C,
    0x22,
    0x25,
    0x0C,
    0x24,
)
_ACW_XOR_KEY = "3000176000856006061501533003690027800375"


class OfficialSourceError(RuntimeError):
    pass


def _date_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text[:10]


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _first(item: dict[str, Any], *names: str) -> Any:
    lowered = {str(key).lower(): value for key, value in item.items()}
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _report_identity(title: str) -> tuple[str, str] | None:
    annual = re.search(r"(20\d{2})\s*年\s*年度报告", title)
    if annual and "摘要" not in title:
        return f"{annual.group(1)}-12-31", "annual"
    q1 = re.search(r"(20\d{2})\s*年\s*第一季度报告", title)
    if q1 and "摘要" not in title:
        return f"{q1.group(1)}-03-31", "q1"
    half = re.search(r"(20\d{2})\s*年\s*半年度报告", title)
    if half and "摘要" not in title:
        return f"{half.group(1)}-06-30", "half"
    q3 = re.search(r"(20\d{2})\s*年\s*第三季度报告", title)
    if q3 and "摘要" not in title:
        return f"{q3.group(1)}-09-30", "q3"
    return None


def _version_label(title: str) -> str:
    if any(token in title for token in ("更正版", "更正后", "修订版", "修订稿")):
        return "corrected"
    if "取消" in title or "作废" in title:
        return "withdrawn"
    return "original"


def _version_rank(document: OfficialDocument) -> tuple[int, str]:
    rank = {"corrected": 3, "original": 2, "withdrawn": 0}.get(document.version_label, 1)
    return rank, document.publish_date


def _calculate_acw_cookie(arg1: str) -> str:
    """Calculate the browser verification cookie returned by the SSE public CDN."""
    if not re.fullmatch(r"[0-9A-Fa-f]{40}", arg1):
        raise ValueError("SSE verification seed must be a 40-character hexadecimal string")
    reordered = [""] * len(_ACW_PERMUTATION)
    for index, character in enumerate(arg1):
        for destination, source_position in enumerate(_ACW_PERMUTATION):
            if source_position == index + 1:
                reordered[destination] = character
                break
    unsboxed = "".join(reordered)
    return "".join(
        f"{int(unsboxed[index:index + 2], 16) ^ int(_ACW_XOR_KEY[index:index + 2], 16):02x}"
        for index in range(0, len(unsboxed), 2)
    )


def _verification_seed(content: bytes) -> str | None:
    text = content.decode("utf-8", errors="ignore")
    match = re.search(r"var\s+arg1\s*=\s*['\"]([0-9A-Fa-f]{40})['\"]", text)
    return match.group(1) if match else None


class SSEOfficialSource:
    """Discover and download official SSE disclosure documents.

    The source is free and official. No commercial data API is used.
    """

    def __init__(self, session: requests.Session | None = None, timeout: int = 45) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.last_payloads: list[dict[str, Any]] = []
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
        )
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Referer": SSE_HOME,
                "Accept": "application/json,text/javascript,*/*;q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def _get_json(self, params: dict[str, str]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.get(SSE_QUERY_URL, params=params, timeout=self.timeout)
                response.raise_for_status()
                text = response.text.strip()
                try:
                    payload = response.json()
                except ValueError:
                    match = re.search(r"\((\{.*\})\)\s*;?\s*$", text, flags=re.S)
                    if not match:
                        raise OfficialSourceError(f"SSE公告查询返回非JSON内容：{text[:200]}") from None
                    payload = json.loads(match.group(1))
                if not isinstance(payload, dict):
                    raise OfficialSourceError("SSE公告查询返回结构不是对象")
                return payload
            except (requests.RequestException, ValueError, OfficialSourceError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2**attempt)
        raise OfficialSourceError(f"SSE公告查询失败：{last_error}")

    def list_reports(
        self,
        security_code: str,
        begin_date: str,
        end_date: str,
    ) -> list[OfficialDocument]:
        base_params = {
            "isPagination": "false",
            "productId": security_code,
            "keyWord": "",
            "securityType": "0101,120100,020100,020200,120200",
            "reportType2": "DQBG",
            "beginDate": begin_date,
            "endDate": end_date,
            "pageHelp.pageSize": "100",
            "pageHelp.pageCount": "50",
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": "5",
        }
        payloads: list[dict[str, Any]] = []
        for report_type in REPORT_TYPE_CODES:
            params = {**base_params, "reportType": report_type}
            payloads.append(self._get_json(params))

        self.last_payloads = payloads

        documents: list[OfficialDocument] = []
        seen: set[tuple[str, str]] = set()
        for payload in payloads:
            for item in _iter_dicts(payload):
                title_value = _first(
                    item,
                    "TITLE",
                    "title",
                    "BULLETIN_HEADING",
                    "bulletinHeading",
                    "announcementTitle",
                )
                url_value = _first(
                    item,
                    "URL",
                    "url",
                    "BULLETIN_URL",
                    "bulletinUrl",
                    "adjunctUrl",
                )
                if title_value in (None, "") or url_value in (None, ""):
                    continue
                title = re.sub(r"<[^>]+>", "", str(title_value)).strip()
                identity = _report_identity(title)
                if not identity:
                    continue
                report_date, report_kind = identity
                url = str(url_value).strip()
                if not url.lower().startswith(("http://", "https://")):
                    url = urljoin(SSE_HOME, url)
                publish_date = _date_text(
                    _first(item, "SSEDATE", "publishDate", "PUBLISH_DATE", "announcementTime")
                )
                key = (title, url)
                if key in seen:
                    continue
                seen.add(key)
                documents.append(
                    OfficialDocument(
                        source="SSE",
                        security_code=security_code,
                        title=title,
                        publish_date=publish_date,
                        report_date=report_date,
                        report_kind=report_kind,
                        version_label=_version_label(title),
                        url=url,
                    )
                )
        documents.sort(key=lambda item: (item.report_date, *_version_rank(item)), reverse=True)
        return documents

    def select_reports(
        self,
        security_code: str,
        report_dates: Iterable[str],
        begin_date: str | None = None,
        end_date: str | None = None,
    ) -> list[OfficialDocument]:
        requested = sorted(set(report_dates))
        if not requested:
            return []
        begin_date = begin_date or f"{min(requested)[:4]}-01-01"
        end_date = end_date or date.today().isoformat()
        available = self.list_reports(security_code, begin_date, end_date)
        selected: list[OfficialDocument] = []
        missing: list[str] = []
        for report_date in requested:
            candidates = [item for item in available if item.report_date == report_date]
            candidates = [item for item in candidates if item.version_label != "withdrawn"]
            if not candidates:
                missing.append(report_date)
                continue
            selected.append(max(candidates, key=_version_rank))
        if missing:
            titles = "；".join(item.title for item in available[:20])
            payload_preview = json.dumps(self.last_payloads, ensure_ascii=False)[:4000]
            raise OfficialSourceError(
                f"SSE未找到报告期 {', '.join(missing)} 的正式报告；"
                f"查询到的报告：{titles or '无'}；响应预览：{payload_preview}"
            )
        return selected

    def download(self, document: OfficialDocument, target_dir: Path) -> OfficialDocument:
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_kind = document.report_kind.replace("/", "-")
        target = target_dir / f"{document.security_code}_{document.report_date}_{safe_kind}.pdf"
        parsed = urlparse(document.url)
        candidate_urls: list[str] = []
        if parsed.path.startswith("/disclosure/"):
            candidate_urls.extend(
                [
                    f"http://static.sse.com.cn{parsed.path}",
                    f"http://www.sse.com.cn{parsed.path}",
                    f"https://static.sse.com.cn{parsed.path}",
                    f"https://www.sse.com.cn{parsed.path}",
                ]
            )
        candidate_urls.append(document.url)

        download_session = requests.Session()
        download_session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "Referer": SSE_ANNOUNCEMENT_PAGE,
                "Connection": "keep-alive",
            }
        )
        try:
            download_session.get(SSE_ANNOUNCEMENT_PAGE, timeout=self.timeout)
        except requests.RequestException:
            pass

        diagnostics: list[str] = []
        last_error: Exception | None = None
        for url in dict.fromkeys(candidate_urls):
            for attempt in range(1, 4):
                try:
                    response = download_session.get(
                        url,
                        timeout=max(self.timeout, 90),
                        allow_redirects=True,
                    )
                    response.raise_for_status()
                    content = response.content
                    seed = _verification_seed(content)
                    if seed:
                        download_session.cookies.set(
                            "acw_sc__v2",
                            _calculate_acw_cookie(seed),
                            domain=".sse.com.cn",
                            path="/",
                        )
                        response = download_session.get(
                            url,
                            timeout=max(self.timeout, 90),
                            allow_redirects=True,
                        )
                        response.raise_for_status()
                        content = response.content
                    if not content.startswith(b"%PDF"):
                        preview = content[:120].decode("utf-8", errors="replace").replace("\n", " ")
                        diagnostics.append(
                            f"url={url}, final={response.url}, status={response.status_code}, "
                            f"content-type={response.headers.get('content-type')}, bytes={len(content)}, "
                            f"preview={preview}"
                        )
                        raise OfficialSourceError(f"下载内容不是PDF：{diagnostics[-1]}")
                    target.write_bytes(content)
                    document.url = response.url
                    document.local_path = str(target)
                    document.sha256 = hashlib.sha256(content).hexdigest()
                    return document
                except (requests.RequestException, OfficialSourceError) as exc:
                    last_error = exc
                    if attempt < 3:
                        time.sleep(2**attempt)
        detail = "；".join(diagnostics[-8:])
        raise OfficialSourceError(
            f"下载官方报告失败：{document.title}：{last_error}；尝试详情：{detail}"
        )
