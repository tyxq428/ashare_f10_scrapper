from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ashare_f10.api.visual_jobs import (
    DEFAULT_VISUAL_OPTIONS as LEGACY_DEFAULT_VISUAL_OPTIONS,
    VisualJobManager as LegacyVisualJobManager,
    normalize_visual_options as normalize_legacy_options,
)
from ashare_f10.config import Settings
from ashare_f10.models import JobState

OFFICIAL_VALIDATION_SCOPES: dict[str, dict[str, Any]] = {
    "latest": {
        "label": "最近2个报告期（快速）",
        "description": "只验证F10中最近两个财务报告期，适合快速检查。",
        "max_periods": 2,
    },
    "recent_3y": {
        "label": "最近3年",
        "description": "验证最近约12个季度/年度报告期。",
        "max_periods": 12,
    },
    "recent_5y": {
        "label": "最近5年",
        "description": "验证最近约20个季度/年度报告期。",
        "max_periods": 20,
    },
    "full_history": {
        "label": "上市以来全部报告（推荐）",
        "description": "自动识别上市日期并验证全部可用官方定期报告；无需手工查询年份。",
        "max_periods": None,
    },
}

DEFAULT_VISUAL_OPTIONS: dict[str, Any] = {
    **LEGACY_DEFAULT_VISUAL_OPTIONS,
    "official_validation_scope": "full_history",
    "official_max_periods": None,
}


def official_max_periods(scope: str) -> int | None:
    selected = OFFICIAL_VALIDATION_SCOPES.get(scope) or OFFICIAL_VALIDATION_SCOPES["full_history"]
    value = selected["max_periods"]
    return int(value) if value is not None else None


def normalize_visual_options(value: dict[str, Any] | None) -> dict[str, Any]:
    options = normalize_legacy_options(value)
    scope = str(options.get("official_validation_scope") or "full_history").strip()
    if scope not in OFFICIAL_VALIDATION_SCOPES:
        scope = "full_history"
    options["official_validation_scope"] = scope
    options["official_max_periods"] = official_max_periods(scope)
    return options


def official_stage_outcome(result: dict[str, Any], scope: str) -> dict[str, Any]:
    source_status = result.get("official_source_status") or {}
    document_count = int(source_status.get("document_count") or result.get("document_count") or 0)
    fact_count = int(result.get("official_fact_count") or 0)
    comparison_count = int(result.get("comparison_count") or result.get("reconciliation_count") or 0)
    conflict_count = int(result.get("true_conflict_count") or 0)
    acceptance = str(result.get("acceptance_status") or "UNKNOWN")
    needs_review = bool(result.get("manual_review_required")) or acceptance.startswith("FAIL")
    scope_label = str(OFFICIAL_VALIDATION_SCOPES[scope]["label"])
    if needs_review:
        message = (
            f"{scope_label}验证完成：{document_count}份官方报告、{fact_count}条官方事实；"
            f"发现{conflict_count}项来源差异，需要复核"
        )
    else:
        message = (
            f"{scope_label}验证完成：{document_count}份官方报告、{fact_count}条官方事实、"
            f"{comparison_count}条对账记录"
        )
    return {
        "stored_status": "COMPLETED",
        "display_status": "COMPLETED_WITH_REVIEW" if needs_review else "COMPLETED",
        "message": message,
        "warning_delta": int(needs_review),
        "needs_review": needs_review,
        "scope": scope,
        "scope_label": scope_label,
    }


