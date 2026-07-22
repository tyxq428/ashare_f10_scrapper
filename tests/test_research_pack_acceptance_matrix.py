from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from ashare_f10.research_pack import run_research_pack
from ashare_f10.research_pack.exporter import validate_research_pack
from ashare_f10.research_pack.models import ResearchPackArtifacts
from ashare_f10.validation.models import OfficialFact

FACT_COLUMNS = [
    "security_code",
    "theme",
    "family",
    "dataset",
    "record_key",
    "report_date",
    "event_date",
    "period_type",
    "data_semantics",
    "field_key",
    "field_name_cn",
    "field_category",
    "value_text",
    "value_num",
    "unit",
    "source_url",
    "source_status",
]


def _fact(
    security_code: str,
    field_key: str,
    value: float,
    *,
    family: str,
    name: str,
    unit: str = "元",
) -> dict[str, object]:
    report_date = "2025-12-31"
    semantics = "point_in_time" if "BALANCE" in family or "SHARE" in family else "flow"
    return {
        "security_code": security_code,
        "theme": "财务分析",
        "family": family,
        "dataset": family,
        "record_key": f"{security_code}|{family}|{report_date}",
        "report_date": report_date,
        "event_date": report_date,
        "period_type": "FY",
        "data_semantics": semantics,
        "field_key": field_key,
        "field_name_cn": name,
        "field_category": "PAGE_DISPLAY_FIELD",
        "value_text": str(value),
        "value_num": value,
        "unit": unit,
        "source_url": "https://eastmoney.invalid/api",
        "source_status": "FACT_DIRECT",
    }


