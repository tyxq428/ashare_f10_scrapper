from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_f10.ascope_bridge.batch import StockProcessResult
from ashare_f10.ascope_bridge.single_stock import infer_industry_template


def fixture_stock_processor(
    request: dict[str, Any],
    _attempt: int,
    context: dict[str, Any],
) -> StockProcessResult:
    security_id = str(request["security_id"])
    code = str(request["code"]).zfill(6)
    cutoff = str(context["as_of_date"])
    output = Path(context["stock_output_root"]) / security_id
    output.mkdir(parents=True, exist_ok=True)
    template = infer_industry_template(str(request.get("name") or ""))
    annual = pd.DataFrame(
        [
            {
                "security_id": security_id,
                "report_period": "2025-12-31",
                "available_at": min(cutoff, "2026-03-31"),
                "industry_template": template.value,
                "revenue": 100.0
                if template.value == "INDUSTRIAL"
                else 1000.0,
                "gross_profit": 40.0
                if template.value == "INDUSTRIAL"
                else None,
                "deducted_net_profit": 10.0,
                "total_assets": 500.0,
                "total_equity": 200.0,
            }
        ]
    )
    quarterly = pd.DataFrame(
        [
            {
                "security_id": security_id,
                "report_period": "2025-12-31",
                "available_at": min(cutoff, "2026-03-31"),
                "industry_template": template.value,
                "quarter": "Q4",
                "revenue": 25.0,
                "gross_profit": 10.0
                if template.value == "INDUSTRIAL"
                else None,
                "deducted_net_profit": 2.5,
                "total_assets": 500.0,
                "total_equity": 200.0,
            }
        ]
    )
    field_status = pd.DataFrame(
        [
            {
                "security_id": security_id,
                "security_code": code,
                "report_period": "2025-12-31",
                "field_name": "gross_profit",
                "status": (
                    "NOT_APPLICABLE"
                    if template.value != "INDUSTRIAL"
                    else "SOURCE_DIRECT"
                ),
            },
            {
                "security_id": security_id,
                "security_code": code,
                "report_period": "2025-12-31",
                "field_name": "revenue",
                "status": "SOURCE_DIRECT",
            },
        ]
    )
    annual.to_csv(
        output / "financial_annual.csv",
        index=False,
        encoding="utf-8-sig",
    )
    quarterly.to_csv(
        output / "financial_quarterly.csv",
        index=False,
        encoding="utf-8-sig",
    )
    field_status.to_csv(
        output / "financial_field_status.csv",
        index=False,
        encoding="utf-8-sig",
    )
    for name in (
        "data_gaps.csv",
        "future_available_rows.csv",
        "duplicate_resolution.csv",
    ):
        pd.DataFrame(columns=["security_id"]).to_csv(
            output / name,
            index=False,
            encoding="utf-8-sig",
        )
    manifest = {
        "schema_version": "1.0.0",
        "mapping_version": "ascope-fixture-v1",
        "status": "PASS",
        "cache_status": "FIXTURE",
        "security_id": security_id,
        "stock_code": code,
        "stock_name": request.get("name"),
        "industry_template": template.value,
        "as_of_date": cutoff,
        "fingerprint": f"fixture:{security_id}:{cutoff}",
        "annual_rows": len(annual),
        "quarterly_rows": len(quarterly),
        "field_status_rows": len(field_status),
        "data_gap_rows": 0,
        "fixture_mode": True,
        "non_investment_output": True,
    }
    (output / "single_stock_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return StockProcessResult(
        status="COMPLETED",
        details={
            "fixture_mode": True,
            "output_dir": str(output),
            "security_id": security_id,
        },
    )
