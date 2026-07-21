from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ashare_f10.config import Settings
from ashare_f10.config import settings as default_settings
from ashare_f10.export.bundle import build_exports
from ashare_f10.fetch.manifest import load_manifest
from ashare_f10.fetch.pipeline import FetchPipeline
from ashare_f10.fetch.security import parse_security
from ashare_f10.models import GroupResult, JobGroupState, JobState


ACTIVE_STATUSES = {"PENDING", "RUNNING", "RETRYING", "DELETING"}
NAME_KEYS = (
    "SECURITY_NAME_ABBR",
    "SECURITY_NAME",
    "SECURITY_NAME_A",
    "f58",
    "short_name",
    "ORG_NAME_ABBR",
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def elapsed_seconds(start: str | None, end: str | None) -> float | None:
    started = parse_utc(start)
    completed = parse_utc(end)
    if not started or not completed:
        return None
    return max(0.0, round((completed - started).total_seconds(), 6))


def extract_security_name(value: Any, stock_code: str, depth: int = 0) -> str:
    if depth > 5:
        return ""
    if isinstance(value, dict):
        for key in NAME_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, str):
                candidate = candidate.strip()
                if candidate and candidate != stock_code and not candidate.endswith((".SH", ".SZ", ".BJ")):
                    return candidate
        for child in list(value.values())[:80]:
            found = extract_security_name(child, stock_code, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for child in value[:80]:
            found = extract_security_name(child, stock_code, depth + 1)
            if found:
                return found
    return ""


class JobManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or default_settings
        self.settings.ensure_dirs()
        self.db_path = self.settings.data_dir / "jobs.sqlite3"
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="f10-job")
        self.cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._active_jobs: set[str] = set()
        self.manifest = load_manifest()
        self.group_definitions = {
            group["group_id"]: {**group, "definition_index": index}
            for index, group in enumerate(self.manifest["groups"])
        }
        self._init_db()
        self._backfill_legacy_jobs()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    stock_code TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
            additions = {
                "stock_name": "TEXT NOT NULL DEFAULT ''",
                "completed_groups": "INTEGER NOT NULL DEFAULT 0",
                "successful_groups": "INTEGER NOT NULL DEFAULT 0",
                "total_groups": "INTEGER NOT NULL DEFAULT 0",
                "failed_groups": "INTEGER NOT NULL DEFAULT 0",
                "started_at_utc": "TEXT",
                "completed_at_utc": "TEXT",
                "duration_seconds": "REAL",
                "is_current": "INTEGER NOT NULL DEFAULT 0",
                "retry_count": "INTEGER NOT NULL DEFAULT 0",
                "last_retry_at_utc": "TEXT",
                "output_dir": "TEXT NOT NULL DEFAULT ''",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_groups (
                    job_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    definition_index INTEGER NOT NULL DEFAULT 0,
                    theme TEXT NOT NULL DEFAULT '',
                    family TEXT NOT NULL DEFAULT '',
                    strategy TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    record_count INTEGER NOT NULL DEFAULT 0,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    used_fallback INTEGER NOT NULL DEFAULT 0,
                    started_at_utc TEXT,
                    completed_at_utc TEXT,
                    duration_seconds REAL,
                    errors_json TEXT NOT NULL DEFAULT '[]',
                    source_urls_json TEXT NOT NULL DEFAULT '[]',
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY(job_id, group_id),
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_code ON jobs(stock_code)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_current ON jobs(stock_code, is_current)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_job_groups_job ON job_groups(job_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_job_groups_status ON job_groups(job_id, status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_job_groups_family ON job_groups(family)")

    def _save(self, state: JobState) -> None:
        state.updated_at_utc = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    job_id, stock_code, stock_name, status, state_json,
                    completed_groups, successful_groups, total_groups, failed_groups,
                    started_at_utc, completed_at_utc, duration_seconds, is_current,
                    retry_count, last_retry_at_utc, output_dir, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    stock_code=excluded.stock_code,
                    stock_name=excluded.stock_name,
                    status=excluded.status,
                    state_json=excluded.state_json,
                    completed_groups=excluded.completed_groups,
                    successful_groups=excluded.successful_groups,
                    total_groups=excluded.total_groups,
                    failed_groups=excluded.failed_groups,
                    started_at_utc=excluded.started_at_utc,
                    completed_at_utc=excluded.completed_at_utc,
                    duration_seconds=excluded.duration_seconds,
                    is_current=excluded.is_current,
                    retry_count=excluded.retry_count,
                    last_retry_at_utc=excluded.last_retry_at_utc,
                    output_dir=excluded.output_dir,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    state.job_id,
                    state.stock_code,
                    state.stock_name,
                    state.status,
                    state.model_dump_json(),
                    state.completed_groups,
                    state.successful_groups,
                    state.total_groups,
                    state.failed_groups,
                    state.started_at_utc,
                    state.completed_at_utc,
                    state.duration_seconds,
                    int(state.is_current),
                    state.retry_count,
                    state.last_retry_at_utc,
                    state.output_dir,
                    state.created_at_utc,
                    state.updated_at_utc,
                ),
            )

    def _state_from_row(self, row: sqlite3.Row) -> JobState:
        state = JobState.model_validate_json(row["state_json"])
        state.stock_name = str(row["stock_name"] or state.stock_name)
        state.status = row["status"]
        state.completed_groups = int(row["completed_groups"] or state.completed_groups)
        state.successful_groups = int(row["successful_groups"] or state.successful_groups)
        state.total_groups = int(row["total_groups"] or state.total_groups)
        state.failed_groups = int(row["failed_groups"] or state.failed_groups)
        state.started_at_utc = row["started_at_utc"] or state.started_at_utc
        state.completed_at_utc = row["completed_at_utc"] or state.completed_at_utc
        state.duration_seconds = row["duration_seconds"] if row["duration_seconds"] is not None else state.duration_seconds
        state.is_current = bool(row["is_current"])
        state.retry_count = int(row["retry_count"] or state.retry_count)
        state.last_retry_at_utc = row["last_retry_at_utc"] or state.last_retry_at_utc
        state.output_dir = str(row["output_dir"] or state.output_dir)
        if state.status == "COMPLETED" and state.failed_groups:
            state.status = "PARTIAL"
        return state

    def _initialize_group_rows(self, job_id: str) -> None:
        now = utc_now()
        rows = [
            (
                job_id,
                group_id,
                definition["definition_index"],
                str(definition.get("theme", "")),
                str(definition.get("family", "")),
                str(definition.get("strategy", "")),
                now,
            )
            for group_id, definition in self.group_definitions.items()
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO job_groups(
                    job_id, group_id, definition_index, theme, family, strategy, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def _group_state_from_row(self, row: sqlite3.Row) -> JobGroupState:
        return JobGroupState(
            job_id=row["job_id"],
            group_id=row["group_id"],
            definition_index=int(row["definition_index"]),
            theme=row["theme"],
            family=row["family"],
            strategy=row["strategy"],
            status=row["status"],
            record_count=int(row["record_count"]),
            attempt_count=int(row["attempt_count"]),
            used_fallback=bool(row["used_fallback"]),
            started_at_utc=row["started_at_utc"],
            completed_at_utc=row["completed_at_utc"],
            duration_seconds=row["duration_seconds"],
            errors=json.loads(row["errors_json"] or "[]"),
            source_urls=json.loads(row["source_urls_json"] or "[]"),
            updated_at_utc=row["updated_at_utc"],
        )

    def _get_group_state(self, job_id: str, group_id: str) -> JobGroupState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM job_groups WHERE job_id=? AND group_id=?",
                (job_id, group_id),
            ).fetchone()
        return self._group_state_from_row(row) if row else None

    def _save_group_state(self, group: JobGroupState) -> None:
        group.updated_at_utc = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_groups(
                    job_id, group_id, definition_index, theme, family, strategy, status,
                    record_count, attempt_count, used_fallback, started_at_utc,
                    completed_at_utc, duration_seconds, errors_json, source_urls_json, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, group_id) DO UPDATE SET
                    definition_index=excluded.definition_index,
                    theme=excluded.theme,
                    family=excluded.family,
                    strategy=excluded.strategy,
                    status=excluded.status,
                    record_count=excluded.record_count,
                    attempt_count=excluded.attempt_count,
                    used_fallback=excluded.used_fallback,
                    started_at_utc=excluded.started_at_utc,
                    completed_at_utc=excluded.completed_at_utc,
                    duration_seconds=excluded.duration_seconds,
                    errors_json=excluded.errors_json,
                    source_urls_json=excluded.source_urls_json,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    group.job_id,
                    group.group_id,
                    group.definition_index,
                    group.theme,
                    group.family,
                    group.strategy,
                    group.status,
                    group.record_count,
                    group.attempt_count,
                    int(group.used_fallback),
                    group.started_at_utc,
                    group.completed_at_utc,
                    group.duration_seconds,
                    json.dumps(group.errors, ensure_ascii=False),
                    json.dumps(group.source_urls, ensure_ascii=False),
                    group.updated_at_utc,
                ),
            )

    def _mark_group_started(self, job_id: str, group_id: str, retrying: bool = False) -> None:
        definition = self.group_definitions[group_id]
        existing = self._get_group_state(job_id, group_id)
        group = existing or JobGroupState(
            job_id=job_id,
            group_id=group_id,
            definition_index=definition["definition_index"],
            theme=str(definition.get("theme", "")),
            family=str(definition.get("family", "")),
            strategy=str(definition.get("strategy", "")),
            updated_at_utc=utc_now(),
        )
        group.status = "RETRYING" if retrying else "RUNNING"
        group.attempt_count += 1
        group.started_at_utc = utc_now()
        group.completed_at_utc = None
        group.duration_seconds = None
        group.errors = []
        self._save_group_state(group)

    def _save_result_group(self, job_id: str, result: GroupResult) -> None:
        definition = self.group_definitions.get(result.group_id, {})
        existing = self._get_group_state(job_id, result.group_id)
        source_urls = []
        for item in result.requests:
            request = item.get("request") if isinstance(item, dict) else None
            if isinstance(request, dict) and request.get("url"):
                source_urls.append(str(request["url"]))
        group = JobGroupState(
            job_id=job_id,
            group_id=result.group_id,
            definition_index=int(definition.get("definition_index", existing.definition_index if existing else 0)),
            theme=result.theme,
            family=result.family,
            strategy=result.strategy,
            status="SUCCESS" if result.success else "FAILED",
            record_count=result.record_count,
            attempt_count=max(1, existing.attempt_count if existing else 1),
            used_fallback=result.used_fallback,
            started_at_utc=result.started_at_utc,
            completed_at_utc=result.completed_at_utc,
            duration_seconds=elapsed_seconds(result.started_at_utc, result.completed_at_utc),
            errors=result.errors,
            source_urls=list(dict.fromkeys(source_urls)),
            updated_at_utc=utc_now(),
        )
        self._save_group_state(group)

    def _group_counts(self, job_id: str) -> tuple[int, int, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, count(*) AS n FROM job_groups WHERE job_id=? GROUP BY status",
                (job_id,),
            ).fetchall()
        counts = {row["status"]: int(row["n"]) for row in rows}
        successful = counts.get("SUCCESS", 0)
        failed = counts.get("FAILED", 0)
        return successful + failed, successful, failed

    def _discover_name_from_output(self, state: JobState) -> str:
        root = Path(state.output_dir)
        for path in sorted((root / "groups").glob("*.json")) if (root / "groups").exists() else []:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            found = extract_security_name(payload.get("records", []), state.stock_code)
            if not found:
                found = extract_security_name(payload.get("payloads", []), state.stock_code)
            if found:
                return found
        combined = root / "combined.json"
        if combined.exists():
            try:
                return extract_security_name(json.loads(combined.read_text(encoding="utf-8")), state.stock_code)
            except Exception:
                return ""
        return ""

    def _sync_group_files(self, state: JobState) -> None:
        self._initialize_group_rows(state.job_id)
        root = Path(state.output_dir)
        group_dir = root / "groups"
        if group_dir.exists():
            for path in group_dir.glob("*.json"):
                try:
                    result = GroupResult.model_validate_json(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                self._save_result_group(state.job_id, result)
                if not state.stock_name:
                    state.stock_name = extract_security_name(result.records, state.stock_code) or extract_security_name(
                        result.payloads, state.stock_code
                    )
        completed, successful, failed = self._group_counts(state.job_id)
        state.completed_groups = completed
        state.successful_groups = successful
        state.failed_groups = failed
        if not state.stock_name:
            state.stock_name = self._discover_name_from_output(state)

    def _backfill_legacy_jobs(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at_utc").fetchall()
        stock_codes: set[str] = set()
        for row in rows:
            try:
                state = self._state_from_row(row)
            except Exception:
                continue
            stock_codes.add(state.stock_code)
            self._initialize_group_rows(state.job_id)
            if state.status in {"RUNNING", "RETRYING", "DELETING", "PENDING"}:
                state.status = "PARTIAL" if state.completed_groups else "FAILED"
                state.message = "服务重启后原执行进程已结束，可重新执行或重试失败子任务"
            self._sync_group_files(state)
            if state.status == "COMPLETED" and state.failed_groups:
                state.status = "PARTIAL"
            self._save(state)
        for stock_code in stock_codes:
            self._reconcile_current_pointer(stock_code)

    def _progress_handler(self, state: JobState):
        def progress(update: dict[str, Any]) -> None:
            group_id = str(update.get("group_id", ""))
            if update.get("type") == "group_started" and group_id in self.group_definitions:
                self._mark_group_started(state.job_id, group_id)
                state.current_group = str(update.get("family", ""))
                state.message = f"正在处理：{state.current_group}"
            elif update.get("type") == "group_completed" and group_id in self.group_definitions:
                existing = self._get_group_state(state.job_id, group_id)
                if existing:
                    existing.status = "SUCCESS" if update.get("success") else "FAILED"
                    existing.record_count = int(update.get("record_count", 0))
                    existing.used_fallback = bool(update.get("used_fallback"))
                    existing.completed_at_utc = utc_now()
                    existing.duration_seconds = elapsed_seconds(existing.started_at_utc, existing.completed_at_utc)
                    self._save_group_state(existing)
                completed, successful, failed = self._group_counts(state.job_id)
                state.completed_groups = completed
                state.successful_groups = successful
                state.failed_groups = failed
            self._save(state)

        return progress

    def create(self, stock_code: str, resume: bool = True, stock_name: str = "") -> JobState:
        identity = parse_security(stock_code)
        job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        run_dir = self.settings.data_dir / identity.code / job_id
        state = JobState(
            job_id=job_id,
            stock_code=identity.code,
            stock_name=stock_name,
            status="PENDING",
            created_at_utc=utc_now(),
            updated_at_utc=utc_now(),
            total_groups=len(self.group_definitions),
            output_dir=str(run_dir),
            message="等待执行",
        )
        self._save(state)
        self._initialize_group_rows(job_id)
        event = threading.Event()
        self.cancel_events[job_id] = event
        with self._lock:
            self._active_jobs.add(job_id)
        self.pool.submit(self._run, state, resume, event)
        return state

    def _run(self, state: JobState, resume: bool, event: threading.Event) -> None:
        state.status = "RUNNING"
        state.started_at_utc = state.started_at_utc or utc_now()
        state.message = "正在拉取固定接口清单"
        self._save(state)
        try:
            pipeline = FetchPipeline(
                state.stock_code,
                Path(state.output_dir),
                settings=self.settings,
                progress=self._progress_handler(state),
                cancel_event=event,
            )
            combined = pipeline.run(resume=resume)
            self._sync_group_files(state)
            if event.is_set():
                state.status = "CANCELLED"
                state.message = "任务已取消"
            else:
                state.message = "正在生成JSON、Excel、Parquet和DuckDB"
                self._save(state)
                state.artifacts = build_exports(combined, Path(state.output_dir))
                state.completed_at_utc = utc_now()
                state.duration_seconds = elapsed_seconds(state.started_at_utc, state.completed_at_utc)
                if state.failed_groups == 0 and state.completed_groups == state.total_groups:
                    state.status = "COMPLETED"
                    state.message = "任务完成"
                    self._set_current_pointer(state)
                else:
                    state.status = "PARTIAL"
                    state.message = f"任务完成，但有{state.failed_groups}个子任务失败"
        except Exception as exc:  # noqa: BLE001
            state.status = "FAILED"
            state.message = str(exc)
            state.errors.append(str(exc))
            state.completed_at_utc = utc_now()
            state.duration_seconds = elapsed_seconds(state.started_at_utc, state.completed_at_utc)
        finally:
            state.current_group = ""
            self._save(state)
            with self._lock:
                self._active_jobs.discard(state.job_id)
            self.cancel_events.pop(state.job_id, None)

    def _pointer_path(self, stock_code: str) -> Path:
        return self.settings.data_dir / stock_code / "latest.json"

    def _write_pointer_file(self, state: JobState) -> None:
        pointer = self._pointer_path(state.stock_code)
        pointer.parent.mkdir(parents=True, exist_ok=True)
        temporary = pointer.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "job_id": state.job_id,
                    "stock_code": state.stock_code,
                    "stock_name": state.stock_name,
                    "status": state.status,
                    "failed_groups": state.failed_groups,
                    "output_dir": state.output_dir,
                    "artifacts": state.artifacts,
                    "updated_at_utc": utc_now(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(pointer)

    def _set_current_pointer(self, state: JobState, allow_partial: bool = False) -> None:
        if not allow_partial and (state.status != "COMPLETED" or state.failed_groups):
            raise ValueError("只有失败0的完整任务才能设为当前数据版本")
        if state.status not in {"COMPLETED", "PARTIAL"}:
            raise ValueError("只有已完成或部分完成的任务可以设为当前版本")
        self._write_pointer_file(state)
        with self._connect() as connection:
            connection.execute("UPDATE jobs SET is_current=0 WHERE stock_code=?", (state.stock_code,))
            connection.execute("UPDATE jobs SET is_current=1 WHERE job_id=?", (state.job_id,))
        state.is_current = True
        self._save(state)

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
                WHERE stock_code=? AND status='COMPLETED' AND failed_groups=0{exclusion}
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
            except Exception:
                job_id = ""
        if job_id:
            state = self.get(job_id, hydrate=False)
            if state and state.status == "COMPLETED" and not state.failed_groups:
                self._set_current_pointer(state)
                return
        self._select_fallback_current(stock_code)

    def get(self, job_id: str, hydrate: bool = True) -> JobState | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return None
        state = self._state_from_row(row)
        if hydrate and not state.stock_name and state.status not in ACTIVE_STATUSES:
            state.stock_name = self._discover_name_from_output(state)
            self._save(state)
        return state

    def query_jobs(
        self,
        q: str = "",
        status: str | None = None,
        sort_by: str = "created_at_utc",
        sort_direction: str = "desc",
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[JobState], int]:
        sort_columns = {
            "stock_code": "stock_code",
            "stock_name": "stock_name",
            "created_at_utc": "created_at_utc",
            "completed_at_utc": "completed_at_utc",
            "failed_groups": "failed_groups",
            "status": "status",
        }
        order_column = sort_columns.get(sort_by, "created_at_utc")
        direction = "ASC" if sort_direction.lower() == "asc" else "DESC"
        conditions = ["1=1"]
        params: list[Any] = []
        if q.strip():
            like = f"%{q.strip()}%"
            conditions.append("(stock_code LIKE ? OR stock_name LIKE ? OR job_id LIKE ?)")
            params.extend([like, like, like])
        if status:
            conditions.append("status=?")
            params.append(status)
        where = " AND ".join(conditions)
        with self._connect() as connection:
            total = int(connection.execute(f"SELECT count(*) FROM jobs WHERE {where}", params).fetchone()[0])
            rows = connection.execute(
                f"""
                SELECT * FROM jobs WHERE {where}
                ORDER BY {order_column} {direction}, created_at_utc DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [self._state_from_row(row) for row in rows], total

    def list(self, limit: int = 50) -> list[JobState]:
        return self.query_jobs(limit=limit)[0]

    def list_groups(
        self,
        job_id: str,
        status: str | None = None,
        q: str = "",
        theme: str | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[JobGroupState], int]:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        self._initialize_group_rows(job_id)
        if state.status not in ACTIVE_STATUSES:
            self._sync_group_files(state)
            self._save(state)
        conditions = ["job_id=?"]
        params: list[Any] = [job_id]
        if status:
            conditions.append("status=?")
            params.append(status)
        if theme:
            conditions.append("theme=?")
            params.append(theme)
        if q.strip():
            like = f"%{q.strip()}%"
            conditions.append("(family LIKE ? OR theme LIKE ? OR group_id LIKE ? OR errors_json LIKE ?)")
            params.extend([like, like, like, like])
        where = " AND ".join(conditions)
        with self._connect() as connection:
            total = int(connection.execute(f"SELECT count(*) FROM job_groups WHERE {where}", params).fetchone()[0])
            rows = connection.execute(
                f"""
                SELECT * FROM job_groups WHERE {where}
                ORDER BY definition_index ASC LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [self._group_state_from_row(row) for row in rows], total

    def _clear_group_cache(self, state: JobState, group_id: str) -> None:
        raw_dir = Path(state.output_dir) / "raw"
        if raw_dir.exists():
            for path in raw_dir.glob(f"{group_id}_*.json.gz"):
                path.unlink(missing_ok=True)

    def _write_group_result_file(self, state: JobState, result: GroupResult) -> None:
        group_dir = Path(state.output_dir) / "groups"
        group_dir.mkdir(parents=True, exist_ok=True)
        destination = group_dir / f"{result.group_id}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(destination)

    def _retry_one_group(self, state: JobState, group_id: str) -> GroupResult:
        definition = self.group_definitions[group_id]
        self._mark_group_started(state.job_id, group_id, retrying=True)
        self._clear_group_cache(state, group_id)
        pipeline = FetchPipeline(state.stock_code, Path(state.output_dir), settings=self.settings)
        pipeline._load_existing()
        pipeline.results.pop(group_id, None)
        if "dynamic_source" in definition:
            result = pipeline._execute_dynamic_group(definition)
        else:
            result = pipeline._execute_standard_group(definition)
        self._write_group_result_file(state, result)
        self._save_result_group(state.job_id, result)
        return result

    def _assemble_combined(self, state: JobState) -> dict[str, Any]:
        results: list[GroupResult] = []
        group_dir = Path(state.output_dir) / "groups"
        for definition in sorted(self.group_definitions.values(), key=lambda item: item["definition_index"]):
            path = group_dir / f"{definition['group_id']}.json"
            if not path.exists():
                continue
            try:
                results.append(GroupResult.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        failed = [result for result in results if not result.success]
        identity = parse_security(state.stock_code)
        combined = {
            "metadata": {
                "schema_version": "1.0.0",
                "security": identity.model_dump(),
                "security_name": state.stock_name,
                "completed_at_utc": utc_now(),
                "fixed_manifest_version": self.manifest["schema_version"],
                "group_count": len(self.group_definitions),
                "completed_group_count": len(results),
                "failed_group_count": len(failed),
                "source": "Eastmoney live APIs",
            },
            "groups": [result.model_dump() for result in results],
        }
        output = Path(state.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / "combined.json").write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
        return combined

    def _run_retry(self, job_id: str, group_ids: list[str]) -> None:
        state = self.get(job_id)
        if not state:
            return
        try:
            standard = [group_id for group_id in group_ids if "dynamic_source" not in self.group_definitions[group_id]]
            dynamic = [group_id for group_id in group_ids if "dynamic_source" in self.group_definitions[group_id]]
            if standard:
                with ThreadPoolExecutor(max_workers=min(self.settings.max_workers, len(standard))) as executor:
                    futures = {executor.submit(self._retry_one_group, state, group_id): group_id for group_id in standard}
                    for future in as_completed(futures):
                        group_id = futures[future]
                        try:
                            future.result()
                        except Exception as exc:  # noqa: BLE001
                            definition = self.group_definitions[group_id]
                            existing = self._get_group_state(job_id, group_id)
                            failed = existing or JobGroupState(
                                job_id=job_id,
                                group_id=group_id,
                                definition_index=definition["definition_index"],
                                theme=definition.get("theme", ""),
                                family=definition.get("family", ""),
                                strategy=definition.get("strategy", ""),
                                updated_at_utc=utc_now(),
                            )
                            failed.status = "FAILED"
                            failed.errors = [str(exc)]
                            failed.completed_at_utc = utc_now()
                            failed.duration_seconds = elapsed_seconds(failed.started_at_utc, failed.completed_at_utc)
                            self._save_group_state(failed)
            for group_id in dynamic:
                try:
                    self._retry_one_group(state, group_id)
                except Exception as exc:  # noqa: BLE001
                    definition = self.group_definitions[group_id]
                    existing = self._get_group_state(job_id, group_id)
                    failed = existing or JobGroupState(
                        job_id=job_id,
                        group_id=group_id,
                        definition_index=definition["definition_index"],
                        theme=definition.get("theme", ""),
                        family=definition.get("family", ""),
                        strategy=definition.get("strategy", ""),
                        updated_at_utc=utc_now(),
                    )
                    failed.status = "FAILED"
                    failed.errors = [str(exc)]
                    failed.completed_at_utc = utc_now()
                    self._save_group_state(failed)

            state = self.get(job_id) or state
            self._sync_group_files(state)
            combined = self._assemble_combined(state)
            state.message = "正在重新生成JSON、Excel、Parquet和DuckDB"
            self._save(state)
            state.artifacts = build_exports(combined, Path(state.output_dir))
            state.completed_at_utc = utc_now()
            state.duration_seconds = elapsed_seconds(state.started_at_utc or state.created_at_utc, state.completed_at_utc)
            if state.failed_groups == 0 and state.completed_groups == state.total_groups:
                state.status = "COMPLETED"
                state.message = "失败子任务已全部恢复，任务完整"
                self._set_current_pointer(state)
            else:
                was_current = state.is_current
                state.status = "PARTIAL"
                state.message = f"重试完成，仍有{state.failed_groups}个子任务失败"
                if was_current:
                    self._select_fallback_current(state.stock_code, exclude_job_id=state.job_id)
                    state.is_current = False
        except Exception as exc:  # noqa: BLE001
            state = self.get(job_id) or state
            state.status = "PARTIAL" if state.completed_groups else "FAILED"
            state.message = f"重试过程异常：{exc}"
            state.errors.append(str(exc))
        finally:
            state.current_group = ""
            self._save(state)
            with self._lock:
                self._active_jobs.discard(job_id)

    def _schedule_retry(self, state: JobState, group_ids: list[str]) -> JobState:
        if not group_ids:
            raise ValueError("没有可重试的子任务")
        unknown = [group_id for group_id in group_ids if group_id not in self.group_definitions]
        if unknown:
            raise ValueError(f"未知子任务：{', '.join(unknown)}")
        with self._lock:
            if state.job_id in self._active_jobs or state.status in ACTIVE_STATUSES:
                raise RuntimeError("该任务正在运行或处理中")
            self._active_jobs.add(state.job_id)
        state.status = "RETRYING"
        state.retry_count += 1
        state.last_retry_at_utc = utc_now()
        state.current_group = ", ".join(self.group_definitions[group_id]["family"] for group_id in group_ids[:3])
        state.message = f"正在重试{len(group_ids)}个子任务"
        self._save(state)
        self.pool.submit(self._run_retry, state.job_id, group_ids)
        return state

    def retry_group(self, job_id: str, group_id: str) -> JobState:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        self._initialize_group_rows(job_id)
        if not self._get_group_state(job_id, group_id):
            raise LookupError("子任务不存在")
        return self._schedule_retry(state, [group_id])

    def retry_failed(self, job_id: str) -> JobState:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        self._sync_group_files(state)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT group_id FROM job_groups WHERE job_id=? AND status='FAILED' ORDER BY definition_index",
                (job_id,),
            ).fetchall()
        return self._schedule_retry(state, [str(row["group_id"]) for row in rows])

    def rerun(self, job_id: str) -> JobState:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        return self.create(state.stock_code, resume=False, stock_name=state.stock_name)

    def set_current(self, job_id: str, allow_partial: bool = False) -> JobState:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        self._set_current_pointer(state, allow_partial=allow_partial)
        return state

    def cancel(self, job_id: str) -> bool:
        event = self.cancel_events.get(job_id)
        if event:
            event.set()
            return True
        return False

    def _safe_run_dir(self, state: JobState) -> Path:
        data_root = self.settings.data_dir.resolve()
        expected_parent = (data_root / state.stock_code).resolve()
        run_dir = Path(state.output_dir).resolve()
        if run_dir.parent != expected_parent or run_dir.name != state.job_id:
            raise ValueError("任务输出目录不在允许删除的路径范围内")
        return run_dir

    def delete(self, job_id: str, confirm: str) -> dict[str, Any]:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        if confirm not in {"DELETE", job_id[-8:]}:
            raise ValueError("删除确认内容不正确")
        with self._lock:
            if job_id in self._active_jobs or state.status in ACTIVE_STATUSES:
                raise RuntimeError("运行中、重试中或删除中的任务不能删除")
            self._active_jobs.add(job_id)
        was_current = state.is_current
        state.status = "DELETING"
        state.message = "正在删除任务及文件"
        self._save(state)
        try:
            run_dir = self._safe_run_dir(state)
            if run_dir.exists():
                shutil.rmtree(run_dir)
            with self._connect() as connection:
                connection.execute("DELETE FROM job_groups WHERE job_id=?", (job_id,))
                connection.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
            self.cancel_events.pop(job_id, None)
            if was_current:
                self._select_fallback_current(state.stock_code, exclude_job_id=job_id)
            return {"job_id": job_id, "deleted": True, "files_deleted": True}
        except Exception as exc:
            state.status = "DELETE_FAILED"
            state.message = f"删除失败：{exc}"
            state.errors.append(str(exc))
            self._save(state)
            raise
        finally:
            with self._lock:
                self._active_jobs.discard(job_id)

    def latest(self, stock_code: str) -> dict[str, Any] | None:
        identity = parse_security(stock_code)
        pointer = self._pointer_path(identity.code)
        if not pointer.exists():
            fallback = self._select_fallback_current(identity.code)
            if not fallback:
                return None
        try:
            payload = json.loads(pointer.read_text(encoding="utf-8"))
        except Exception:
            fallback = self._select_fallback_current(identity.code)
            if not fallback:
                return None
            payload = json.loads(pointer.read_text(encoding="utf-8"))
        return payload

    def artifact_path(self, job_id: str, kind: str) -> Path:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        aliases = {"xlsx": "excel", "db": "duckdb"}
        key = aliases.get(kind, kind)
        value = state.artifacts.get(key)
        if not value:
            raise LookupError(f"该任务没有{kind}文件")
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError("任务文件不存在")
        return path
