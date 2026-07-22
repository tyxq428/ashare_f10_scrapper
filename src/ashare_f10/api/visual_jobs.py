from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ashare_f10.api.jobs import elapsed_seconds, utc_now
from ashare_f10.api.jobs_v2 import JobManager as BaseJobManager
from ashare_f10.config import Settings
from ashare_f10.export.bundle import build_exports
from ashare_f10.fetch.pipeline import FetchPipeline
from ashare_f10.fetch.security import parse_security
from ashare_f10.models import GroupResult, JobGroupState, JobState

DEFAULT_VISUAL_OPTIONS: dict[str, Any] = {
    "workers": 8,
    "auto_retry_failed": True,
    "max_auto_retries": 2,
    "retry_backoff_seconds": 5,
    "include_raw_pack": False,
    "raw_pack_packs": "default",
    "raw_pack_max_docs": 200,
    "run_official_validation": False,
    "official_annual_year": 2025,
    "official_quarter_year": 2026,
}


def normalize_visual_options(value: dict[str, Any] | None) -> dict[str, Any]:
    options = {**DEFAULT_VISUAL_OPTIONS, **(value or {})}
    options["workers"] = max(1, min(32, int(options["workers"])))
    options["auto_retry_failed"] = bool(options["auto_retry_failed"])
    options["max_auto_retries"] = max(0, min(5, int(options["max_auto_retries"])))
    options["retry_backoff_seconds"] = max(0, min(120, int(options["retry_backoff_seconds"])))
    options["include_raw_pack"] = bool(options["include_raw_pack"])
    options["raw_pack_packs"] = str(options["raw_pack_packs"] or "default").strip() or "default"
    options["raw_pack_max_docs"] = max(1, min(5000, int(options["raw_pack_max_docs"])))
    options["run_official_validation"] = bool(options["run_official_validation"])
    options["official_annual_year"] = max(2000, min(2100, int(options["official_annual_year"])))
    options["official_quarter_year"] = max(2000, min(2100, int(options["official_quarter_year"])))
    return options


