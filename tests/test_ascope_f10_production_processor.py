from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import ashare_f10.ascope_bridge.production_processor as production
from ashare_f10.ascope_bridge.finance import FinanceExportResult
from ashare_f10.ascope_bridge.single_stock import SingleStockExportError


def _empty_result() -> FinanceExportResult:
    return FinanceExportResult(
        annual=pd.DataFrame(),
        quarterly=pd.DataFrame(),
        field_status=pd.DataFrame(),
        future_rows=pd.DataFrame(),
        data_gaps=pd.DataFrame(),
        duplicate_resolution=pd.DataFrame(),
    )


def _fact(field_key: str, family: str, value: float | None) -> dict:
    return {
        "security_code": "000001",
        "family": family,
        "record_key": f"000001|{family}|2026-03-31",
        "report_date": "2026-03-31",
        "available_at": "2026-04-25",
        "field_key": field_key,
        "value_num": value,
        "value_text": None if value is None else str(value),
        "unit": "元",
    }


def test_canonical_mapper_binds_fields_to_statement_families(monkeypatch) -> None:
    captured: dict[str, pd.DataFrame] = {}

    def fake_mapper(facts: pd.DataFrame, **_kwargs):
        captured["facts"] = facts.copy()
        return _empty_result()

    monkeypatch.setattr(production, "build_financial_tables", fake_mapper)
    facts = pd.DataFrame(
        [
            _fact("OPERATE_INCOME", "RPT_F10_FINANCE_GINCOME", 100),
            _fact("OPERATE_INCOME", "RPT_F10_FINANCE_GINCOMEQC", 25),
            _fact("TOTAL_ASSETS", "RPT_F10_FINANCE_GBALANCE", 1_000),
            _fact("TOTAL_ASSETS", "RPT_F10_FINANCE_GRATIO", 100),
            _fact("HOLDER_RANK", "RPT_F10_EH_HOLDERS", 1),
            _fact("MONETARYFUNDS", "RPT_F10_FINANCE_DUPONT", 12),
        ]
    )

    production.build_canonical_financial_tables(facts)
    selected = captured["facts"]
    assert list(selected["field_key"]) == [
        "OPERATE_INCOME",
        "OPERATE_INCOME",
        "TOTAL_ASSETS",
    ]
    assert list(selected["family"]) == [
        "RPT_F10_FINANCE_GINCOME",
        "RPT_F10_FINANCE_GINCOMEQC",
        "RPT_F10_FINANCE_GBALANCE",
    ]
    assert list(selected["period_basis"]) == [
        "CUMULATIVE",
        "STANDALONE",
        "CUMULATIVE",
    ]
    assert list(selected["source_priority"]) == [100, 100, 100]


def test_canonical_selector_drops_empty_and_exact_duplicates() -> None:
    row = _fact("NETCASH_OPERATE", "RPT_F10_FINANCE_GCASHFLOW", 88)
    empty = _fact("NETCASH_OPERATE", "RPT_F10_FINANCE_GCASHFLOW", None)
    selected = production.select_canonical_source_facts(
        pd.DataFrame([row, dict(row), empty])
    )
    assert len(selected) == 1
    assert selected.iloc[0]["value_num"] == 88


def test_scope_finance_export_uses_request_windows_and_pads_codes() -> None:
    def frame(periods: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "security_id": "SZSE.000001",
                    "security_code": 1,
                    "report_period": period,
                }
                for period in periods
            ]
        )

    result = FinanceExportResult(
        annual=frame(["2018-12-31", "2019-12-31", "2025-12-31", "2026-12-31"]),
        quarterly=frame(["2021-12-31", "2022-03-31", "2026-06-30", "2026-09-30"]),
        field_status=frame(
            ["2018-12-31", "2019-12-31", "2021-09-30", "2022-03-31", "2026-09-30"]
        ),
        future_rows=frame(["2018-12-31", "2022-03-31", "2026-09-30"]),
        data_gaps=frame(["2018-12-31", "2019-12-31", "2022-03-31", "2026-09-30"]),
        duplicate_resolution=frame(["2018-12-31", "2025-12-31"]),
    )
    scoped = production.scope_finance_export(
        result,
        {
            "request_annual_from": "2019-12-31",
            "request_quarterly_from": "2022-03-31",
            "request_through": "2026-07-30",
        },
    )

    assert list(scoped.annual["report_period"]) == ["2019-12-31", "2025-12-31"]
    assert list(scoped.quarterly["report_period"]) == ["2022-03-31", "2026-06-30"]
    assert list(scoped.field_status["report_period"]) == ["2019-12-31", "2022-03-31"]
    assert list(scoped.future_rows["report_period"]) == ["2022-03-31"]
    assert list(scoped.data_gaps["report_period"]) == ["2019-12-31", "2022-03-31"]
    assert list(scoped.duplicate_resolution["report_period"]) == ["2025-12-31"]
    assert set(scoped.field_status["security_code"]) == {"000001"}


def test_production_processor_prunes_completed_transient_fetch(monkeypatch, tmp_path) -> None:
    calls = 0
    captured: dict[str, list[str]] = {}
    batch_root = tmp_path / "batch"
    stocks_root = tmp_path / "stocks"

    def fake_export(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SingleStockExportError("CURRENT_RUN_NOT_FOUND", "missing")
        output_dir = stocks_root / "SZSE.000001"
        output_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(status="PASS", to_dict=lambda: {"status": "PASS"})

    def fake_run(command, check=False):
        assert check is False
        captured["command"] = [str(value) for value in command]
        report = Path(command[command.index("--report") + 1])
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text('{"status":"PASS"}\n', encoding="utf-8")
        (report.parent / "large-transient.bin").write_bytes(b"x" * 1024)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(production, "export_single_stock", fake_export)
    monkeypatch.setattr(production.subprocess, "run", fake_run)

    result = production.canonical_stock_processor(
        {
            "security_id": "SZSE.000001",
            "code": "000001",
            "request_annual_from": "2019-12-31",
            "request_quarterly_from": "2022-03-31",
            "request_through": "2026-07-30",
        },
        1,
        {
            "data_root": tmp_path / "data",
            "stock_output_root": stocks_root,
            "as_of_date": "2026-07-30",
            "batch_output_dir": batch_root,
            "endpoint_workers": 4,
            "heartbeat_seconds": 30.0,
        },
    )

    command = captured["command"]
    assert command[command.index("--heartbeat-seconds") + 1] == "30"
    assert result.status == "COMPLETED"
    assert not (batch_root / "_f10_runs" / "SZSE.000001").exists()
    assert (
        stocks_root / "SZSE.000001" / "source_fetch_report.json"
    ).read_text(encoding="utf-8") == '{"status":"PASS"}\n'
