from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ashare_f10.api.jobs import ACTIVE_STATUSES
from ashare_f10.api.jobs import JobManager as BaseJobManager
from ashare_f10.models import GroupResult, JobState

NAME_KEYS = (
    "SECURITY_NAME_ABBR",
    "f58",
    "SECURITY_NAME",
    "SECURITY_NAME_A",
    "short_name",
    "ORG_NAME_ABBR",
    "name",
)
CODE_KEYS = (
    "SECURITY_CODE",
    "SECUCODE",
    "SECURITYCODE",
    "SECURITY_CODE_A",
    "f57",
    "code",
    "secucode",
    "security_code",
)
PREFERRED_NAME_FAMILIES = {
    "/api/qt/stock/get": 0,
    "RPT_F10_ORG_BASICINFO": 1,
    "RPT_HSF9_BASIC_ORGINFO": 2,
    "PageAjax": 3,
}
INVALID_NAMES = {"", "名称获取中", "证券名称", "股票名称", "None", "null", "--", "-"}


def normalize_security_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        parts = text.split(".")
        for part in reversed(parts):
            if len(part) == 6 and part.isdigit():
                return part
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and len(text) >= 8 and text[-6:].isdigit():
            return text[-6:]
    digits = "".join(character for character in text if character.isdigit())
    return digits[-6:] if len(digits) >= 6 else ""


def _valid_security_name(value: Any, stock_code: str) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if candidate in INVALID_NAMES or candidate == stock_code:
        return ""
    if candidate.endswith((".SH", ".SZ", ".BJ")) or candidate.isdigit():
        return ""
    if len(candidate) > 80:
        return ""
    return candidate


def extract_security_name(value: Any, stock_code: str) -> str:
    """Return a name only when it is in the same object as the requested code.

    F10 payloads contain peer companies, research organisations and shareholders.
    Looking for the first ``*_NAME`` anywhere in a nested payload can therefore
    assign another company's name to every task.  A candidate is accepted only
    when the same dictionary also carries a code matching ``stock_code``.
    """

    target = normalize_security_code(stock_code)
    if not target:
        return ""
    stack: list[tuple[Any, int]] = [(value, 0)]
    visited = 0
    while stack and visited < 20000:
        current, depth = stack.pop()
        visited += 1
        if depth > 8:
            continue
        if isinstance(current, dict):
            codes = {
                normalize_security_code(current.get(key))
                for key in CODE_KEYS
                if current.get(key) not in (None, "")
            }
            if target in codes:
                for key in NAME_KEYS:
                    candidate = _valid_security_name(current.get(key), target)
                    if candidate:
                        return candidate
            children = list(current.values())
            for child in reversed(children[:300]):
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            for child in reversed(current[:500]):
                stack.append((child, depth + 1))
    return ""


