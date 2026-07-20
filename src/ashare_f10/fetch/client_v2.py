from __future__ import annotations

import gzip
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any

import requests

from ashare_f10.fetch.client import HttpClient as BaseHttpClient
from ashare_f10.fetch.client import PageResponse, parse_json_or_jsonp, utc_now
from ashare_f10.models import RequestSpec

QUOTE_HOST = "push2.eastmoney.com"
QUOTE_PATH = "/api/qt/stock/get"
QUOTE_STABLE_UT = "bd1d9ddb04089700cf9c27f6f7426281"
QUOTE_IDENTITY_FIELDS = ("f57", "f58")
QUOTE_CORE_FIELDS = (
    "f57",
    "f58",
    "f47",
    "f43",
    "f169",
    "f170",
    "f44",
    "f45",
    "f46",
    "f48",
    "f60",
    "f168",
    "f164",
    "f50",
    "f171",
)


def is_eastmoney_quote_request(spec: RequestSpec) -> bool:
    return spec.host.lower() == QUOTE_HOST and spec.path == QUOTE_PATH


def _page_security_code(params: dict[str, Any]) -> str:
    secid = str(params.get("secid", ""))
    if "." not in secid:
        return ""
    market, code = secid.split(".", 1)
    if not code.isdigit():
        return ""
    prefix = {"0": "SZ", "1": "SH", "2": "BJ"}.get(market, "")
    return f"{prefix}{code}" if prefix else code


def build_quote_headers(spec: RequestSpec) -> dict[str, str]:
    """Build stable browser-like headers without copying expiring browser tokens.

    Browser requests may include ``ct`` and a second ``ut`` header. Those values
    are session-specific anti-bot tokens and must not be persisted in the
    manifest. The stable query-string ``ut`` value is retained separately.
    """

    headers = {str(key): str(value) for key, value in spec.headers.items()}
    for key in list(headers):
        if key.lower() in {
            "ct",
            "ut",
            "cookie",
            "sec-ch-ua",
            "sec-ch-ua-mobile",
            "sec-ch-ua-platform",
        }:
            headers.pop(key, None)
    headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.7,en;q=0.5",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "close",
            "Origin": "https://emweb.eastmoney.com",
            "Referer": "https://emweb.eastmoney.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
    )
    page_code = _page_security_code(spec.params)
    if page_code:
        headers["pageurl"] = (
            "https://emweb.eastmoney.com/PC_HSF10/pages/index.html"
            f"?type=web&color=w&ischoice=1&code={page_code}#/zxgg"
        )
    return headers


def build_quote_params(spec: RequestSpec, fields: list[str] | None = None) -> dict[str, Any]:
    params = dict(spec.params)
    params.setdefault("ut", QUOTE_STABLE_UT)
    params.setdefault("fltt", "2")
    params.setdefault("wbp2u", "3208325652266276|0|1|0|web")
    params["v"] = f"{random.random():.17f}".split(".", 1)[1]
    if fields is not None:
        params["fields"] = ",".join(fields)
    return params


def _quote_delay(attempt: int) -> float:
    return min(5.0, 0.55 * (2 ** max(0, attempt - 1))) + random.uniform(0.15, 0.65)


def _with_identity_fields(fields: list[str]) -> list[str]:
    extras = [field for field in fields if field not in QUOTE_IDENTITY_FIELDS]
    return list(dict.fromkeys([*QUOTE_IDENTITY_FIELDS, *extras]))