class VisualJobManager(LegacyVisualJobManager):
    """Product-oriented visual orchestration using full-history validation."""

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
        # Raw Pack and full-history validation can run concurrently. Lock the whole
        # read-modify-write cycle so their progress messages never overwrite each other.
        with self._visual_lock:
            return super()._update_sidecar(
                state,
                stage=stage,
                status=status,
                message=message,
                result=result,
                warning_delta=warning_delta,
            )

    @staticmethod
    def _infer_f10_status(state: JobState) -> str:
        if state.status in {"PENDING", "RUNNING", "RETRYING", "PARTIAL", "FAILED", "CANCELLED"}:
            return state.status
        if state.total_groups and state.completed_groups >= state.total_groups and state.failed_groups == 0:
            return "COMPLETED"
        if state.failed_groups:
            return "PARTIAL"
        return "UNKNOWN"

    def _read_sidecar(self, state: JobState) -> dict[str, Any]:
        payload = super()._read_sidecar(state)
        payload["options"] = normalize_visual_options(payload.get("options"))
        stage_status = payload.setdefault("stage_status", {})
        stage_messages = payload.setdefault("stage_messages", {})
        payload.setdefault("stage_results", {})
        payload.setdefault("warning_count", 0)

        if stage_status.get("f10") in {None, "", "UNKNOWN"}:
            stage_status["f10"] = self._infer_f10_status(state)
            if stage_status["f10"] == "COMPLETED":
                stage_messages.setdefault("f10", "历史任务：F10结构化数据已完成")

        artifact_keys = set((state.artifacts or {}).keys())
        if stage_status.get("raw_pack") in {None, "", "UNKNOWN", "NOT_REQUESTED"} and any(
            key.startswith("raw_pack") for key in artifact_keys
        ):
            stage_status["raw_pack"] = "COMPLETED"
            stage_messages.setdefault("raw_pack", "历史任务：Raw Pack资料已生成")
        if stage_status.get("official_validation") in {None, "", "UNKNOWN", "NOT_REQUESTED"} and any(
            key.startswith("official_") for key in artifact_keys
        ):
            stage_status["official_validation"] = "COMPLETED"
            stage_messages.setdefault("official_validation", "历史任务：官方验证结果已生成")
        return payload

    @staticmethod
    def _compact_official_result(result: dict[str, Any], scope: str) -> dict[str, Any]:
        source_status = result.get("official_source_status") or {}
        outcome = official_stage_outcome(result, scope)
        return {
            "scope": scope,
            "scope_label": outcome["scope_label"],
            "acceptance_status": result.get("acceptance_status"),
            "document_count": source_status.get("document_count", result.get("document_count")),
            "official_fact_count": result.get("official_fact_count"),
            "comparison_count": result.get("comparison_count", result.get("reconciliation_count")),
            "status_counts": result.get("status_counts"),
            "true_conflict_count": result.get("true_conflict_count", 0),
            "comparable_match_rate": result.get("comparable_match_rate"),
            "classification_coverage": result.get("classification_coverage"),
            "manual_review_required": result.get("manual_review_required"),
            "display_status": outcome["display_status"],
            "official_source_status": source_status,
            "artifacts": result.get("artifacts"),
        }

    def _official_progress_handler(self, state: JobState, scope_label: str):
        def progress(event: dict[str, Any]) -> None:
            stage = str(event.get("stage") or "")
            if stage == "PROCESS_POLICY_CHECK":
                message = f"{scope_label}：检查验证规则"
            elif stage == "EASTMONEY_NORMALIZE":
                message = f"{scope_label}：整理F10全历史事实"
            elif stage == "OFFICIAL_DISCOVERY":
                requested = len(event.get("requested_report_dates") or [])
                expected = len(event.get("periodic_expected_report_dates") or [])
                pre_listing = len(event.get("pre_listing_report_dates") or [])
                message = (
                    f"{scope_label}：已识别{requested}个F10报告期，"
                    f"上市后预计{expected}份，上市前{pre_listing}期"
                )
            elif stage == "OFFICIAL_DOWNLOAD":
                message = f"{scope_label}：下载官方报告 {event.get('completed', 0)}/{event.get('total', 0)}"
            elif stage == "OFFICIAL_PARSE":
                message = (
                    f"{scope_label}：解析官方报告 {event.get('completed', 0)}/{event.get('total', 0)}；"
                    f"缓存命中{event.get('cache_hits', 0)}"
                )
            elif stage == "RECONCILIATION":
                message = (
                    f"{scope_label}：正在对账，F10事实{event.get('eastmoney_fact_count', 0)}条，"
                    f"官方事实{event.get('official_fact_count', 0)}条"
                )
            elif stage == "EXPORT":
                message = f"{scope_label}：正在导出{event.get('comparison_count', 0)}条对账结果"
            elif stage == "COMPLETED":
                message = f"{scope_label}：验证计算完成"
            else:
                message = f"{scope_label}：{stage or '运行中'}"
            self._update_sidecar(
                state,
                stage="official_validation",
                status="RUNNING",
                message=message,
            )

        return progress

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
                scope = str(options["official_validation_scope"])
                scope_label = str(OFFICIAL_VALIDATION_SCOPES[scope]["label"])
                self._update_sidecar(
                    state,
                    stage="official_validation",
                    status="RUNNING",
                    message=f"正在执行{scope_label}官方交叉验证",
                )
                from ashare_f10.cross_validation.runner import run_full_cross_validation

                future = executor.submit(
                    run_full_cross_validation,
                    state.stock_code,
                    run_dir,
                    run_dir / "cross_validation",
                    max_periods=options["official_max_periods"],
                    progress=self._official_progress_handler(state, scope_label),
                )
                tasks[future] = "official_validation"

            for future in as_completed(tasks):
                stage = tasks[future]
                try:
                    result = future.result()
                    warning_delta = 0
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
                        message = f"Raw Pack完成：{result.get('document_count', 0)}条资料"
                    else:
                        scope = str(options["official_validation_scope"])
                        compact = self._compact_official_result(result, scope)
                        outcome = official_stage_outcome(result, scope)
                        warning_delta = int(outcome["warning_delta"])
                        warnings += warning_delta
                        message = str(outcome["message"])
                        for key, value in (result.get("artifacts") or {}).items():
                            if value:
                                state.artifacts[f"official_{key}"] = str(value)
                    state.artifacts = {key: value for key, value in state.artifacts.items() if value}
                    self._save(state)
                    self._update_sidecar(
                        state,
                        stage=stage,
                        status="COMPLETED",
                        message=message,
                        result=compact,
                        warning_delta=warning_delta,
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


__all__ = [
    "DEFAULT_VISUAL_OPTIONS",
    "OFFICIAL_VALIDATION_SCOPES",
    "VisualJobManager",
    "normalize_visual_options",
    "official_max_periods",
    "official_stage_outcome",
]
