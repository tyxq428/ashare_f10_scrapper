from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest

from ashare_f10.ascope_bridge.reducer import (
    BatchReductionError,
    reduce_batch,
)


@dataclass
class Manifest:
    through: str = "2026-07-30"


@dataclass
class Resolved:
    batch_id: str
    rows: tuple[dict, ...]
    package_sha256: str = "package"
    selected_batch_sha256: str = "batch"
    manifest: Manifest = field(default_factory=Manifest)


def request_rows() -> tuple[dict, ...]:
    return tuple(
        {
            "security_id": f"SZSE.{index:06d}",
            "code": f"{index:06d}",
            "name": f"N{index}",
            "request_annual_from": "2019-12-31",
            "request_quarterly_from": "2022-03-31",
            "request_through": "2026-07-30",
        }
        for index in (1, 2, 3)
    )


def write_stock_files(
    root: Path,
    security_id: str,
    *,
    future: bool = False,
    duplicate: bool = False,
) -> None:
    stock_dir = root / "stocks" / security_id
    stock_dir.mkdir(parents=True)
    annual = pd.DataFrame(
        [
            {
                "security_id": security_id,
                "report_period": "2025-12-31",
                "available_at": "2026-08-01" if future else "2026-03-30",
                "industry_template": "INDUSTRIAL",
                "revenue": 1,
            }
        ]
    )
    if duplicate:
        annual = pd.concat([annual, annual], ignore_index=True)
    annual.to_csv(stock_dir / "financial_annual.csv", index=False)
    pd.DataFrame(
        [
            {
                "security_id": security_id,
                "report_period": "2025-12-31",
                "available_at": "2026-03-30",
                "industry_template": "INDUSTRIAL",
                "quarter": "Q4",
                "revenue": 1,
            }
        ]
    ).to_csv(stock_dir / "financial_quarterly.csv", index=False)
    pd.DataFrame(
        [
            {
                "security_id": security_id,
                "security_code": security_id[-6:],
                "report_period": "2025-12-31",
                "field_name": "revenue",
                "status": "SOURCE_DIRECT",
            }
        ]
    ).to_csv(stock_dir / "financial_field_status.csv", index=False)
    for filename in (
        "data_gaps.csv",
        "future_available_rows.csv",
        "duplicate_resolution.csv",
    ):
        pd.DataFrame().to_csv(stock_dir / filename, index=False)
    (stock_dir / "single_stock_manifest.json").write_text(
        json.dumps(
            {
                "security_id": security_id,
                "as_of_date": "2026-07-30",
                "industry_template": "INDUSTRIAL",
                "fingerprint": security_id,
            }
        ),
        encoding="utf-8",
    )


def setup_batch(
    tmp_path: Path,
    *,
    future: bool = False,
    duplicate: bool = False,
) -> Path:
    root = tmp_path / "B001"
    root.mkdir()
    write_stock_files(
        root,
        "SZSE.000001",
        future=future,
        duplicate=duplicate,
    )
    write_stock_files(root, "SZSE.000002")
    stocks = [
        {
            "security_id": "SZSE.000001",
            "stock_code": "000001",
            "stock_name": "N1",
            "status": "COMPLETED",
            "attempt_count": 1,
        },
        {
            "security_id": "SZSE.000002",
            "stock_code": "000002",
            "stock_name": "N2",
            "status": "COMPLETED_WITH_GAPS",
            "attempt_count": 1,
        },
        {
            "security_id": "SZSE.000003",
            "stock_code": "000003",
            "stock_name": "N3",
            "status": "FAILED_RETRYABLE",
            "attempt_count": 2,
            "error_code": "TEMP",
            "message": "temporary",
        },
    ]
    (root / "checkpoint.json").write_text(
        json.dumps({"batch_id": "B001", "stocks": stocks}),
        encoding="utf-8",
    )
    return root


def test_reduce_mixed_batch(tmp_path: Path) -> None:
    root = setup_batch(tmp_path)
    result = reduce_batch(
        Resolved("B001", request_rows()),
        batch_output_dir=root,
    )
    assert result.status == "FAILED_RECOVERABLE"
    assert result.successful_count == 2
    assert result.failed_count == 1
    assert (root / "field_coverage.csv").exists()
    validation = json.loads(
        (root / "validation_report.json").read_text(encoding="utf-8")
    )
    assert validation["conservation_pass"] is True


def test_future_formal_row_fails(tmp_path: Path) -> None:
    root = setup_batch(tmp_path, future=True)
    with pytest.raises(BatchReductionError) as error:
        reduce_batch(
            Resolved("B001", request_rows()),
            batch_output_dir=root,
        )
    assert error.value.code == "REDUCTION_FUTURE_ROW"


def test_duplicate_key_fails(tmp_path: Path) -> None:
    root = setup_batch(tmp_path, duplicate=True)
    with pytest.raises(BatchReductionError) as error:
        reduce_batch(
            Resolved("B001", request_rows()),
            batch_output_dir=root,
        )
    assert error.value.code == "REDUCTION_DUPLICATE_KEY"


def test_checkpoint_request_mismatch_fails(tmp_path: Path) -> None:
    root = setup_batch(tmp_path)
    checkpoint = root / "checkpoint.json"
    value = json.loads(checkpoint.read_text(encoding="utf-8"))
    value["stocks"].reverse()
    checkpoint.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(BatchReductionError) as error:
        reduce_batch(
            Resolved("B001", request_rows()),
            batch_output_dir=root,
        )
    assert error.value.code == "REDUCTION_REQUEST_MISMATCH"