class HttpClient(BaseHttpClient):
    """Base client plus a resilient transport for Eastmoney's realtime quote API."""

    def _quote_once(
        self,
        spec: RequestSpec,
        fields: list[str] | None,
        max_attempts: int,
    ) -> tuple[requests.Response, dict[str, Any], bytes, int, list[str]]:
        url = f"{spec.scheme}://{spec.host}{spec.path}"
        errors: list[str] = []
        for attempt in range(1, max_attempts + 1):
            session = requests.Session()
            session.headers.update(self.session.headers)
            try:
                response = session.request(
                    method="GET",
                    url=url,
                    params=build_quote_params(spec, fields),
                    headers=build_quote_headers(spec),
                    timeout=(10, self.settings.timeout),
                    allow_redirects=True,
                )
                raw = response.content
                if response.status_code in {403, 408, 425, 429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
                response.raise_for_status()
                payload = parse_json_or_jsonp(raw)
                if not isinstance(payload, dict):
                    raise ValueError("行情接口未返回JSON对象")
                if payload.get("rc") not in (None, 0, "0"):
                    raise ValueError(f"行情接口rc={payload.get('rc')}")
                data = payload.get("data")
                if not isinstance(data, dict) or not data:
                    raise ValueError("行情接口data为空")
                requested_code = str(spec.params.get("secid", "")).split(".")[-1]
                if "f57" in data and str(data.get("f57", "")) != requested_code:
                    raise ValueError("行情接口返回的证券代码与请求不一致")
                if fields is None or "f57" in fields:
                    if str(data.get("f57", "")) != requested_code:
                        raise ValueError("行情接口未返回可校验的证券代码")
                return response, payload, raw, attempt, errors
            except Exception as exc:  # noqa: BLE001
                errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                if attempt < max_attempts:
                    time.sleep(_quote_delay(attempt))
            finally:
                session.close()
        raise RuntimeError("；".join(errors[-max_attempts:]))

    def _quote_field_batches(self, fields: list[str]) -> list[list[str]]:
        core = [field for field in QUOTE_CORE_FIELDS if field in fields]
        remaining = [field for field in fields if field not in core]
        batches: list[list[str]] = []
        if core:
            batches.append(_with_identity_fields(core))
        for start in range(0, len(remaining), 10):
            extra_fields = remaining[start : start + 10]
            if extra_fields:
                batches.append(_with_identity_fields(extra_fields))
        return batches or [_with_identity_fields(fields)]

    def _quote_batch_recursive(
        self,
        spec: RequestSpec,
        fields: list[str],
    ) -> list[tuple[requests.Response, dict[str, Any], bytes, int, list[str], list[str]]]:
        requested_fields = _with_identity_fields(fields)
        try:
            response, payload, raw, attempt, errors = self._quote_once(
                spec,
                requested_fields,
                max(3, self.settings.retries),
            )
            return [(response, payload, raw, attempt, errors, requested_fields)]
        except Exception:
            extras = [field for field in requested_fields if field not in QUOTE_IDENTITY_FIELDS]
            if len(extras) <= 1:
                raise
            midpoint = max(1, len(extras) // 2)
            return self._quote_batch_recursive(spec, extras[:midpoint]) + self._quote_batch_recursive(
                spec,
                extras[midpoint:],
            )

    def _write_quote_cache(self, cache_path: Path, result: PageResponse) -> PageResponse:
        with gzip.open(cache_path, "wt", encoding="utf-8") as handle:
            json.dump(result.__dict__, handle, ensure_ascii=False)
        return result

    def _request_quote(self, spec: RequestSpec, group_id: str, page: int) -> PageResponse:
        fingerprint = self.request_fingerprint(spec)
        cache_path = self.raw_dir / f"{group_id}_{fingerprint}.json.gz"
        if cache_path.exists():
            with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
                return PageResponse(**json.load(handle))

        started = time.perf_counter()
        full_errors: list[str] = []
        try:
            response, payload, raw, attempt, full_errors = self._quote_once(
                spec,
                None,
                max(5, self.settings.retries),
            )
            elapsed = time.perf_counter() - started
            result = PageResponse(
                request={
                    "method": "GET",
                    "url": response.url,
                    "params": dict(spec.params),
                    "body": None,
                    "page": page,
                    "transport_profile": "eastmoney_quote_resilient_v1",
                },
                response={
                    "fetched_at_utc": utc_now(),
                    "http_status": response.status_code,
                    "elapsed_seconds": round(elapsed, 6),
                    "content_type": response.headers.get("Content-Type", ""),
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "attempt": attempt,
                    "transport_profile": "eastmoney_quote_resilient_v1",
                    "split_fields": False,
                },
                payload=payload,
                raw_path=str(cache_path),
            )
            return self._write_quote_cache(cache_path, result)
        except Exception as full_error:  # noqa: BLE001
            full_errors.append(str(full_error))

        fields = [field.strip() for field in str(spec.params.get("fields", "")).split(",") if field.strip()]
        if not fields:
            raise RuntimeError(f"行情接口请求失败且无法拆分fields：{full_errors[-1]}")

        merged_payload: dict[str, Any] | None = None
        merged_data: dict[str, Any] = {}
        batch_urls: list[str] = []
        batch_attempts = 0
        batch_errors: list[str] = []
        for batch in self._quote_field_batches(fields):
            results = self._quote_batch_recursive(spec, batch)
            for response, payload, _raw, attempts, errors, actual_fields in results:
                batch_urls.append(response.url)
                batch_attempts += attempts
                batch_errors.extend(errors)
                if merged_payload is None:
                    merged_payload = {key: value for key, value in payload.items() if key != "data"}
                data = payload.get("data")
                if not isinstance(data, dict):
                    raise RuntimeError(f"行情拆分请求未返回data：{actual_fields}")
                merged_data.update(data)

        if merged_payload is None or not merged_data:
            raise RuntimeError(f"行情接口拆分请求失败：{full_errors[-3:]}")
        requested_code = str(spec.params.get("secid", "")).split(".")[-1]
        if str(merged_data.get("f57", "")) != requested_code:
            raise RuntimeError("行情拆分请求返回的证券代码与请求不一致")

        merged_payload["data"] = merged_data
        raw = json.dumps(merged_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        elapsed = time.perf_counter() - started
        result = PageResponse(
            request={
                "method": "GET",
                "url": batch_urls[0] if batch_urls else f"{spec.scheme}://{spec.host}{spec.path}",
                "params": dict(spec.params),
                "body": None,
                "page": page,
                "transport_profile": "eastmoney_quote_resilient_v1",
                "field_batch_urls": batch_urls,
            },
            response={
                "fetched_at_utc": utc_now(),
                "http_status": 200,
                "elapsed_seconds": round(elapsed, 6),
                "content_type": "application/json; charset=UTF-8",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "attempt": batch_attempts,
                "transport_profile": "eastmoney_quote_resilient_v1",
                "split_fields": True,
                "full_request_errors": full_errors[-5:],
                "batch_retry_errors": batch_errors[-10:],
            },
            payload=merged_payload,
            raw_path=str(cache_path),
        )
        return self._write_quote_cache(cache_path, result)

    def request(self, spec: RequestSpec, group_id: str, page: int = 1) -> PageResponse:
        if is_eastmoney_quote_request(spec):
            return self._request_quote(spec, group_id, page)
        return super().request(spec, group_id, page)