class VisualJobManager(BaseJobManager):
    """Visual-first orchestration on top of the stable F10 job manager.

    Execution options and optional-stage state are kept in a sidecar file. This
    preserves the existing SQLite/JobState contract and lets legacy jobs remain
    readable without a database migration.
    """

    def __init__(self, settings: Settings | None = None):
        super().__init__(settings)
        self._visual_lock = threading.RLock()

    @staticmethod
    def _sidecar_path(state: JobState) -> Path:
        return Path(state.output_dir) / "visual-execution.json"

    def _read_sidecar(self, state: JobState) -> dict[str, Any]:
        path = self._sidecar_path(state)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except Exception:  # noqa: BLE001
                pass
        return {
            "schema_version": "1.0.0",
            "job_id": state.job_id,
            "stock_code": state.stock_code,
            "options": normalize_visual_options(None),
            "stage_status": {
                "f10": "UNKNOWN",
                "raw_pack": "NOT_REQUESTED",
                "official_validation": "NOT_REQUESTED",
            },
            "stage_messages": {},
            "stage_results": {},
            "heartbeat_at_utc": state.updated_at_utc,
            "warning_count": 0,
        }

    def _write_sidecar(self, state: JobState, payload: dict[str, Any]) -> None:
        path = self._sidecar_path(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = "1.0.0"
        payload["job_id"] = state.job_id
        payload["stock_code"] = state.stock_code
        payload["heartbeat_at_utc"] = utc_now()
        temporary = path.with_suffix(".json.tmp")
        with self._visual_lock:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)

    def _update_sidecar(
        self,
        state: JobState,
        *,
        stage: str | None = None,
        status: str | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        warning_delta: int = 0,
    ) -> dict[str, Any]:
        payload = self._read_sidecar(state)
        if stage:
            payload.setdefault("stage_status", {})[stage] = status or payload.get("stage_status", {}).get(
                stage, "UNKNOWN"
            )
            if message is not None:
                payload.setdefault("stage_messages", {})[stage] = message
            if result is not None:
                payload.setdefault("stage_results", {})[stage] = result
        payload["warning_count"] = max(0, int(payload.get("warning_count", 0)) + warning_delta)
        self._write_sidecar(state, payload)
        return payload

    def visual_payload(self, state: JobState) -> dict[str, Any]:
        return {**state.model_dump(mode="json"), "visual": self._read_sidecar(state)}

    def create_visual(
        self,
        stock_code: str,
        *,
        resume: bool = True,
        stock_name: str = "",
        options: dict[str, Any] | None = None,
    ) -> JobState:
        identity = parse_security(stock_code)
        normalized = normalize_visual_options(options)
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
            message="等待可视化任务执行",
        )
        sidecar = {
            "options": normalized,
            "stage_status": {
                "f10": "PENDING",
                "raw_pack": "PENDING" if normalized["include_raw_pack"] else "NOT_REQUESTED",
                "official_validation": (
                    "PENDING" if normalized["run_official_validation"] else "NOT_REQUESTED"
                ),
            },
            "stage_messages": {},
            "stage_results": {},
            "warning_count": 0,
        }
        self._write_sidecar(state, sidecar)
        self._save(state)
        self._initialize_group_rows(job_id)
        event = threading.Event()
        self.cancel_events[job_id] = event
        with self._lock:
            self._active_jobs.add(job_id)
        self.pool.submit(self._run_visual, state, resume, event)
        return state

    def rerun_visual(self, job_id: str) -> JobState:
        state = self.get(job_id)
        if not state:
            raise LookupError("任务不存在")
        options = self._read_sidecar(state).get("options")
        return self.create_visual(
            state.stock_code,
            resume=False,
            stock_name=state.stock_name,
            options=options if isinstance(options, dict) else None,
        )

    def _settings_for_state(self, state: JobState) -> Settings:
        options = normalize_visual_options(self._read_sidecar(state).get("options"))
        workers = int(options["workers"])
        return self.settings.model_copy(
            deep=True,
            update={"max_workers": workers, "page_workers": min(workers, self.settings.page_workers)},
        )

    def _progress_handler_visual(self, state: JobState):
        base_handler = self._progress_handler(state)

        def progress(update: dict[str, Any]) -> None:
            base_handler(update)
            event_type = str(update.get("type", ""))
            family = str(update.get("family", ""))
            if event_type == "group_started":
                self._update_sidecar(
                    state,
                    stage="f10",
                    status="RUNNING",
                    message=f"正在处理：{family}",
                )
            elif event_type == "group_completed":
                completed, successful, failed = self._group_counts(state.job_id)
                self._update_sidecar(
                    state,
                    stage="f10",
                    status="RUNNING",
                    message=f"已完成{completed}/{state.total_groups}；成功{successful}；失败{failed}",
                )

        return progress

    def _failed_group_ids(self, job_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT group_id FROM job_groups WHERE job_id=? AND status='FAILED' ORDER BY definition_index",
                (job_id,),
            ).fetchall()
        return [str(row["group_id"]) for row in rows]

    def _retry_one_group_with_settings(
        self,
        state: JobState,
        group_id: str,
        job_settings: Settings,
    ) -> GroupResult:
        definition = self.group_definitions[group_id]
        self._mark_group_started(state.job_id, group_id, retrying=True)
        self._clear_group_cache(state, group_id)
        pipeline = FetchPipeline(state.stock_code, Path(state.output_dir), settings=job_settings)
        pipeline._load_existing()
        pipeline.results.pop(group_id, None)
        if "dynamic_source" in definition:
            result = pipeline._execute_dynamic_group(definition)
        else:
            result = pipeline._execute_standard_group(definition)
        self._write_group_result_file(state, result)
        self._save_result_group(state.job_id, result)
        return result

    def _mark_retry_exception(self, state: JobState, group_id: str, exc: Exception) -> None:
        definition = self.group_definitions[group_id]
        existing = self._get_group_state(state.job_id, group_id)
        failed = existing or JobGroupState(
            job_id=state.job_id,
            group_id=group_id,
            definition_index=definition["definition_index"],
            theme=str(definition.get("theme", "")),
            family=str(definition.get("family", "")),
            strategy=str(definition.get("strategy", "")),
            updated_at_utc=utc_now(),
        )
        failed.status = "FAILED"
        failed.errors = [f"{type(exc).__name__}: {exc}"]
        failed.completed_at_utc = utc_now()
        failed.duration_seconds = elapsed_seconds(failed.started_at_utc, failed.completed_at_utc)
        self._save_group_state(failed)

    def _auto_retry_failed(self, state: JobState, event: threading.Event) -> None:
        options = normalize_visual_options(self._read_sidecar(state).get("options"))
        if not options["auto_retry_failed"] or int(options["max_auto_retries"]) <= 0:
            return
        job_settings = self._settings_for_state(state)
        for attempt in range(1, int(options["max_auto_retries"]) + 1):
            self._sync_group_files(state)
            group_ids = self._failed_group_ids(state.job_id)
            if not group_ids or event.is_set():
                break
            state.status = "RETRYING"
            state.retry_count += 1
            state.last_retry_at_utc = utc_now()
            state.message = f"自动恢复第{attempt}轮：重试{len(group_ids)}个失败子任务"
            self._save(state)
            self._update_sidecar(
                state,
                stage="f10",
                status="RETRYING",
                message=state.message,
            )
            backoff = int(options["retry_backoff_seconds"]) * (2 ** (attempt - 1))
            if backoff and event.wait(backoff):
                break

            standard = [
                group_id
                for group_id in group_ids
                if "dynamic_source" not in self.group_definitions[group_id]
            ]
            dynamic = [
                group_id
                for group_id in group_ids
                if "dynamic_source" in self.group_definitions[group_id]
            ]
            if standard:
                with ThreadPoolExecutor(
                    max_workers=min(job_settings.max_workers, len(standard)),
                    thread_name_prefix="visual-retry",
                ) as executor:
                    futures = {
                        executor.submit(
                            self._retry_one_group_with_settings,
                            state,
                            group_id,
                            job_settings,
                        ): group_id
                        for group_id in standard
                    }
                    for future in as_completed(futures):
                        group_id = futures[future]
                        try:
                            future.result()
                        except Exception as exc:  # noqa: BLE001
                            self._mark_retry_exception(state, group_id, exc)
            for group_id in dynamic:
                if event.is_set():
                    break
                try:
                    self._retry_one_group_with_settings(state, group_id, job_settings)
                except Exception as exc:  # noqa: BLE001
                    self._mark_retry_exception(state, group_id, exc)
            self._sync_group_files(state)

        if not event.is_set():
            state.status = "RUNNING"
            self._save(state)

    @staticmethod
    def _compact_raw_pack_result(result: dict[str, Any]) -> dict[str, Any]:
        return {
            key: result.get(key)
            for key in (
                "run_id",
                "output_dir",
                "selected_source_count",
                "document_count",
                "status_counts",
                "errors",
            )
        }

    @staticmethod
    def _compact_official_result(result: dict[str, Any]) -> dict[str, Any]:
        return {
            key: result.get(key)
            for key in (
                "acceptance_status",
                "document_count",
                "official_fact_count",
                "reconciliation_count",
                "status_counts",
                "high_severity_mismatch_count",
                "manual_review_required",
                "artifacts",
            )
        }

    def _run_optional_stages(self, state: JobState, job_settings: Settings) -> int:
        options = normalize_visual_options(self._read_sidecar(state).get("options"))
        tasks: dict[Any, str] = {}
        warnings = 0
        run_dir = Path(state.output_dir)
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="visual-optional") as executor:
            if options["include_raw_pack"]:
                self._update_sidecar(
                    state,
                    stage="raw_pack",
                    status="RUNNING",
                    message="正在获取官方Raw Pack原始资料",
                )
                from ashare_f10.raw_sources.runner import run_raw_pack

                future = executor.submit(
                    run_raw_pack,
                    state.stock_code,
                    run_dir,
                    f10_run_dir=run_dir,
                    packs=options["raw_pack_packs"],
                    max_docs=options["raw_pack_max_docs"],
                    config=job_settings,
                )
                tasks[future] = "raw_pack"
            if options["run_official_validation"]:
                self._update_sidecar(
                    state,
                    stage="official_validation",
                    status="RUNNING",
                    message="正在执行免费官方披露交叉验证",
                )
                from ashare_f10.validation.runner import run_official_validation

                future = executor.submit(
                    run_official_validation,
                    state.stock_code,
                    run_dir,
                    run_dir / "validation",
                    options["official_annual_year"],
                    options["official_quarter_year"],
                )
                tasks[future] = "official_validation"

            for future in as_completed(tasks):
                stage = tasks[future]
                try:
                    result = future.result()
                    if stage == "raw_pack":
                        compact = self._compact_raw_pack_result(result)
                        raw_artifacts = result.get("artifacts") or {}
                        state.artifacts.update(
                            {
                                "raw_pack_manifest": str(raw_artifacts.get("run_manifest", "")),
                                "raw_pack_excel": str(raw_artifacts.get("excel_index", "")),
                                "raw_pack_parquet": str(raw_artifacts.get("parquet_index", "")),
                                "raw_pack_duckdb": str(raw_artifacts.get("duckdb_index", "")),
                                "raw_pack_quality": str(raw_artifacts.get("quality_report_json", "")),
                            }
                        )
                    else:
                        compact = self._compact_official_result(result)
                        for key, value in (result.get("artifacts") or {}).items():
                            if value:
                                state.artifacts[f"official_{key}"] = str(value)
                    state.artifacts = {key: value for key, value in state.artifacts.items() if value}
                    self._save(state)
                    self._update_sidecar(
                        state,
                        stage=stage,
                        status="COMPLETED",
                        message="执行完成",
                        result=compact,
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings += 1
                    state.errors.append(f"{stage}: {type(exc).__name__}: {exc}")
                    self._save(state)
                    self._update_sidecar(
                        state,
                        stage=stage,
                        status="FAILED",
                        message=str(exc),
                        warning_delta=1,
                    )
        return warnings

    def _run_visual(self, state: JobState, resume: bool, event: threading.Event) -> None:
        state.status = "RUNNING"
        state.started_at_utc = state.started_at_utc or utc_now()
        state.message = "正在拉取F10固定接口清单"
        self._save(state)
        self._update_sidecar(state, stage="f10", status="RUNNING", message=state.message)
        try:
            job_settings = self._settings_for_state(state)
            pipeline = FetchPipeline(
                state.stock_code,
                Path(state.output_dir),
                settings=job_settings,
                progress=self._progress_handler_visual(state),
                cancel_event=event,
            )
            combined = pipeline.run(resume=resume)
            self._sync_group_files(state)
            self._auto_retry_failed(state, event)
            self._sync_group_files(state)
            combined = self._assemble_combined(state)

            if event.is_set():
                state.status = "CANCELLED"
                state.message = "任务已取消"
                self._update_sidecar(state, stage="f10", status="CANCELLED", message=state.message)
            else:
                state.message = "正在生成JSON、Excel、Parquet和DuckDB"
                self._save(state)
                state.artifacts = build_exports(combined, Path(state.output_dir))
                core_complete = state.failed_groups == 0 and state.completed_groups == state.total_groups
                if not core_complete:
                    state.status = "PARTIAL"
                    state.message = f"F10完成，但仍有{state.failed_groups}个子任务失败"
                    self._update_sidecar(
                        state,
                        stage="f10",
                        status="PARTIAL",
                        message=state.message,
                    )
                    visual = self._read_sidecar(state)
                    for optional_stage in ("raw_pack", "official_validation"):
                        if visual.get("stage_status", {}).get(optional_stage) == "PENDING":
                            self._update_sidecar(
                                state,
                                stage=optional_stage,
                                status="SKIPPED_INCOMPLETE_F10",
                                message="F10核心任务未完整，已跳过可选阶段",
                            )
                else:
                    self._update_sidecar(
                        state,
                        stage="f10",
                        status="COMPLETED",
                        message="113个F10子任务全部完成",
                    )
                    warning_count = self._run_optional_stages(state, job_settings)
                    state.status = "COMPLETED"
                    state.message = (
                        f"完整研究包完成，{warning_count}个可选阶段存在警告"
                        if warning_count
                        else "完整研究包完成"
                    )
                state.completed_at_utc = utc_now()
                state.duration_seconds = elapsed_seconds(state.started_at_utc, state.completed_at_utc)
                if state.status == "COMPLETED":
                    self._set_current_pointer(state)
        except Exception as exc:  # noqa: BLE001
            state.status = "FAILED"
            state.message = str(exc)
            state.errors.append(f"{type(exc).__name__}: {exc}")
            state.completed_at_utc = utc_now()
            state.duration_seconds = elapsed_seconds(state.started_at_utc, state.completed_at_utc)
            self._update_sidecar(state, stage="f10", status="FAILED", message=str(exc))
        finally:
            state.current_group = ""
            self._save(state)
            with self._lock:
                self._active_jobs.discard(state.job_id)
            self.cancel_events.pop(state.job_id, None)

    def _run_retry(self, job_id: str, group_ids: list[str]) -> None:
        super()._run_retry(job_id, group_ids)
        state = self.get(job_id)
        if not state or state.status != "COMPLETED":
            return
        visual = self._read_sidecar(state)
        options = normalize_visual_options(visual.get("options"))
        requested = options["include_raw_pack"] or options["run_official_validation"]
        incomplete_optional = any(
            visual.get("stage_status", {}).get(stage) not in {"COMPLETED", "NOT_REQUESTED"}
            for stage in ("raw_pack", "official_validation")
        )
        if requested and incomplete_optional:
            with self._lock:
                if state.job_id in self._active_jobs:
                    return
                self._active_jobs.add(state.job_id)
            try:
                state.status = "RUNNING"
                state.message = "F10已恢复，正在执行可选投研阶段"
                self._save(state)
                self._run_optional_stages(state, self._settings_for_state(state))
                state.status = "COMPLETED"
                state.completed_at_utc = utc_now()
                state.duration_seconds = elapsed_seconds(
                    state.started_at_utc or state.created_at_utc, state.completed_at_utc
                )
                state.message = "失败子任务和可选投研阶段均已完成"
                self._set_current_pointer(state)
                self._save(state)
            finally:
                with self._lock:
                    self._active_jobs.discard(state.job_id)


__all__ = ["DEFAULT_VISUAL_OPTIONS", "VisualJobManager", "normalize_visual_options"]
