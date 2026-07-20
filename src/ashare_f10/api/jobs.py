from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ashare_f10.config import Settings
from ashare_f10.config import settings as default_settings
from ashare_f10.export.bundle import build_exports
from ashare_f10.fetch.pipeline import FetchPipeline
from ashare_f10.models import JobState


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JobManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or default_settings
        self.settings.ensure_dirs()
        self.db_path = self.settings.data_dir / "jobs.sqlite3"
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="f10-job")
        self.cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
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

    def _save(self, state: JobState) -> None:
        state.updated_at_utc = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs(job_id, stock_code, status, state_json, created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                  status=excluded.status,
                  state_json=excluded.state_json,
                  updated_at_utc=excluded.updated_at_utc
                """,
                (
                    state.job_id,
                    state.stock_code,
                    state.status,
                    state.model_dump_json(),
                    state.created_at_utc,
                    state.updated_at_utc,
                ),
            )

    def create(self, stock_code: str, resume: bool = True) -> JobState:
        job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        run_dir = self.settings.data_dir / stock_code / job_id
        state = JobState(
            job_id=job_id,
            stock_code=stock_code,
            status="PENDING",
            created_at_utc=utc_now(),
            updated_at_utc=utc_now(),
            total_groups=113,
            output_dir=str(run_dir),
        )
        self._save(state)
        event = threading.Event()
        self.cancel_events[job_id] = event
        self.pool.submit(self._run, state, resume, event)
        return state

    def _run(self, state: JobState, resume: bool, event: threading.Event) -> None:
        state.status = "RUNNING"
        state.message = "正在拉取固定接口清单"
        self._save(state)

        def progress(update: dict[str, Any]) -> None:
            if update.get("type") == "group_started":
                state.current_group = str(update.get("family", ""))
                state.message = f"正在处理：{state.current_group}"
            elif update.get("type") == "group_completed":
                state.completed_groups += 1
                if not update.get("success"):
                    state.failed_groups += 1
            self._save(state)

        try:
            pipeline = FetchPipeline(
                state.stock_code,
                Path(state.output_dir),
                settings=self.settings,
                progress=progress,
                cancel_event=event,
            )
            combined = pipeline.run(resume=resume)
            if event.is_set():
                state.status = "CANCELLED"
                state.message = "任务已取消"
            else:
                state.message = "正在生成JSON、Excel、Parquet和DuckDB"
                self._save(state)
                artifacts = build_exports(combined, Path(state.output_dir))
                state.artifacts = artifacts
                state.status = "COMPLETED"
                state.message = "任务完成"
                self._update_latest_pointer(state)
        except Exception as exc:  # noqa: BLE001
            state.status = "FAILED"
            state.message = str(exc)
            state.errors.append(str(exc))
        finally:
            state.current_group = ""
            self._save(state)

    def _update_latest_pointer(self, state: JobState) -> None:
        stock_dir = self.settings.data_dir / state.stock_code
        pointer = stock_dir / "latest.json"
        pointer.write_text(
            json.dumps(
                {
                    "job_id": state.job_id,
                    "output_dir": state.output_dir,
                    "artifacts": state.artifacts,
                    "updated_at_utc": utc_now(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def get(self, job_id: str) -> JobState | None:
        with self._connect() as connection:
            row = connection.execute("SELECT state_json FROM jobs WHERE job_id = ?", [job_id]).fetchone()
        return JobState.model_validate_json(row[0]) if row else None

    def list(self, limit: int = 50) -> list[JobState]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state_json FROM jobs ORDER BY created_at_utc DESC LIMIT ?", [limit]
            ).fetchall()
        return [JobState.model_validate_json(row[0]) for row in rows]

    def cancel(self, job_id: str) -> bool:
        event = self.cancel_events.get(job_id)
        if event:
            event.set()
            return True
        return False

    def latest(self, stock_code: str) -> dict[str, Any] | None:
        pointer = self.settings.data_dir / stock_code / "latest.json"
        if not pointer.exists():
            return None
        return json.loads(pointer.read_text(encoding="utf-8"))
