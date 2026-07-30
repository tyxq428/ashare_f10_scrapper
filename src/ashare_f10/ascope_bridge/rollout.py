from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_f10.ascope_bridge.request_package import resolve_request_package

ROLLOUT_PHASES = {
    "WAITING_FOR_INPUT",
    "B001_SMOKE_READY",
    "B001_SMOKE_RUNNING",
    "B001_SMOKE_PASS",
    "B001_FULL_RUNNING",
    "B001_FULL_PASS",
    "FULL_ROLLOUT_RUNNING",
    "FULL_ROLLOUT_PARTIAL",
    "FULL_REDUCTION_READY",
    "COMPLETED",
    "BLOCKED",
}
SUCCESS_BATCH = {"PASS", "PASS_WITH_GAPS"}
REQUIRED_BATCH_FILES = {
    "batch_manifest.json",
    "validation_report.json",
    "financial_annual.csv",
    "financial_quarterly.csv",
    "financial_field_status.csv",
    "completed_securities.csv",
    "failed_securities.csv",
    "deferred_securities.csv",
    "data_gaps.csv",
    "future_available_rows.csv",
    "duplicate_resolution.csv",
    "field_coverage.csv",
    "checkpoint.json",
}


class RolloutError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RolloutError("ROLLOUT_JSON_INVALID", str(path)) from exc
    if not isinstance(value, dict):
        raise RolloutError("ROLLOUT_JSON_INVALID", str(path))
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _batch_ids(count: int) -> list[str]:
    if count <= 0 or count > 999:
        raise RolloutError("ROLLOUT_BATCH_COUNT_INVALID", str(count))
    return [f"B{index:03d}" for index in range(1, count + 1)]


def initialize_rollout(
    request_source: Path,
    *,
    as_of_date: str,
    state_path: Path | None = None,
    smoke_count: int = 5,
    fixture_mode: bool = False,
    max_active_batches: int = 2,
) -> dict[str, Any]:
    if max_active_batches != 2:
        raise RolloutError(
            "ROLLOUT_PARALLELISM_INVALID",
            "max_active_batches must equal 2",
        )
    smoke = resolve_request_package(
        request_source,
        batch_id="B001",
        as_of_date=as_of_date,
        smoke_count=smoke_count,
    )
    batch_ids = _batch_ids(smoke.manifest.batch_count)
    if set(batch_ids) != set(smoke.all_batch_sha256):
        raise RolloutError(
            "ROLLOUT_BATCH_SET_MISMATCH",
            f"manifest={batch_ids}, package={sorted(smoke.all_batch_sha256)}",
        )

    batches: dict[str, dict[str, Any]] = {}
    total_rows = 0
    for batch_id in batch_ids:
        resolved = resolve_request_package(
            request_source,
            batch_id=batch_id,
            as_of_date=as_of_date,
            smoke_count=0,
        )
        total_rows += resolved.source_row_count
        batches[batch_id] = {
            "batch_id": batch_id,
            "expected_count": resolved.source_row_count,
            "selected_batch_sha256": resolved.selected_batch_sha256,
            "status": "PENDING",
            "run_id": None,
            "artifact_name": None,
            "artifact_sha256": None,
            "attempts": 0,
            "last_error": None,
            "updated_at_utc": utc_now(),
        }
    if total_rows != smoke.manifest.standard_request_count:
        raise RolloutError(
            "ROLLOUT_REQUEST_CONSERVATION_FAILED",
            f"rows={total_rows}, manifest={smoke.manifest.standard_request_count}",
        )

    state: dict[str, Any] = {
        "schema_version": 1,
        "state_revision": 1,
        "phase": "B001_SMOKE_READY",
        "request_source": str(request_source),
        "request_source_kind": smoke.source_kind,
        "request_source_name": smoke.source_name,
        "package_sha256": smoke.package_sha256,
        "manifest_sha256": smoke.manifest_sha256,
        "as_of_date": as_of_date,
        "expected_batch_count": smoke.manifest.batch_count,
        "expected_security_count": smoke.manifest.standard_request_count,
        "smoke_count": smoke_count,
        "fixture_mode": bool(fixture_mode),
        "non_investment_output": bool(fixture_mode),
        "max_active_batches": max_active_batches,
        "active_batches": [],
        "smoke": {
            "status": "PENDING",
            "expected_count": len(smoke.rows),
            "selected_batch_sha256": smoke.selected_batch_sha256,
            "run_id": None,
            "artifact_name": None,
            "artifact_sha256": None,
            "last_error": None,
        },
        "batches": batches,
        "created_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "completed_at_utc": None,
        "block_reason": None,
    }
    if state_path:
        _atomic_json(state_path, state)
    return state


