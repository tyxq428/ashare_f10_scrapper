from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from ashare_f10.ascope_bridge.request_package import resolve_request_package
from ashare_f10.ascope_bridge.rollout import (
    RolloutError,
    initialize_rollout,
    mark_running,
    planned_actions,
    record_batch_result,
    reduce_full_market,
)


def _request_package(root: Path, *, batches: int = 3, rows_per_batch: int = 2) -> Path:
    source = root / "request"
    batch_root = source / "financial_batches"
    batch_root.mkdir(parents=True)
    manifest = {
        "status": "READY",
        "through": "2026-07-30",
        "batch_size": rows_per_batch,
        "batch_count": batches,
        "standard_request_count": batches * rows_per_batch,
        "identity_count": batches * rows_per_batch,
        "high_risk_st_count": 0,
        "archive_or_review_count": 0,
        "generated_at_utc": "2026-07-30T00:00:00Z",
        "selection_rule": "test fixture",
    }
    (source / "financial_request_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fields = [
        "batch_id",
        "security_id",
        "code",
        "name",
        "exchange",
        "request_annual_from",
        "request_quarterly_from",
        "request_through",
        "required_available_at",
        "request_status",
    ]
    counter = 1
    for index in range(1, batches + 1):
        batch_id = f"B{index:03d}"
        path = batch_root / f"{batch_id}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for _ in range(rows_per_batch):
                code = f"{counter:06d}"
                writer.writerow(
                    {
                        "batch_id": batch_id,
                        "security_id": f"SZSE.{code}",
                        "code": code,
                        "name": f"测试{code}",
                        "exchange": "SZSE",
                        "request_annual_from": "2019-12-31",
                        "request_quarterly_from": "2022-03-31",
                        "request_through": "2026-07-30",
                        "required_available_at": "True",
                        "request_status": "PENDING",
                    }
                )
                counter += 1
    return source


def _manifest(
    state: dict,
    *,
    batch_id: str,
    smoke_count: int = 0,
    status: str = "PASS",
    fixture_mode: bool = False,
    failed_count: int = 0,
    deferred_count: int = 0,
) -> dict:
    expected = state["smoke"] if smoke_count else state["batches"][batch_id]
    input_count = int(expected["expected_count"])
    return {
        "schema_version": 1,
        "status": status,
        "batch_id": batch_id,
        "as_of_date": state["as_of_date"],
        "package_sha256": state["package_sha256"],
        "selected_batch_sha256": expected["selected_batch_sha256"],
        "input_count": input_count,
        "successful_count": input_count - failed_count - deferred_count,
        "failed_count": failed_count,
        "deferred_count": deferred_count,
        "fixture_mode": fixture_mode,
        "non_investment_output": fixture_mode,
    }


def _record(
    state: dict,
    *,
    batch_id: str,
    smoke_count: int = 0,
    status: str = "PASS",
    run_id: int = 1,
    failed_count: int = 0,
    deferred_count: int = 0,
) -> dict:
    return record_batch_result(
        state,
        batch_id=batch_id,
        smoke_count=smoke_count,
        manifest=_manifest(
            state,
            batch_id=batch_id,
            smoke_count=smoke_count,
            status=status,
            failed_count=failed_count,
            deferred_count=deferred_count,
        ),
        run_id=run_id,
        artifact_name=f"artifact-{batch_id}-{run_id}",
        artifact_sha256=f"sha-{batch_id}-{run_id}",
    )


def test_rollout_enforces_smoke_b001_and_two_batch_parallelism(tmp_path: Path) -> None:
    source = _request_package(tmp_path)
    state = initialize_rollout(
        source,
        as_of_date="2026-07-30",
        smoke_count=1,
        max_active_batches=2,
    )
    assert state["phase"] == "B001_SMOKE_READY"
    assert planned_actions(state) == [
        {"batch_id": "B001", "smoke_count": 1, "kind": "SMOKE"}
    ]
    with pytest.raises(RolloutError, match="ROLLOUT_B001_ORDER_VIOLATION"):
        mark_running(state, batch_id="B001", smoke_count=0, run_id=1)

    state = mark_running(state, batch_id="B001", smoke_count=1, run_id=10)
    state = _record(state, batch_id="B001", smoke_count=1, run_id=10)
    assert state["phase"] == "B001_SMOKE_PASS"
    assert planned_actions(state)[0]["kind"] == "FULL_BATCH"

    state = mark_running(state, batch_id="B001", smoke_count=0, run_id=11)
    state = _record(state, batch_id="B001", run_id=11)
    assert state["phase"] == "B001_FULL_PASS"
    actions = planned_actions(state)
    assert [item["batch_id"] for item in actions] == ["B002", "B003"]

    state = mark_running(state, batch_id="B002", smoke_count=0, run_id=12)
    state = mark_running(state, batch_id="B003", smoke_count=0, run_id=13)
    assert len(state["active_batches"]) == 2
    assert planned_actions(state) == []
    with pytest.raises(RolloutError, match="ROLLOUT_SUCCESS_RESTART_FORBIDDEN"):
        mark_running(state, batch_id="B001", smoke_count=0, run_id=14)


