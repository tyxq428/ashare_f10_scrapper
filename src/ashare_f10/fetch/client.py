from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

import requests

from ashare_f10.config import Settings
from ashare_f10.models import RequestSpec


@dataclass
class PageResponse:
    request: dict[str, Any]
    response: dict[str, Any]
    payload: Any
    raw_path: str


def utc_now() -> str:
    from datetime import datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_json_or_jsonp(raw: bytes) -> Any:
    text = raw.decode("utf-8-sig", errors="replace").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # callback({...}) and variableName={...}; forms.
    start_candidates = [pos for pos in (text.find("{"), text.find("[")) if pos >= 0]
    if not start_candidates:
        raise ValueError("响应不是有效的JSON或JSONP")
    start = min(start_candidates)
    end_obj = text.rfind("}")
    end_arr = text.rfind("]")
    end = max(end_obj, end_arr)
    if end < start:
        raise ValueError("无法定位JSONP正文")
    return json.loads(text[start : end + 1])


def get_path(payload: Any, path: str | None) -> Any:
    if path is None:
        return None
    current = payload
    for part in path.split("."):
        match = re.fullmatch(r"([^\[]+)(?:\[(\d+)\])?", part)
        if not match:
            return None
        key, index = match.groups()
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
        if index is not None:
            if not isinstance(current, list) or int(index) >= len(current):
                return None
            current = current[int(index)]
    return current


def infer_pages(payload: Any, spec: RequestSpec) -> int:
    candidates: list[int] = []
    if isinstance(payload, dict):
        for path in (
            "result.pages",
            "pages",
            "data.pages",
            "data.total_pages",
            "data.totalPages",
            "data.page_count",
            "data.pageCount",
        ):
            value = get_path(payload, path)
            if isinstance(value, (int, float)) and value > 0:
                candidates.append(int(value))

        total = None
        for path in ("result.count", "data.total_hits", "data.total", "total", "count"):
            value = get_path(payload, path)
            if isinstance(value, (int, float)) and value >= 0:
                total = int(value)
                break
        if total is not None:
            page_size = _page_size(spec)
            if page_size > 0:
                candidates.append(max(1, (total + page_size - 1) // page_size))
    return max(candidates, default=1)


def _page_size(spec: RequestSpec) -> int:
    for key in ("pageSize", "page_size", "ps", "pz"):
        value = spec.params.get(key)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass
    if isinstance(spec.body, dict):
        args = spec.body.get("args") if isinstance(spec.body.get("args"), dict) else spec.body
        for key in ("pageSize", "page_size", "ps", "pz"):
            try:
                if args.get(key) is not None:
                    return int(args[key])
            except (TypeError, ValueError, AttributeError):
                pass
    return 0


def with_page(spec: RequestSpec, page: int) -> RequestSpec:
    copied = spec.model_copy(deep=True)
    for key in ("pageNumber", "page_index", "page", "p", "pi"):
        if key in copied.params:
            copied.params[key] = str(page)
            return copied
    if isinstance(copied.body, dict):
        args = copied.body.get("args") if isinstance(copied.body.get("args"), dict) else copied.body
        for key in ("pageNumber", "page_index", "page", "p", "pi"):
            if key in args:
                args[key] = page
                return copied
    return copied


class HttpClient:
    def __init__(self, settings: Settings, raw_dir: Path):
        self.settings = settings
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            }
        )

    @staticmethod
    def request_fingerprint(spec: RequestSpec) -> str:
        canonical = json.dumps(spec.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def request(self, spec: RequestSpec, group_id: str, page: int = 1) -> PageResponse:
        fingerprint = self.request_fingerprint(spec)
        cache_path = self.raw_dir / f"{group_id}_{fingerprint}.json.gz"
        if cache_path.exists():
            with gzip.open(cache_path, "rt", encoding="utf-8") as fh:
                cached = json.load(fh)
            return PageResponse(**cached)

        url = f"{spec.scheme}://{spec.host}{spec.path}"
        headers = {**spec.headers}
        started = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(1, self.settings.retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "method": spec.method.upper(),
                    "url": url,
                    "params": spec.params,
                    "headers": headers,
                    "timeout": self.settings.timeout,
                }
                if spec.method.upper() != "GET" and spec.body is not None:
                    content_type = headers.get("Content-Type", "")
                    if "text/plain" in content_type:
                        kwargs["data"] = json.dumps(spec.body, ensure_ascii=False)
                    else:
                        kwargs["json"] = spec.body
                response = self.session.request(**kwargs)
                raw = response.content
                if response.status_code in {403, 429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
                response.raise_for_status()
                payload = parse_json_or_jsonp(raw)
                elapsed = time.perf_counter() - started
                result = PageResponse(
                    request={
                        "method": spec.method.upper(),
                        "url": response.url,
                        "params": spec.params,
                        "body": spec.body,
                        "page": page,
                    },
                    response={
                        "fetched_at_utc": utc_now(),
                        "http_status": response.status_code,
                        "elapsed_seconds": round(elapsed, 6),
                        "content_type": response.headers.get("Content-Type", ""),
                        "size_bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "attempt": attempt,
                    },
                    payload=payload,
                    raw_path=str(cache_path),
                )
                with gzip.open(cache_path, "wt", encoding="utf-8") as fh:
                    json.dump(result.__dict__, fh, ensure_ascii=False)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self.settings.retries:
                    break
                delay = (2 ** (attempt - 1)) + random.random()
                time.sleep(delay)
        raise RuntimeError(f"请求失败: {url}: {last_error}") from last_error

    def request_all_pages(
        self,
        spec: RequestSpec,
        group_id: str,
        record_path: str | None,
    ) -> tuple[list[PageResponse], list[dict[str, Any]]]:
        first = self.request(spec, group_id, page=1)
        pages = [first]
        total_pages = infer_pages(first.payload, spec)

        if total_pages > 1:
            with ThreadPoolExecutor(max_workers=min(self.settings.page_workers, total_pages - 1)) as pool:
                futures = {
                    pool.submit(self.request, with_page(spec, page), group_id, page): page
                    for page in range(2, total_pages + 1)
                }
                for future in as_completed(futures):
                    pages.append(future.result())
            pages.sort(key=lambda item: int(item.request.get("page", 1)))

        records: list[dict[str, Any]] = []
        for page in pages:
            extracted = get_path(page.payload, record_path)
            if isinstance(extracted, list):
                records.extend(item for item in extracted if isinstance(item, dict))
            elif isinstance(extracted, dict):
                records.append(extracted)
        return pages, records