class JobManager(BaseJobManager):
    """Task manager with secure name resolution and stronger legacy repair."""

    @staticmethod
    def _load_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

    def _iter_output_group_payloads(self, state: JobState) -> Iterator[dict[str, Any]]:
        root = Path(state.output_dir)
        group_dir = root / "groups"
        if group_dir.exists():
            for path in sorted(group_dir.glob("*.json")):
                payload = self._load_json(path)
                if isinstance(payload, dict):
                    yield payload

        for path in (root / "combined.json", root / "exports" / f"{state.stock_code}_F10_full.json"):
            payload = self._load_json(path)
            if not isinstance(payload, dict):
                continue
            groups = payload.get("groups")
            if isinstance(groups, list):
                for group in groups:
                    if isinstance(group, dict):
                        yield group

        exports_dir = root / "exports"
        if exports_dir.exists():
            for path in sorted(exports_dir.glob("*_F10_full.json")):
                if path.name == f"{state.stock_code}_F10_full.json":
                    continue
                payload = self._load_json(path)
                if not isinstance(payload, dict):
                    continue
                groups = payload.get("groups")
                if isinstance(groups, list):
                    for group in groups:
                        if isinstance(group, dict):
                            yield group

    @staticmethod
    def _group_quality(raw: dict[str, Any]) -> tuple[int, int, int, int]:
        records = raw.get("records") if isinstance(raw.get("records"), list) else []
        payloads = raw.get("payloads") if isinstance(raw.get("payloads"), list) else []
        try:
            reported = int(raw.get("record_count", len(records)))
        except (TypeError, ValueError):
            reported = -1
        return (
            int(reported == len(records)),
            int(bool(raw.get("success"))),
            len(records),
            len(payloads),
        )

    def _best_saved_groups(self, state: JobState) -> dict[str, dict[str, Any]]:
        selected: dict[str, dict[str, Any]] = {}
        for raw in self._iter_output_group_payloads(state):
            group_id = str(raw.get("group_id", ""))
            if group_id not in self.group_definitions:
                continue
            previous = selected.get(group_id)
            if previous is None or self._group_quality(raw) > self._group_quality(previous):
                selected[group_id] = raw
        return selected

    def _coerce_group_result(self, state: JobState, raw: dict[str, Any]) -> GroupResult:
        try:
            return GroupResult.model_validate(raw)
        except Exception as validation_error:  # noqa: BLE001
            group_id = str(raw.get("group_id", ""))
            definition = self.group_definitions[group_id]
            records = raw.get("records") if isinstance(raw.get("records"), list) else []
            payloads = raw.get("payloads") if isinstance(raw.get("payloads"), list) else []
            requests_log = raw.get("requests") if isinstance(raw.get("requests"), list) else []
            errors = [str(item) for item in raw.get("errors", []) if item]
            try:
                reported = int(raw.get("record_count", len(records)))
            except (TypeError, ValueError):
                reported = -1
            if reported != len(records):
                errors.append(
                    f"历史缓存record_count={reported}，records实际为{len(records)}，已标记为失败并等待重试"
                )
            errors.append(f"历史请求组校验失败：{validation_error}")
            started = str(raw.get("started_at_utc") or state.started_at_utc or state.created_at_utc)
            completed = str(raw.get("completed_at_utc") or state.completed_at_utc or state.updated_at_utc)
            return GroupResult(
                group_id=group_id,
                theme=str(raw.get("theme") or definition.get("theme", "")),
                family=str(raw.get("family") or definition.get("family", "")),
                strategy=str(raw.get("strategy") or definition.get("strategy", "")),
                success=False,
                used_fallback=bool(raw.get("used_fallback")),
                record_count=len(records),
                records=records,
                payloads=payloads,
                requests=requests_log,
                errors=list(dict.fromkeys(errors)),
                started_at_utc=started,
                completed_at_utc=completed,
            )

    def _discover_name_from_output(self, state: JobState) -> str:
        candidates: list[tuple[int, str]] = []
        for raw in self._iter_output_group_payloads(state):
            family = str(raw.get("family", ""))
            priority = PREFERRED_NAME_FAMILIES.get(family, 20)
            for section in (raw.get("records"), raw.get("payloads"), raw):
                candidate = extract_security_name(section, state.stock_code)
                if candidate:
                    candidates.append((priority, candidate))
                    break
        if not candidates:
            return ""
        best_priority = min(priority for priority, _name in candidates)
        names = [name for priority, name in candidates if priority == best_priority]
        return Counter(names).most_common(1)[0][0]

    def _sync_group_files(self, state: JobState) -> None:
        self._initialize_group_rows(state.job_id)
        for raw in self._best_saved_groups(state).values():
            result = self._coerce_group_result(state, raw)
            self._save_result_group(state.job_id, result)

        completed, successful, failed = self._group_counts(state.job_id)
        state.completed_groups = completed
        state.successful_groups = successful
        state.failed_groups = failed
        discovered = self._discover_name_from_output(state)
        if discovered:
            state.stock_name = discovered

    def _backfill_legacy_jobs(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at_utc").fetchall()
        stock_codes: set[str] = set()
        for row in rows:
            try:
                state = self._state_from_row(row)
            except Exception:  # noqa: BLE001
                continue
            stock_codes.add(state.stock_code)
            self._initialize_group_rows(state.job_id)
            if state.status in ACTIVE_STATUSES:
                state.status = "PARTIAL" if state.completed_groups else "FAILED"
                state.message = "服务重启后原执行进程已结束，可重新执行或重试失败子任务"
            self._sync_group_files(state)
            if state.status == "COMPLETED" and (
                state.failed_groups
                or not state.total_groups
                or state.completed_groups != state.total_groups
            ):
                state.status = "PARTIAL" if state.completed_groups else "FAILED"
                state.message = "历史任务状态与子任务文件不一致，请重新执行或重试失败子任务"
            self._save(state)
        for stock_code in stock_codes:
            self._reconcile_current_pointer(stock_code)

    def _set_current_pointer(self, state: JobState, allow_partial: bool = False) -> None:
        if not allow_partial and state.completed_groups != state.total_groups:
            raise ValueError("只有113个子任务全部结束且失败0的完整任务才能设为当前版本")
        super()._set_current_pointer(state, allow_partial=allow_partial)

    def _select_fallback_current(self, stock_code: str, exclude_job_id: str | None = None) -> JobState | None:
        params: list[Any] = [stock_code]
        exclusion = ""
        if exclude_job_id:
            exclusion = " AND job_id<>?"
            params.append(exclude_job_id)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT * FROM jobs
                WHERE stock_code=?
                  AND status='COMPLETED'
                  AND failed_groups=0
                  AND total_groups>0
                  AND completed_groups=total_groups{exclusion}
                ORDER BY coalesce(completed_at_utc, updated_at_utc) DESC, created_at_utc DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            connection.execute("UPDATE jobs SET is_current=0 WHERE stock_code=?", (stock_code,))
        if row:
            state = self._state_from_row(row)
            self._set_current_pointer(state)
            return state
        pointer = self._pointer_path(stock_code)
        if pointer.exists():
            pointer.unlink()
        return None

    def _reconcile_current_pointer(self, stock_code: str) -> None:
        pointer = self._pointer_path(stock_code)
        job_id = ""
        if pointer.exists():
            try:
                job_id = str(json.loads(pointer.read_text(encoding="utf-8")).get("job_id", ""))
            except Exception:  # noqa: BLE001
                job_id = ""
        if job_id:
            state = self.get(job_id, hydrate=False)
            if (
                state
                and state.status == "COMPLETED"
                and not state.failed_groups
                and state.total_groups > 0
                and state.completed_groups == state.total_groups
            ):
                self._set_current_pointer(state)
                return
        self._select_fallback_current(stock_code)


__all__ = ["JobManager", "extract_security_name", "normalize_security_code"]
