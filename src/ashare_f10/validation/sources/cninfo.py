from __future__ import annotations

import hashlib
import html
import re
import time
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

from ashare_f10.validation.models import OfficialDocument

CNINFO_HOME = "https://www.cninfo.com.cn/"
CNINFO_FULLTEXT_PAGE = "https://www.cninfo.com.cn/new/fulltextSearch"
CNINFO_LOOKUP_URL = "https://www.cninfo.com.cn/new/information/topSearch/query"
CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_HOME = "https://static.cninfo.com.cn/"
CNINFO_TIMEZONE = ZoneInfo("Asia/Shanghai")
CNINFO_PERIODIC_CATEGORIES = ";".join(
    (
        "category_ndbg_szsh",
        "category_bndbg_szsh",
        "category_yjdbg_szsh",
        "category_sjdbg_szsh",
    )
)


class CNInfoOfficialSourceError(RuntimeError):
    pass


def _clean_title(value: Any) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", str(value or "")))
    return re.sub(r"\s+", "", text).strip()


def _date_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)) or str(value).isdigit():
        number = int(float(value))
        if number > 10_000_000_000:
            return (
                datetime.fromtimestamp(number / 1000, tz=UTC).astimezone(CNINFO_TIMEZONE).date().isoformat()
            )
    text = str(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text[:10]


def _report_identity(title: str) -> tuple[str, str] | None:
    compact = _clean_title(title)
    if any(token in compact for token in ("摘要", "英文版", "H股公告")):
        return None
    patterns = (
        (r"(20\d{2})年年度报告(?:全文)?(?:[（(][^）)]*(?:更正|修订|更新)[^）)]*[）)])?$", "12-31", "annual"),
        (
            r"(20\d{2})年(?:第?一|1)季度报告(?:全文)?(?:[（(][^）)]*(?:更正|修订|更新)[^）)]*[）)])?$",
            "03-31",
            "q1",
        ),
        (r"(20\d{2})年半年度报告(?:全文)?(?:[（(][^）)]*(?:更正|修订|更新)[^）)]*[）)])?$", "06-30", "half"),
        (
            r"(20\d{2})年(?:第?三|3)季度报告(?:全文)?(?:[（(][^）)]*(?:更正|修订|更新)[^）)]*[）)])?$",
            "09-30",
            "q3",
        ),
    )
    for pattern, suffix, kind in patterns:
        match = re.search(pattern, compact)
        if match:
            return f"{match.group(1)}-{suffix}", kind
    return None


def _version_label(title: str) -> str:
    compact = _clean_title(title)
    if any(token in compact for token in ("更正版", "更正后", "修订版", "修订稿", "更新后")):
        return "corrected"
    if any(token in compact for token in ("取消", "作废", "撤回")):
        return "withdrawn"
    return "original"


def _version_rank(document: OfficialDocument) -> tuple[int, str]:
    rank = {"corrected": 3, "original": 2, "withdrawn": 0}.get(document.version_label, 1)
    return rank, document.publish_date


class CNInfoOfficialSource:
    """Discover and download free official Shenzhen disclosures from CNINFO."""

    source_name = "CNINFO"

    def __init__(self, session: requests.Session | None = None, timeout: int = 45) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.last_payloads: list[dict[str, Any]] = []
        self._org_ids: dict[str, str] = {}
        self._warmed_codes: set[str] = set()
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
        )
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            }
        )

    def _warmup(self, security_code: str) -> None:
        if security_code in self._warmed_codes:
            return
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                self.session.get(CNINFO_HOME, timeout=self.timeout).raise_for_status()
                self.session.get(
                    CNINFO_FULLTEXT_PAGE,
                    params={"keyWord": security_code},
                    timeout=self.timeout,
                ).raise_for_status()
                self._warmed_codes.add(security_code)
                return
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2**attempt)
        raise CNInfoOfficialSourceError(f"巨潮资讯会话初始化失败：{last_error}")

    def _post_json(self, url: str, data: dict[str, str], referer: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.post(
                    url,
                    data=data,
                    headers={
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "Referer": referer,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2**attempt)
        raise CNInfoOfficialSourceError(f"巨潮资讯接口请求失败：{url}: {last_error}")

    def resolve_org_id(self, security_code: str) -> str:
        if security_code in self._org_ids:
            return self._org_ids[security_code]
        self._warmup(security_code)
        payload = self._post_json(
            CNINFO_LOOKUP_URL,
            {"keyWord": security_code, "maxNum": "10"},
            f"{CNINFO_FULLTEXT_PAGE}?keyWord={security_code}",
        )
        if not isinstance(payload, list):
            raise CNInfoOfficialSourceError("巨潮证券查询返回结构不是列表")
        candidates = [
            item
            for item in payload
            if isinstance(item, dict) and str(item.get("code") or "") == security_code
        ]
        if not candidates:
            raise CNInfoOfficialSourceError(f"巨潮未找到证券代码 {security_code} 对应的机构标识")
        candidates.sort(
            key=lambda item: (
                str(item.get("category") or "") == "A股",
                str(item.get("delisted") or "").lower() != "true",
            ),
            reverse=True,
        )
        org_id = str(candidates[0].get("orgId") or "")
        if not org_id:
            raise CNInfoOfficialSourceError(f"巨潮证券 {security_code} 缺少机构标识")
        self._org_ids[security_code] = org_id
        return org_id

    def list_reports(
        self,
        security_code: str,
        begin_date: str,
        end_date: str,
    ) -> list[OfficialDocument]:
        org_id = self.resolve_org_id(security_code)
        referer = f"{CNINFO_FULLTEXT_PAGE}?keyWord={security_code}"
        page_size = 30
        page_num = 1
        payloads: list[dict[str, Any]] = []
        documents: list[OfficialDocument] = []
        seen: set[tuple[str, str]] = set()

        while page_num <= 200:
            payload = self._post_json(
                CNINFO_QUERY_URL,
                {
                    "pageNum": str(page_num),
                    "pageSize": str(page_size),
                    "column": "szse",
                    "tabName": "fulltext",
                    "plate": "szse",
                    "stock": f"{security_code},{org_id}",
                    "searchkey": "",
                    "secid": "",
                    "category": CNINFO_PERIODIC_CATEGORIES,
                    "trade": "",
                    "seDate": f"{begin_date}~{end_date}",
                    "sortName": "",
                    "sortType": "",
                    "isHLtitle": "true",
                },
                referer,
            )
            if not isinstance(payload, dict):
                raise CNInfoOfficialSourceError("巨潮公告查询返回结构不是对象")
            payloads.append(payload)
            announcements = payload.get("announcements") or []
            if not isinstance(announcements, list):
                raise CNInfoOfficialSourceError("巨潮公告列表返回结构不是列表")

            for item in announcements:
                if not isinstance(item, dict):
                    continue
                title = _clean_title(item.get("announcementTitle"))
                identity = _report_identity(title)
                if not identity:
                    continue
                adjunct_url = str(item.get("adjunctUrl") or "").strip()
                adjunct_type = str(item.get("adjunctType") or "").upper()
                if not adjunct_url or (adjunct_type and adjunct_type != "PDF"):
                    continue
                report_date, report_kind = identity
                url = urljoin(CNINFO_STATIC_HOME, adjunct_url.lstrip("/"))
                key = (title, url)
                if key in seen:
                    continue
                seen.add(key)
                documents.append(
                    OfficialDocument(
                        source=self.source_name,
                        security_code=security_code,
                        title=title,
                        publish_date=_date_text(item.get("announcementTime")),
                        report_date=report_date,
                        report_kind=report_kind,
                        version_label=_version_label(title),
                        url=url,
                    )
                )

            has_more = bool(payload.get("hasMore"))
            total_pages = int(payload.get("totalpages") or 0)
            if not announcements or not has_more or (total_pages and page_num >= total_pages):
                break
            page_num += 1

        if page_num > 200:
            raise CNInfoOfficialSourceError("巨潮公告分页超过安全上限")
        self.last_payloads = payloads
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
            candidates = [
                item
                for item in available
                if item.report_date == report_date and item.version_label != "withdrawn"
            ]
            if not candidates:
                missing.append(report_date)
                continue
            selected.append(max(candidates, key=_version_rank))
        if missing:
            titles = "；".join(item.title for item in available[:30])
            raise CNInfoOfficialSourceError(
                f"巨潮未找到报告期 {', '.join(missing)} 的正式报告；查询到的报告：{titles or '无'}"
            )
        return selected

    def download(self, document: OfficialDocument, target_dir: Path) -> OfficialDocument:
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_kind = document.report_kind.replace("/", "-")
        target = target_dir / f"{document.security_code}_{document.report_date}_{safe_kind}.pdf"
        candidate_urls = [
            document.url,
            document.url.replace("https://static.cninfo.com.cn/", "https://www.cninfo.com.cn/", 1),
        ]
        last_error: Exception | None = None
        for url in dict.fromkeys(candidate_urls):
            for attempt in range(1, 4):
                try:
                    response = self.session.get(
                        url,
                        headers={
                            "User-Agent": self.user_agent,
                            "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                            "Referer": f"{CNINFO_FULLTEXT_PAGE}?keyWord={document.security_code}",
                        },
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    content = response.content
                    if not content.startswith(b"%PDF"):
                        raise CNInfoOfficialSourceError(
                            f"巨潮报告下载返回非PDF内容：{response.headers.get('content-type')}"
                        )
                    temporary = target.with_suffix(".pdf.tmp")
                    temporary.write_bytes(content)
                    temporary.replace(target)
                    document.url = url
                    document.local_path = str(target)
                    document.sha256 = hashlib.sha256(content).hexdigest()
                    return document
                except (requests.RequestException, CNInfoOfficialSourceError) as exc:
                    last_error = exc
                    if attempt < 3:
                        time.sleep(2**attempt)
        raise CNInfoOfficialSourceError(f"巨潮报告下载失败：{document.title}: {last_error}")