def _build_run_dir(
    root: Path,
    security_code: str,
    *,
    include_official: bool,
    explicit_zero: bool = False,
) -> Path:
    normalized = root / "normalized"
    cross_validation = root / "cross_validation"
    normalized.mkdir(parents=True)
    cross_validation.mkdir(parents=True)
    rows = [
        _fact(
            security_code,
            "OPERATE_INCOME",
            1_000_000_000.0,
            family="RPT_F10_FINANCE_GINCOME",
            name="营业收入",
        ),
        _fact(
            security_code,
            "PARENT_NETPROFIT",
            100_000_000.0,
            family="RPT_F10_FINANCE_GINCOME",
            name="归母净利润",
        ),
        _fact(
            security_code,
            "NETCASH_OPERATE",
            150_000_000.0,
            family="RPT_F10_FINANCE_GCASHFLOW",
            name="经营活动现金流量净额",
        ),
        _fact(
            security_code,
            "CONSTRUCT_LONG_ASSET",
            30_000_000.0,
            family="RPT_F10_FINANCE_GCASHFLOW",
            name="购建长期资产支付现金",
        ),
        _fact(
            security_code,
            "RESEARCH_EXPENSE",
            0.0 if explicit_zero else 20_000_000.0,
            family="RPT_F10_FINANCE_GINCOME",
            name="研发费用",
        ),
        _fact(
            security_code,
            "TOTAL_SHARES",
            1_000_000_000.0,
            family="RPT_F10_SHARE_STRUCTURE",
            name="总股本",
            unit="股",
        ),
    ]
    facts = pd.DataFrame(rows, columns=FACT_COLUMNS)
    facts_path = normalized / "facts.parquet"
    facts.to_parquet(facts_path, index=False)
    connection = duckdb.connect(str(normalized / "f10.duckdb"))
    try:
        connection.execute("CREATE TABLE facts AS SELECT * FROM read_parquet(?)", [str(facts_path)])
    finally:
        connection.close()

    if include_official:
        official_facts = [
            OfficialFact(
                security_code=security_code,
                report_date="2025-12-31",
                statement_type="income_statement",
                scope="consolidated",
                field_key="OPERATE_INCOME",
                field_name_report="营业收入",
                value=1_000_000_000.0,
                unit="元",
                normalized_unit="元",
                source_document=f"{security_code} 2025年年度报告",
                source_url="https://official.invalid/annual.pdf",
                source_page=80,
                source_row="营业收入 1,000,000,000.00",
                extraction_method="PDF_TABLE",
                precision_tolerance=0.01,
                confidence="high",
                document_id=f"{security_code}-annual-2025",
                available_at="2026-03-20",
            ),
            OfficialFact(
                security_code=security_code,
                report_date="2025-12-31",
                statement_type="income_statement",
                scope="consolidated",
                field_key="RESEARCH_EXPENSE",
                field_name_report="研发费用",
                value=0.0 if explicit_zero else 20_000_000.0,
                unit="元",
                normalized_unit="元",
                source_document=f"{security_code} 2025年年度报告",
                source_url="https://official.invalid/annual.pdf",
                source_page=82,
                source_row="研发费用 0.00" if explicit_zero else "研发费用 20,000,000.00",
                extraction_method="PDF_TABLE",
                precision_tolerance=0.01,
                confidence="high",
                source_status="FACT_ZERO_EXPLICIT" if explicit_zero else "FACT_DIRECT",
                document_id=f"{security_code}-annual-2025",
                available_at="2026-03-20",
            ),
        ]
        pd.DataFrame([fact.to_dict() for fact in official_facts]).to_parquet(
            cross_validation / "official_direct_facts.parquet",
            index=False,
        )

    (root / "artifacts.json").write_text(
        json.dumps({"duckdb": str(normalized / "f10.duckdb")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return root


def _copied_artifacts(copy_dir: Path, security_code: str) -> ResearchPackArtifacts:
    return ResearchPackArtifacts(
        output_dir=copy_dir,
        manifest_json=copy_dir / "manifest.json",
        summary_json=copy_dir / "summary.json",
        package_json=copy_dir / "exports" / f"{security_code}_research_pack.json",
        package_excel=copy_dir / "exports" / f"{security_code}_research_pack.xlsx",
        package_duckdb=copy_dir / "exports" / f"{security_code}_research_pack.duckdb",
        quality_json=copy_dir / "quality" / "research_pack_quality.json",
        checkpoint_json=copy_dir / "checkpoint.json",
    )


@pytest.mark.parametrize(
    ("security_code", "include_official"),
    [("688521", True), ("002352", True), ("920001", False)],
)
def test_multi_market_matrix_is_idempotent_and_portable(
    tmp_path: Path,
    security_code: str,
    include_official: bool,
) -> None:
    run_dir = _build_run_dir(
        tmp_path / security_code,
        security_code,
        include_official=include_official,
    )
    first = run_research_pack(security_code, run_dir, as_of_date="2026-03-31")
    assert first["status"] == "COMPLETED"
    assert first["cache_hit"] is False

    second = run_research_pack(security_code, run_dir, as_of_date="2026-03-31")
    assert second["status"] == "COMPLETED"
    assert second["cache_hit"] is True

    output_dir = Path(first["artifacts"]["output_dir"])
    portable = tmp_path / f"{security_code}-portable-copy"
    shutil.copytree(output_dir, portable)
    quality = validate_research_pack(_copied_artifacts(portable, security_code))
    assert quality["status"] == "PASS"

    connection = duckdb.connect(
        str(portable / "exports" / f"{security_code}_research_pack.duckdb"),
        read_only=True,
    )
    try:
        assert connection.execute("SELECT count(*) FROM source_facts").fetchone()[0] >= 6
        assert connection.execute("SELECT count(*) FROM canonical_observations").fetchone()[0] > 0
        assert connection.execute("SELECT count(*) FROM fact_lineage").fetchone()[0] > 0
    finally:
        connection.close()


def test_explicit_zero_is_preserved_as_a_fact_not_a_missing_value(tmp_path: Path) -> None:
    security_code = "002352"
    run_dir = _build_run_dir(
        tmp_path / security_code,
        security_code,
        include_official=True,
        explicit_zero=True,
    )
    result = run_research_pack(security_code, run_dir, as_of_date="2026-03-31")
    source_facts = pd.read_parquet(
        Path(result["artifacts"]["output_dir"]) / "tables" / "source_facts.parquet"
    )
    official_zero = source_facts[
        (source_facts["field_key"] == "RESEARCH_EXPENSE")
        & (source_facts["source_name"] == "OFFICIAL_DISCLOSURE")
    ]
    assert len(official_zero) == 1
    assert official_zero.iloc[0]["source_status"] == "FACT_ZERO_EXPLICIT"
    assert float(official_zero.iloc[0]["normalized_value_num"]) == 0.0
