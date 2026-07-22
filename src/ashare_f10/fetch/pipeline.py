from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ashare_f10.config import Settings
from ashare_f10.config import settings as default_settings
from ashare_f10.fetch.client_v2 import HttpClient
from ashare_f10.fetch.manifest import load_manifest
from ashare_f10.fetch.security import parse_security, replace_security_tokens
from ashare_f10.models import GroupResult, RequestSpec, SecurityIdentity

ProgressCallback = Callable[[dict[str, Any]], None]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        fingerprint = hashlib.sha256(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if fingerprint not in seen:
            seen.add(fingerprint)
            output.append(record)
    return output


def _payload_is_success(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return payload is not None
    if payload.get("success") is False:
        return False
    if payload.get("code") not in (None, 0, "0"):
        return False
    if payload.get("rc") not in (None, 0, "0"):
        return False
    return True


def _validate_records(records: list[dict[str, Any]], expected_fields: list[str], payloads: list[Any]) -> bool:
    if not payloads or not all(_payload_is_success(payload) for payload in payloads):
        return False
    if not expected_fields or not records:
        return True
    available = {key for record in records for key in record}
    expected = set(expected_fields)
    if not expected:
        return True
    return len(available & expected) / len(expected) >= 0.7


class FetchPipeline:
    def __init__(
        self,
        stock_code: str,
        output_dir: Path,
        settings: Settings | None = None,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ):
        self.settings = settings or default_settings
        self.identity: SecurityIdentity = parse_security(stock_code)
        self.output_dir = output_dir
        self.raw_dir = output_dir / "raw"
        self.group_dir = output_dir / "groups"
        self.checkpoint_path = output_dir / "checkpoint.json"
        self.progress = progress or (lambda _: None)
        self.cancel_event = cancel_event or threading.Event()
        self.manifest = load_manifest()
        self.client = HttpClient(self.settings, self.raw_dir)
        self.results: dict[str, GroupResult] = {}
        self.group_dir.mkdir(parents=True, exist_ok=True)

    def _emit(self, **event: Any) -> None:
        self.progress({"at_utc": utc_now(), **event})

    def _save_group(self, result: GroupResult) -> None:
        path = self.group_dir / f"{result.group_id}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        self.results[result.group_id] = result
        self._save_checkpoint()

    def _load_existing(self) -> None:
        for path in self.group_dir.glob("*.json"):
            try:
                result = GroupResult.model_validate_json(path.read_text(encoding="utf-8"))
                if result.success:
                    self.results[result.group_id] = result
            except Exception:
                continue

    def _save_checkpoint(self) -> None:
        payload = {
            "security": self.identity.model_dump(),
            "updated_at_utc": utc_now(),
            "completed_group_ids": sorted(self.results),
            "completed_count": len(self.results),
            "total_count": len(self.manifest["groups"]),
        }
        self.checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _template_spec(self, raw: dict[str, Any]) -> RequestSpec:
        converted = replace_security_tokens(copy.deepcopy(raw), self.identity)
        # POST news service has an explicit numeric market field.
        if isinstance(converted.get("body"), dict):
            args = converted["body"].get("args")
            if isinstance(args, dict) and "market" in args:
                args["market"] = str(self.identity.market_id)
        return RequestSpec.model_validate(converted)

    def _execute_requests(
        self,
        group: dict[str, Any],
        request_items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[Any], list[dict[str, Any]], list[str]]:
        records: list[dict[str, Any]] = []
        payloads: list[Any] = []
        requests_log: list[dict[str, Any]] = []
        errors: list[str] = []
        for item in request_items:
            if self.cancel_event.is_set():
                raise RuntimeError("任务已取消")
            try:
                spec = self._template_spec(item["request_spec"])
                pages, page_records = self.client.request_all_pages(
                    spec, group["group_id"], item.get("record_path")
                )
                records.extend(page_records)
                payloads.extend(page.payload for page in pages)
                requests_log.extend({"request": page.request, "response": page.response} for page in pages)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        return _dedupe_records(records), payloads, requests_log, errors

    def _execute_standard_group(self, group: dict[str, Any]) -> GroupResult:
        started = utc_now()
        self._emit(type="group_started", group_id=group["group_id"], family=group["family"])

        candidate_records, candidate_payloads, candidate_log, candidate_errors = self._execute_requests(
            group, group.get("candidate_requests", [])
        )
        candidate_ok = not candidate_errors and _validate_records(
            candidate_records, group.get("expected_fields", []), candidate_payloads
        )

        used_fallback = False
        records = candidate_records
        payloads = candidate_payloads
        requests_log = candidate_log
        errors = candidate_errors

        if not candidate_ok and group.get("fallback_requests"):
            used_fallback = True
            records, payloads, requests_log, errors = self._execute_requests(
                group, group["fallback_requests"]
            )

        success = not errors and bool(payloads)
        result = GroupResult(
            group_id=group["group_id"],
            theme=group["theme"],
            family=group["family"],
            strategy=group["strategy"],
            success=success,
            used_fallback=used_fallback,
            record_count=len(records),
            records=records,
            payloads=payloads,
            requests=requests_log,
            errors=errors,
            started_at_utc=started,
            completed_at_utc=utc_now(),
        )
        self._emit(
            type="group_completed",
            group_id=group["group_id"],
            family=group["family"],
            success=success,
            record_count=len(records),
            used_fallback=used_fallback,
        )
        return result

    def _find_family(self, family: str) -> list[GroupResult]:
        return [result for result in self.results.values() if result.family == family]

    @staticmethod
    def _recursive_find_dicts(value: Any, key: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(value, dict):
            if key in value:
                found.append(value)
            for child in value.values():
                found.extend(FetchPipeline._recursive_find_dicts(child, key))
        elif isinstance(value, list):
            for child in value:
                found.extend(FetchPipeline._recursive_find_dicts(child, key))
        return found

    def _execute_dynamic_group(self, group: dict[str, Any]) -> GroupResult:
        started = utc_now()
        dynamic = group["dynamic_source"]
        identifiers: list[str] = []

        if dynamic["kind"] == "announcement_art_codes":
            for source in self._find_family(dynamic["source_family"]):
                identifiers.extend(
                    str(record.get(dynamic["key"])) for record in source.records if record.get(dynamic["key"])
                )
        elif dynamic["kind"] == "research_art_codes":
            for source in self._find_family(dynamic["source_family"]):
                for payload in source.payloads:
                    section = payload.get(dynamic.get("section")) if isinstance(payload, dict) else None
                    if isinstance(section, list):
                        identifiers.extend(
                            str(record.get(dynamic["key"]))
                            for record in section
                            if isinstance(record, dict) and record.get(dynamic["key"])
                        )
                    else:
                        identifiers.extend(
                            str(record.get(dynamic["key"]))
                            for record in self._recursive_find_dicts(payload, dynamic["key"])
                            if record.get(dynamic["key"])
                        )

        identifiers = list(
            dict.fromkeys(identifier for identifier in identifiers if identifier and identifier != "None")
        )
        identifiers = identifiers[: int(dynamic.get("max_items", 10))]
        records: list[dict[str, Any]] = []
        payloads: list[Any] = []
        request_log: list[dict[str, Any]] = []
        errors: list[str] = []

        def fetch_identifier(identifier: str) -> tuple[Any, dict[str, Any], str | None]:
            try:
                if group["family"] == "/api/content/ann":
                    raw_spec = {
                        "method": "GET",
                        "scheme": "https",
                        "host": "np-cnotice-pc.eastmoney.com",
                        "path": "/api/content/ann",
                        "params": {"page_index": "1", "client_source": "PC", "art_code": identifier},
                        "body": None,
                        "headers": {},
                    }
                else:
                    raw_spec = {
                        "method": "GET",
                        "scheme": "https",
                        "host": "np-creport-pc.eastmoney.com",
                        "path": "/api/content/rep",
                        "params": {
                            "art_code": identifier,
                            "stock": "",
                            "client_source": "pc",
                            "page_index": "1",
                        },
                        "body": None,
                        "headers": {},
                    }
                page = self.client.request(RequestSpec.model_validate(raw_spec), group["group_id"])
                data = page.payload.get("data") if isinstance(page.payload, dict) else None
                record = data if isinstance(data, dict) else {"art_code": identifier, "payload": page.payload}
                return record, {"request": page.request, "response": page.response}, None
            except Exception as exc:  # noqa: BLE001
                return {}, {}, str(exc)

        with ThreadPoolExecutor(
            max_workers=min(self.settings.page_workers, max(1, len(identifiers)))
        ) as pool:
            futures = {pool.submit(fetch_identifier, identifier): identifier for identifier in identifiers}
            for future in as_completed(futures):
                record, log, error = future.result()
                if error:
                    errors.append(error)
                else:
                    records.append(record)
                    request_log.append(log)
                    payloads.append(record)

        success = not errors or bool(records)
        result = GroupResult(
            group_id=group["group_id"],
            theme=group["theme"],
            family=group["family"],
            strategy=group["strategy"],
            success=success,
            used_fallback=False,
            record_count=len(records),
            records=_dedupe_records(records),
            payloads=payloads,
            requests=request_log,
            errors=errors,
            started_at_utc=started,
            completed_at_utc=utc_now(),
        )
        self._emit(
            type="group_completed",
            group_id=group["group_id"],
            family=group["family"],
            success=success,
            record_count=len(records),
            used_fallback=False,
        )
        return result

    def run(self, resume: bool = True) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if resume:
            self._load_existing()

        groups: list[dict[str, Any]] = self.manifest["groups"]
        pageajax = next(group for group in groups if group["family"] == "PageAjax")
        if pageajax["group_id"] not in self.results:
            self._save_group(self._execute_standard_group(pageajax))

        standard = [
            group
            for group in groups
            if group["family"] != "PageAjax"
            and "dynamic_source" not in group
            and group["group_id"] not in self.results
        ]
        self._emit(type="batch_started", batch="standard", count=len(standard))
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as pool:
            futures = {pool.submit(self._execute_standard_group, group): group for group in standard}
            for future in as_completed(futures):
                if self.cancel_event.is_set():
                    break
                result = future.result()
                self._save_group(result)

        dynamic = [
            group for group in groups if "dynamic_source" in group and group["group_id"] not in self.results
        ]
        for group in dynamic:
            if self.cancel_event.is_set():
                break
            self._save_group(self._execute_dynamic_group(group))

        failed = [result for result in self.results.values() if not result.success]
        combined = {
            "metadata": {
                "schema_version": "1.0.0",
                "security": self.identity.model_dump(),
                "completed_at_utc": utc_now(),
                "fixed_manifest_version": self.manifest["schema_version"],
                "group_count": len(groups),
                "completed_group_count": len(self.results),
                "failed_group_count": len(failed),
                "source": "Eastmoney live APIs",
            },
            "groups": [result.model_dump() for result in self.results.values()],
        }
        (self.output_dir / "combined.json").write_text(
            json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return combined