def test_rollout_retries_only_failed_batch_and_preserves_success(tmp_path: Path) -> None:
    source = _request_package(tmp_path)
    state = initialize_rollout(source, as_of_date="2026-07-30", smoke_count=1)
    state = mark_running(state, batch_id="B001", smoke_count=1, run_id=1)
    state = _record(state, batch_id="B001", smoke_count=1, run_id=1)
    state = mark_running(state, batch_id="B001", smoke_count=0, run_id=2)
    state = _record(state, batch_id="B001", run_id=2)
    state = mark_running(state, batch_id="B002", smoke_count=0, run_id=3)
    state = mark_running(state, batch_id="B003", smoke_count=0, run_id=4)
    state = _record(
        state,
        batch_id="B002",
        status="PASS_WITH_GAPS",
        run_id=3,
        failed_count=1,
    )
    state = _record(state, batch_id="B003", run_id=4)
    assert state["batches"]["B003"]["status"] == "PASS"
    assert state["batches"]["B002"]["status"] == "PASS_WITH_GAPS"
    assert state["phase"] == "FULL_REDUCTION_READY"
    assert planned_actions(state) == []


def test_rollout_rejects_fixture_contamination(tmp_path: Path) -> None:
    source = _request_package(tmp_path)
    state = initialize_rollout(source, as_of_date="2026-07-30", smoke_count=1)
    state = mark_running(state, batch_id="B001", smoke_count=1, run_id=1)
    manifest = _manifest(state, batch_id="B001", smoke_count=1, fixture_mode=True)
    with pytest.raises(RolloutError, match="ROLLOUT_FIXTURE_CONTAMINATION"):
        record_batch_result(
            state,
            batch_id="B001",
            smoke_count=1,
            manifest=manifest,
            run_id=1,
            artifact_name="fixture",
            artifact_sha256="fixture",
        )


def _write_batch_output(
    request_source: Path,
    root: Path,
    *,
    batch_id: str,
    as_of_date: str,
) -> Path:
    resolved = resolve_request_package(
        request_source,
        batch_id=batch_id,
        as_of_date=as_of_date,
        smoke_count=0,
    )
    output = root / batch_id
    output.mkdir(parents=True)
    rows = list(resolved.rows)
    financial = pd.DataFrame(
        [
            {
                "security_id": row.security_id,
                "report_period": "2025-12-31",
                "available_at": "2026-03-31",
                "revenue": float(index + 1),
            }
            for index, row in enumerate(rows)
        ]
    )
    financial.to_csv(output / "financial_annual.csv", index=False)
    financial.assign(quarter="Q4").to_csv(output / "financial_quarterly.csv", index=False)
    pd.DataFrame(
        [
            {
                "security_id": row.security_id,
                "report_period": "2025-12-31",
                "field_name": "revenue",
                "status": "SOURCE_DIRECT",
            }
            for row in rows
        ]
    ).to_csv(output / "financial_field_status.csv", index=False)
    pd.DataFrame({"security_id": [row.security_id for row in rows]}).to_csv(
        output / "completed_securities.csv", index=False
    )
    for filename in (
        "failed_securities.csv",
        "deferred_securities.csv",
        "data_gaps.csv",
        "future_available_rows.csv",
        "duplicate_resolution.csv",
    ):
        pd.DataFrame(columns=["security_id"]).to_csv(output / filename, index=False)
    pd.DataFrame(
        [{"field_name": "revenue", "status": "SOURCE_DIRECT", "row_count": len(rows)}]
    ).to_csv(output / "field_coverage.csv", index=False)
    (output / "checkpoint.json").write_text("{}\n", encoding="utf-8")
    (output / "validation_report.json").write_text(
        json.dumps({"status": "PASS"}) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "batch_id": batch_id,
        "as_of_date": as_of_date,
        "package_sha256": resolved.package_sha256,
        "selected_batch_sha256": resolved.selected_batch_sha256,
        "input_count": len(rows),
        "successful_count": len(rows),
        "failed_count": 0,
        "deferred_count": 0,
        "fixture_mode": False,
        "non_investment_output": False,
    }
    (output / "batch_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return output


def test_full_market_reduction_conserves_batches_and_securities(tmp_path: Path) -> None:
    source = _request_package(tmp_path)
    batch_root = tmp_path / "batches"
    batch_dirs = [
        _write_batch_output(source, batch_root, batch_id=f"B{index:03d}", as_of_date="2026-07-30")
        for index in range(1, 4)
    ]
    output = tmp_path / "full"
    result = reduce_full_market(
        source,
        batch_dirs,
        as_of_date="2026-07-30",
        output_dir=output,
    )
    assert result["status"] == "PASS"
    assert result["batch_count"] == 3
    assert result["expected_security_count"] == 6
    assert result["completed_security_count"] == 6
    assert len(pd.read_csv(output / "financial_annual.csv")) == 6
    assert len(pd.read_csv(output / "batch_index.csv")) == 3


def test_full_market_reduction_fails_closed_on_duplicate_security(tmp_path: Path) -> None:
    source = _request_package(tmp_path)
    batch_root = tmp_path / "batches"
    batch_dirs = [
        _write_batch_output(source, batch_root, batch_id=f"B{index:03d}", as_of_date="2026-07-30")
        for index in range(1, 4)
    ]
    second = pd.read_csv(batch_dirs[1] / "completed_securities.csv")
    first = pd.read_csv(batch_dirs[0] / "completed_securities.csv")
    second.loc[0, "security_id"] = first.loc[0, "security_id"]
    second.to_csv(batch_dirs[1] / "completed_securities.csv", index=False)
    with pytest.raises(RolloutError, match="FULL_REDUCTION_DUPLICATE_SECURITY"):
        reduce_full_market(
            source,
            batch_dirs,
            as_of_date="2026-07-30",
            output_dir=tmp_path / "full",
        )