def load_rollout(path: Path) -> dict[str, Any]:
    state = _read_json(path)
    if state.get("phase") not in ROLLOUT_PHASES:
        raise RolloutError("ROLLOUT_PHASE_INVALID", str(state.get("phase")))
    return state


def save_rollout(path: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(state)
    value["state_revision"] = int(value.get("state_revision") or 0) + 1
    value["updated_at_utc"] = utc_now()
    _atomic_json(path, value)
    return value


def planned_actions(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    phase = str(state.get("phase"))
    if phase == "B001_SMOKE_READY":
        return [
            {
                "batch_id": "B001",
                "smoke_count": int(state["smoke_count"]),
                "kind": "SMOKE",
            }
        ]
    if phase == "B001_SMOKE_PASS":
        return [{"batch_id": "B001", "smoke_count": 0, "kind": "FULL_BATCH"}]
    valid = {"B001_FULL_PASS", "FULL_ROLLOUT_RUNNING", "FULL_ROLLOUT_PARTIAL"}
    if phase not in valid:
        return []

    active = set(state.get("active_batches") or [])
    available = max(0, int(state["max_active_batches"]) - len(active))
    actions: list[dict[str, Any]] = []
    for batch_id, record in state["batches"].items():
        if batch_id == "B001" or batch_id in active:
            continue
        if record.get("status") not in {"PENDING", "FAILED", "DEFERRED"}:
            continue
        actions.append(
            {"batch_id": batch_id, "smoke_count": 0, "kind": "FULL_BATCH"}
        )
        if len(actions) >= available:
            break
    return actions


def mark_running(
    state: Mapping[str, Any],
    *,
    batch_id: str,
    smoke_count: int,
    run_id: int | str,
) -> dict[str, Any]:
    value = json.loads(json.dumps(state))
    if smoke_count:
        if batch_id != "B001" or value["phase"] != "B001_SMOKE_READY":
            raise RolloutError(
                "ROLLOUT_SMOKE_ORDER_VIOLATION",
                f"phase={value['phase']}",
            )
        value["phase"] = "B001_SMOKE_RUNNING"
        value["smoke"].update(status="RUNNING", run_id=int(run_id), last_error=None)
        return value

    record = value["batches"].get(batch_id)
    if record is None:
        raise RolloutError("ROLLOUT_UNKNOWN_BATCH", batch_id)
    if record["status"] in SUCCESS_BATCH:
        raise RolloutError("ROLLOUT_SUCCESS_RESTART_FORBIDDEN", batch_id)

    if batch_id == "B001":
        if value["phase"] != "B001_SMOKE_PASS":
            raise RolloutError(
                "ROLLOUT_B001_ORDER_VIOLATION",
                f"phase={value['phase']}",
            )
        value["phase"] = "B001_FULL_RUNNING"
    elif value["phase"] not in {
        "B001_FULL_PASS",
        "FULL_ROLLOUT_RUNNING",
        "FULL_ROLLOUT_PARTIAL",
    }:
        raise RolloutError(
            "ROLLOUT_FULL_ORDER_VIOLATION",
            f"phase={value['phase']}",
        )

    active = list(value.get("active_batches") or [])
    if batch_id not in active:
        active.append(batch_id)
    if len(active) > int(value["max_active_batches"]):
        raise RolloutError("ROLLOUT_PARALLELISM_EXCEEDED", str(active))
    value["active_batches"] = active
    record.update(
        status="RUNNING",
        run_id=int(run_id),
        attempts=int(record.get("attempts") or 0) + 1,
        last_error=None,
        updated_at_utc=utc_now(),
    )
    if batch_id != "B001":
        value["phase"] = "FULL_ROLLOUT_RUNNING"
    return value


def _validate_batch_manifest(
    state: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    batch_id: str,
    smoke_count: int,
) -> None:
    if manifest.get("batch_id") != batch_id:
        raise RolloutError(
            "ROLLOUT_BATCH_ID_MISMATCH",
            str(manifest.get("batch_id")),
        )
    if manifest.get("as_of_date") != state.get("as_of_date"):
        raise RolloutError(
            "ROLLOUT_CUTOFF_MISMATCH",
            str(manifest.get("as_of_date")),
        )
    if manifest.get("package_sha256") != state.get("package_sha256"):
        raise RolloutError("ROLLOUT_PACKAGE_HASH_MISMATCH", batch_id)
    expected_hash = (
        state["smoke"]["selected_batch_sha256"]
        if smoke_count
        else state["batches"][batch_id]["selected_batch_sha256"]
    )
    if manifest.get("selected_batch_sha256") != expected_hash:
        raise RolloutError("ROLLOUT_BATCH_HASH_MISMATCH", batch_id)

    fixture = bool(manifest.get("fixture_mode"))
    prohibited = bool(manifest.get("non_investment_output"))
    if bool(state.get("fixture_mode")) != fixture:
        raise RolloutError("ROLLOUT_FIXTURE_CONTAMINATION", batch_id)
    if fixture != prohibited:
        raise RolloutError("ROLLOUT_INVESTMENT_MARKER_INVALID", batch_id)

    expected_count = int(
        state["smoke"]["expected_count"]
        if smoke_count
        else state["batches"][batch_id]["expected_count"]
    )
    if int(manifest.get("input_count") or -1) != expected_count:
        raise RolloutError(
            "ROLLOUT_INPUT_COUNT_MISMATCH",
            f"{batch_id}: {manifest.get('input_count')} != {expected_count}",
        )


def record_batch_result(
    state: Mapping[str, Any],
    *,
    batch_id: str,
    smoke_count: int,
    manifest: Mapping[str, Any],
    run_id: int | str,
    artifact_name: str,
    artifact_sha256: str,
) -> dict[str, Any]:
    _validate_batch_manifest(
        state,
        manifest,
        batch_id=batch_id,
        smoke_count=smoke_count,
    )
    value = json.loads(json.dumps(state))
    status = str(manifest.get("status") or "").upper()
    success = status in SUCCESS_BATCH

    if smoke_count:
        if value["phase"] != "B001_SMOKE_RUNNING":
            raise RolloutError(
                "ROLLOUT_SMOKE_RESULT_ORDER_VIOLATION",
                value["phase"],
            )
        value["smoke"].update(
            status=status if success else "FAILED",
            run_id=int(run_id),
            artifact_name=artifact_name,
            artifact_sha256=artifact_sha256,
            last_error=None if success else status,
        )
        value["phase"] = "B001_SMOKE_PASS" if success else "BLOCKED"
        value["block_reason"] = None if success else "B001_SMOKE_FAILED"
        return value

    value["active_batches"] = [
        item for item in value.get("active_batches") or [] if item != batch_id
    ]
    record = value["batches"][batch_id]
    record.update(
        status=(
            status
            if success
            else "DEFERRED"
            if int(manifest.get("deferred_count") or 0)
            else "FAILED"
        ),
        run_id=int(run_id),
        artifact_name=artifact_name,
        artifact_sha256=artifact_sha256,
        last_error=None if success else status,
        updated_at_utc=utc_now(),
    )
    if batch_id == "B001":
        value["phase"] = "B001_FULL_PASS" if success else "BLOCKED"
        value["block_reason"] = None if success else "B001_FULL_FAILED"
        return value

    remaining = [
        item
        for item, candidate in value["batches"].items()
        if item != "B001" and candidate["status"] not in SUCCESS_BATCH
    ]
    active = value["active_batches"]
    if not remaining and not active:
        value["phase"] = "FULL_REDUCTION_READY"
    elif any(
        value["batches"][item]["status"] in {"FAILED", "DEFERRED"}
        for item in remaining
    ):
        value["phase"] = "FULL_ROLLOUT_PARTIAL"
    else:
        value["phase"] = "FULL_ROLLOUT_RUNNING"
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RolloutError("FULL_REDUCTION_FILE_MISSING", str(path))
    return pd.read_csv(path, dtype={"security_id": "string"})


def _concat(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    values = list(frames)
    if not values:
        return pd.DataFrame()
    columns: list[str] = []
    for frame in values:
        for column in frame.columns:
            if column not in columns:
                columns.append(column)
    return pd.concat(
        [frame.reindex(columns=columns) for frame in values],
        ignore_index=True,
    )


def reduce_full_market(
    request_source: Path,
    batch_dirs: Sequence[Path],
    *,
    as_of_date: str,
    output_dir: Path,
    fixture_mode: bool = False,
) -> dict[str, Any]:
    first = resolve_request_package(
        request_source,
        batch_id="B001",
        as_of_date=as_of_date,
        smoke_count=0,
    )
    expected_ids: set[str] = set()
    expected_hashes: dict[str, str] = {}
    for batch_id in _batch_ids(first.manifest.batch_count):
        resolved = resolve_request_package(
            request_source,
            batch_id=batch_id,
            as_of_date=as_of_date,
            smoke_count=0,
        )
        expected_ids.update(row.security_id for row in resolved.rows)
        expected_hashes[batch_id] = resolved.selected_batch_sha256
    if len(batch_dirs) != first.manifest.batch_count:
        raise RolloutError(
            "FULL_REDUCTION_BATCH_COUNT_MISMATCH",
            f"{len(batch_dirs)} != {first.manifest.batch_count}",
        )

    annual_frames: list[pd.DataFrame] = []
    quarterly_frames: list[pd.DataFrame] = []
    status_frames: list[pd.DataFrame] = []
    gap_frames: list[pd.DataFrame] = []
    completed_ids: set[str] = set()
    batch_index: list[dict[str, Any]] = []
    seen_batches: set[str] = set()

    for batch_dir in batch_dirs:
        missing = sorted(
            name for name in REQUIRED_BATCH_FILES if not (batch_dir / name).exists()
        )
        if missing:
            raise RolloutError(
                "FULL_REDUCTION_FILE_MISSING",
                f"{batch_dir}: {missing}",
            )
        manifest = _read_json(batch_dir / "batch_manifest.json")
        batch_id = str(manifest.get("batch_id") or "")
        if batch_id in seen_batches:
            raise RolloutError("FULL_REDUCTION_DUPLICATE_BATCH", batch_id)
        seen_batches.add(batch_id)
        if batch_id not in expected_hashes:
            raise RolloutError("FULL_REDUCTION_UNKNOWN_BATCH", batch_id)
        if manifest.get("status") not in SUCCESS_BATCH:
            raise RolloutError("FULL_REDUCTION_BATCH_NOT_SUCCESSFUL", batch_id)
        if manifest.get("as_of_date") != as_of_date:
            raise RolloutError("FULL_REDUCTION_CUTOFF_MISMATCH", batch_id)
        if manifest.get("package_sha256") != first.package_sha256:
            raise RolloutError("FULL_REDUCTION_PACKAGE_HASH_MISMATCH", batch_id)
        if manifest.get("selected_batch_sha256") != expected_hashes[batch_id]:
            raise RolloutError("FULL_REDUCTION_BATCH_HASH_MISMATCH", batch_id)

        fixture = bool(manifest.get("fixture_mode"))
        prohibited = bool(manifest.get("non_investment_output"))
        if fixture != bool(fixture_mode) or prohibited != bool(fixture_mode):
            raise RolloutError("FULL_REDUCTION_FIXTURE_CONTAMINATION", batch_id)

        failed = _read_csv(batch_dir / "failed_securities.csv")
        deferred = _read_csv(batch_dir / "deferred_securities.csv")
        if not failed.empty or not deferred.empty:
            raise RolloutError("FULL_REDUCTION_NONTERMINAL_SECURITIES", batch_id)
        completed = _read_csv(batch_dir / "completed_securities.csv")
        ids = set(
            completed.get("security_id", pd.Series(dtype="string"))
            .dropna()
            .astype(str)
        )
        if completed_ids & ids:
            raise RolloutError("FULL_REDUCTION_DUPLICATE_SECURITY", batch_id)
        completed_ids.update(ids)

        annual_frames.append(_read_csv(batch_dir / "financial_annual.csv"))
        quarterly_frames.append(_read_csv(batch_dir / "financial_quarterly.csv"))
        status_frames.append(_read_csv(batch_dir / "financial_field_status.csv"))
        gap_frames.append(_read_csv(batch_dir / "data_gaps.csv"))
        batch_index.append(
            {
                "batch_id": batch_id,
                "input_count": int(manifest.get("input_count") or 0),
                "successful_count": int(manifest.get("successful_count") or 0),
                "batch_manifest_sha256": _sha256(
                    batch_dir / "batch_manifest.json"
                ),
                "batch_dir": str(batch_dir),
            }
        )

    if seen_batches != set(expected_hashes):
        raise RolloutError(
            "FULL_REDUCTION_BATCH_SET_MISMATCH",
            f"missing={sorted(set(expected_hashes) - seen_batches)}",
        )
    if completed_ids != expected_ids:
        raise RolloutError(
            "FULL_REDUCTION_SECURITY_CONSERVATION_FAILED",
            (
                f"missing={len(expected_ids - completed_ids)}, "
                f"extra={len(completed_ids - expected_ids)}"
            ),
        )

    annual = _concat(annual_frames)
    quarterly = _concat(quarterly_frames)
    field_status = _concat(status_frames)
    data_gaps = _concat(gap_frames)
    for name, frame in (("annual", annual), ("quarterly", quarterly)):
        if frame.empty:
            continue
        if bool(frame.duplicated(["security_id", "report_period"], keep=False).any()):
            raise RolloutError("FULL_REDUCTION_DUPLICATE_KEY", name)
        available = pd.to_datetime(frame["available_at"], errors="coerce")
        if available.isna().any():
            raise RolloutError("FULL_REDUCTION_AVAILABLE_AT_MISSING", name)
        if (available > pd.Timestamp(as_of_date)).any():
            raise RolloutError("FULL_REDUCTION_FUTURE_ROW", name)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "financial_annual.csv": annual,
        "financial_quarterly.csv": quarterly,
        "financial_field_status.csv": field_status,
        "data_gaps.csv": data_gaps,
        "batch_index.csv": pd.DataFrame(batch_index).sort_values("batch_id"),
    }
    for filename, frame in outputs.items():
        frame.to_csv(output_dir / filename, index=False, encoding="utf-8-sig")

    report = {
        "schema_version": 1,
        "status": "PASS",
        "as_of_date": as_of_date,
        "package_sha256": first.package_sha256,
        "batch_count": len(seen_batches),
        "expected_security_count": len(expected_ids),
        "completed_security_count": len(completed_ids),
        "annual_rows": len(annual),
        "quarterly_rows": len(quarterly),
        "field_status_rows": len(field_status),
        "data_gap_rows": len(data_gaps),
        "fixture_mode": bool(fixture_mode),
        "non_investment_output": bool(fixture_mode),
        "generated_at_utc": utc_now(),
    }
    _atomic_json(output_dir / "full_market_validation.json", report)
    manifest = {
        **report,
        "output_sha256": {
            path.name: _sha256(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "bundle_manifest.json"
        },
    }
    _atomic_json(output_dir / "bundle_manifest.json", manifest)
    return manifest
