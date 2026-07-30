from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ashare_f10.ascope_bridge.finance import FinanceExportResult, IndustryTemplate
from ashare_f10.ascope_bridge.single_stock import (
    SingleStockExportError,
    export_single_stock,
    infer_industry_template,
)


def request() -> dict:
    return {
        "batch_id": "B001",
        "security_id": "SZSE.000002",
        "code": "000002",
        "name": "万科A",
        "exchange": "SZSE",
        "request_annual_from": "2019-12-31",
        "request_quarterly_from": "2022-03-31",
        "request_through": "2026-07-30",
        "required_available_at": True,
        "request_status": "PENDING",
    }


def setup_run(
    tmp_path: Path, *, status: str = "COMPLETED", failed_groups: int = 0
) -> tuple[Path, Path]:
    data = tmp_path / "data"
    run = data / "000002" / "job-1"
    (run / "normalized").mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "security_code": "000002",
                "field_key": "X",
                "report_date": "2025-12-31",
                "available_at": "2026-03-30",
                "value_num": 1,
            }
        ]
    ).to_csv(run / "normalized" / "facts.csv", index=False)
    (run / "combined.json").write_text(
        json.dumps({"metadata": {"failed_group_count": failed_groups}}), encoding="utf-8"
    )
    (run / "artifacts.json").write_text("{}", encoding="utf-8")
    pointer = data / "000002" / "latest.json"
    pointer.write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "stock_code": "000002",
                "status": status,
                "failed_groups": failed_groups,
                "output_dir": str(run),
                "updated_at_utc": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return data, run


def mapped() -> FinanceExportResult:
    annual = pd.DataFrame(
        [
            {
                "security_id": "SZSE.000002",
                "report_period": "2025-12-31",
                "available_at": "2026-03-30",
                "industry_template": "INDUSTRIAL",
                "revenue": 10.0,
            }
        ]
    )
    quarterly = pd.DataFrame(
        [
            {
                "security_id": "SZSE.000002",
                "report_period": "2025-12-31",
                "available_at": "2026-03-30",
                "industry_template": "INDUSTRIAL",
                "quarter": "Q4",
                "revenue": 3.0,
            }
        ]
    )
    status = pd.DataFrame(
        [
            {
                "security_id": "SZSE.000002",
                "report_period": "2025-12-31",
                "field_name": "revenue",
                "status": "SOURCE_DIRECT",
            }
        ]
    )
    return FinanceExportResult(
        annual,
        quarterly,
        status,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )


def test_export_and_cache_hit(tmp_path: Path) -> None:
    data, _run = setup_run(tmp_path)
    calls: list[int] = []

    def mapper(*_args, **_kwargs) -> FinanceExportResult:
        calls.append(1)
        return mapped()

    first = export_single_stock(
        request(),
        data_root=data,
        output_root=tmp_path / "out",
        as_of_date="2026-07-30",
        mapper=mapper,
    )
    second = export_single_stock(
        request(),
        data_root=data,
        output_root=tmp_path / "out",
        as_of_date="2026-07-30",
        mapper=mapper,
    )
    assert first.cache_status == "CACHE_MISS"
    assert second.cache_status == "CACHE_HIT"
    assert len(calls) == 1
    assert Path(first.output_dir, "financial_annual.csv").exists()


def test_source_change_invalidates_cache(tmp_path: Path) -> None:
    data, run = setup_run(tmp_path)
    calls: list[int] = []

    def mapper(*_args, **_kwargs) -> FinanceExportResult:
        calls.append(1)
        return mapped()

    export_single_stock(
        request(),
        data_root=data,
        output_root=tmp_path / "out",
        as_of_date="2026-07-30",
        mapper=mapper,
    )
    facts = run / "normalized" / "facts.csv"
    facts.write_text(facts.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = export_single_stock(
        request(),
        data_root=data,
        output_root=tmp_path / "out",
        as_of_date="2026-07-30",
        mapper=mapper,
    )
    assert result.cache_status == "CACHE_MISS"
    assert len(calls) == 2


def test_incomplete_current_run_fails_closed(tmp_path: Path) -> None:
    data, _run = setup_run(tmp_path, status="PARTIAL", failed_groups=1)
    with pytest.raises(SingleStockExportError) as error:
        export_single_stock(
            request(),
            data_root=data,
            output_root=tmp_path / "out",
            as_of_date="2026-07-30",
        )
    assert error.value.code == "CURRENT_RUN_INCOMPLETE"


def test_cutoff_mismatch_fails(tmp_path: Path) -> None:
    data, _run = setup_run(tmp_path)
    with pytest.raises(SingleStockExportError) as error:
        export_single_stock(
            request(),
            data_root=data,
            output_root=tmp_path / "out",
            as_of_date="2026-07-29",
        )
    assert error.value.code == "REQUEST_CUTOFF_MISMATCH"


def test_infer_financial_templates() -> None:
    assert infer_industry_template("平安银行") is IndustryTemplate.BANK
    assert infer_industry_template("中国人寿保险") is IndustryTemplate.INSURANCE
    assert infer_industry_template("中信证券") is IndustryTemplate.SECURITIES
    assert infer_industry_template("万科A") is IndustryTemplate.INDUSTRIAL
