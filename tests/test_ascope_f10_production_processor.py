from __future__ import annotations

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


def test_canonical_mapper_filters_unrelated_f10_fields(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_mapper(facts: pd.DataFrame, **_kwargs):
        captured["keys"] = facts["field_key"].tolist()
        return _empty_result()

    monkeypatch.setattr(production, "build_financial_tables", fake_mapper)
    facts = pd.DataFrame(
        [
            {"field_key": "OPERATE_INCOME", "value_num": 100},
            {"field_key": "HOLDER_RANK", "value_num": 1},
            {"field_key": "NOTICE_DATE", "value_text": "2026-04-25"},
        ]
    )

    production.build_canonical_financial_tables(facts)
    assert captured["keys"] == ["OPERATE_INCOME"]


def test_production_processor_normalizes_heartbeat_for_fetch(monkeypatch, tmp_path) -> None:
    calls = 0
    captured: dict[str, list[str]] = {}

    def fake_export(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SingleStockExportError("CURRENT_RUN_NOT_FOUND", "missing")
        return SimpleNamespace(status="PASS", to_dict=lambda: {"status": "PASS"})

    def fake_run(command, check=False):
        assert check is False
        captured["command"] = [str(value) for value in command]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(production, "export_single_stock", fake_export)
    monkeypatch.setattr(production.subprocess, "run", fake_run)

    result = production.canonical_stock_processor(
        {"security_id": "SZSE.000001", "code": "000001"},
        1,
        {
            "data_root": tmp_path / "data",
            "stock_output_root": tmp_path / "stocks",
            "as_of_date": "2026-07-30",
            "batch_output_dir": tmp_path / "batch",
            "endpoint_workers": 4,
            "heartbeat_seconds": 30.0,
        },
    )

    command = captured["command"]
    assert command[command.index("--heartbeat-seconds") + 1] == "30"
    assert result.status == "COMPLETED"
