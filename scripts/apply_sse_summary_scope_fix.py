from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"{label} marker not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


parser = ROOT / "src/ashare_f10/validation/documents/pdf_parser.py"
summary_helpers = '''

SUMMARY_DIRECT_ALIASES = {
    "总资产",
    "资产总计",
    "归属于上市公司股东的净资产",
    "归属于母公司股东的净资产",
    "经营活动产生的现金流量净额",
    "营业收入",
    "归属于上市公司股东的净利润",
    "归属于母公司股东的净利润",
    "归属于上市公司股东的扣除非经常性损益的净利润",
    "归属于母公司股东的扣除非经常性损益的净利润",
    "基本每股收益",
    "稀释每股收益",
    "加权平均净资产收益率",
    "研发投入占营业收入的比例",
}


def _is_summary_direct_target(target: TargetField) -> bool:
    return any(_compact(alias) in {_compact(item) for item in SUMMARY_DIRECT_ALIASES} for alias in target.aliases)


def financial_scope_from_texts(texts: Iterable[str]) -> str:
    has_summary = False
    for text in texts:
        compact = _compact(text)
        if _heading_events(None, text):
            return "FULL_STATEMENTS"
        if "主要财务数据" in compact:
            has_summary = True
    return "SUMMARY_ONLY" if has_summary else "UNRESOLVED"


def classify_pdf_financial_scope(pdf_path: Path | str) -> str:
    texts: list[str] = []
    with pdfplumber.open(Path(pdf_path)) as pdf:
        for page in pdf.pages:
            texts.append(
                page.extract_text(x_tolerance=1.5, y_tolerance=3, layout=True)
                or page.extract_text()
                or ""
            )
    return financial_scope_from_texts(texts)
'''
replace_once(
    parser,
    "\n\ndef _normalized_label(value: Any) -> str:\n",
    summary_helpers + "\n\ndef _normalized_label(value: Any) -> str:\n",
    "add old-quarter summary scope helpers",
)
replace_once(
    parser,
    '''                ("balance_sheet", "TOTAL_LIAB_EQUITY"): ("负债及股东权益总计",),
''',
    '''                ("balance_sheet", "TOTAL_LIAB_EQUITY"): ("负债及股东权益总计",),
                ("balance_sheet", "TOTAL_ASSETS"): ("总资产",),
''',
    "add total-assets summary alias",
)
replace_once(
    parser,
    '''                compact_text = _compact(text)
                has_summary_alias = "扣除非经常性损益" in compact_text or any(
''',
    '''                compact_text = _compact(text)
                is_key_financial_summary_page = (
                    "主要财务数据" in compact_text and page_number <= 5
                )
                has_summary_alias = "扣除非经常性损益" in compact_text or any(
''',
    "detect key financial summary pages",
)
replace_once(
    parser,
    '''                    allowed_text = (
                        target.statement_type == "summary"
                        or (page_section == target.statement_type and page_scope != "parent")
                        or is_cashflow_supplement
                    )
''',
    '''                    is_summary_direct = (
                        is_key_financial_summary_page and _is_summary_direct_target(target)
                    )
                    allowed_text = (
                        target.statement_type == "summary"
                        or (page_section == target.statement_type and page_scope != "parent")
                        or is_cashflow_supplement
                        or is_summary_direct
                    )
''',
    "allow safe old-quarter summary targets",
)
replace_once(
    parser,
    '''                        page_scope or "consolidated",
                    )
''',
    '''                        page_scope or "consolidated",
                        max_width=6 if is_summary_direct else 3,
                    )
''',
    "expand summary text window only on summary pages",
)
replace_once(
    parser,
    '''        unit: tuple[str, float],
        scope: str,
    ) -> OfficialFact | None:
''',
    '''        unit: tuple[str, float],
        scope: str,
        max_width: int = 3,
    ) -> OfficialFact | None:
''',
    "parameterize text window width",
)
replace_once(
    parser,
    '''        for start in range(len(lines)):
            for width in (1, 2, 3):
''',
    '''        for start in range(len(lines)):
            for width in range(1, max_width + 1):
''',
    "use parameterized text windows",
)
replace_once(
    parser,
    '''                    width_bonus = {1: 30, 2: 20, 3: 10}[width]
''',
    '''                    width_bonus = max(0, 40 - 10 * width)
''',
    "score extended summary windows",
)

models = ROOT / "src/ashare_f10/cross_validation/models.py"
replace_once(
    models,
    '    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",\n',
    '    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",\n'
    '    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",\n'
    '    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",\n',
    "add summary-only and pending-report statuses",
)

lifecycle = ROOT / "src/ashare_f10/cross_validation/lifecycle.py"
replace_once(
    lifecycle,
    '''    zero_extraction = set(source_status.get("discovered_but_zero_extraction_dates") or [])
    post_listing_missing = set(source_status.get("post_listing_missing_report_dates") or [])
''',
    '''    zero_extraction = set(source_status.get("discovered_but_zero_extraction_dates") or [])
    summary_only = set(source_status.get("summary_only_report_dates") or [])
    post_listing_missing = set(source_status.get("post_listing_missing_report_dates") or [])
    latest_available = max(source_status.get("available_report_dates") or [""])
''',
    "read summary and pending lifecycle dates",
)
replace_once(
    lifecycle,
    '''    zero_mask = date_values.isin(zero_extraction) & result["status"].isin(
''',
    '''    summary_mask = date_values.isin(summary_only) & result["status"].isin(
        ["MISSING_OFFICIAL", "OFFICIAL_PERIOD_NOT_LOADED"]
    )
    result.loc[summary_mask, "status"] = "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP"
    result.loc[summary_mask, "verification_grade"] = "N/A"
    result.loc[summary_mask, "notes"] = (
        "官方旧版季度报告仅披露主要财务数据摘要，不包含完整三张报表；"
        "摘要未直接披露的项目不参与一致性判断"
    )

    pending_mask = (
        (date_values > latest_available)
        & result["status"].eq("OFFICIAL_PERIOD_NOT_LOADED")
    )
    result.loc[pending_mask, "status"] = "OFFICIAL_REPORT_NOT_YET_DISCLOSED"
    result.loc[pending_mask, "verification_grade"] = "N/A"
    result.loc[pending_mask, "notes"] = "该报告期晚于最新已披露官方报告期，报告尚未公开，不参与一致性判断"

    zero_mask = date_values.isin(zero_extraction) & result["status"].isin(
''',
    "classify summary-only and not-yet-disclosed records",
)
replace_once(
    lifecycle,
    '''    requested = lifecycle.get("requested_report_dates") or source_status.get("requested_report_dates") or []
''',
    '''    requested = list(
        lifecycle.get("requested_report_dates") or source_status.get("requested_report_dates") or []
    )
    requested.extend(source_status.get("not_yet_disclosed_report_dates") or [])
    requested = sorted(set(requested))
''',
    "include pending report periods in lifecycle table",
)
replace_once(
    lifecycle,
    '''    zero_extraction = set(source_status.get("discovered_but_zero_extraction_dates") or [])
    post_missing = set(source_status.get("post_listing_missing_report_dates") or [])
''',
    '''    zero_extraction = set(source_status.get("discovered_but_zero_extraction_dates") or [])
    summary_only = set(source_status.get("summary_only_report_dates") or [])
    pending = set(source_status.get("not_yet_disclosed_report_dates") or [])
    post_missing = set(source_status.get("post_listing_missing_report_dates") or [])
''',
    "read lifecycle display classifications",
)
replace_once(
    lifecycle,
    '''        else:
            period_class = "POST_LISTING_PERIODIC_EXPECTED"
            coverage_status = "OFFICIAL_DOCUMENT_EXTRACTION_FAILED" if report_date in zero_extraction else (
''',
    '''        elif report_date in pending:
            period_class = "POST_LISTING_PERIOD_NOT_YET_DISCLOSED"
            coverage_status = "OFFICIAL_REPORT_NOT_YET_DISCLOSED"
        else:
            period_class = "POST_LISTING_PERIODIC_EXPECTED"
            coverage_status = "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP" if report_date in summary_only else (
                "OFFICIAL_DOCUMENT_EXTRACTION_FAILED" if report_date in zero_extraction else (
''',
    "display summary-only and pending periods",
)
replace_once(
    lifecycle,
    '''                    "AVAILABLE" if report_date in available else "UNRESOLVED"
                )
            )
''',
    '''                    "AVAILABLE" if report_date in available else "UNRESOLVED"
                )
            )
            )
''',
    "close nested lifecycle coverage expression",
)

runner = ROOT / "src/ashare_f10/cross_validation/runner.py"
replace_once(
    runner,
    '''from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
''',
    '''from ashare_f10.validation.documents.pdf_parser import (
    PdfStatementParser,
    classify_pdf_financial_scope,
)
''',
    "import PDF financial scope classifier",
)
replace_once(
    runner,
    '''        extraction_by_report_date: dict[str, int] = {}
        parser_cache_hits = 0
''',
    '''        extraction_by_report_date: dict[str, int] = {}
        document_scope_by_report_date: dict[str, str] = {}
        parser_cache_hits = 0
''',
    "track financial document scope",
)
replace_once(
    runner,
    '''                facts = parser.extract(path, document)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
''',
    '''                facts = parser.extract(path, document)
                document_scope_by_report_date[document.report_date] = classify_pdf_financial_scope(path)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
''',
    "classify downloaded report financial scope",
)
replace_once(
    runner,
    '''        zero_extraction_dates = sorted(
            report_date for report_date, count in extraction_by_report_date.items() if count == 0
        )
''',
    '''        summary_only_dates = sorted(
            report_date
            for report_date, scope in document_scope_by_report_date.items()
            if scope == "SUMMARY_ONLY"
        )
        zero_extraction_dates = sorted(
            report_date
            for report_date, count in extraction_by_report_date.items()
            if count == 0 and report_date not in summary_only_dates
        )
''',
    "separate summary-only from true extraction failures",
)
replace_once(
    runner,
    '''            "discovered_but_zero_extraction_dates": zero_extraction_dates,
''',
    '''            "discovered_but_zero_extraction_dates": zero_extraction_dates,
            "summary_only_report_dates": summary_only_dates,
            "document_scope_by_report_date": document_scope_by_report_date,
''',
    "write document scope status",
)
replace_once(
    runner,
    '''        comparison = apply_lifecycle_statuses(comparison, source_status)
        source_unavailable = source_status.get("source") == "UNAVAILABLE"
''',
    '''        comparison = apply_lifecycle_statuses(comparison, source_status)
        source_status["not_yet_disclosed_report_dates"] = sorted(
            {
                str(value)[:10]
                for value in comparison.loc[
                    comparison["status"] == "OFFICIAL_REPORT_NOT_YET_DISCLOSED",
                    "report_date",
                ]
                if value not in (None, "") and not pd.isna(value)
            }
        )
        source_unavailable = source_status.get("source") == "UNAVAILABLE"
''',
    "persist not-yet-disclosed dates",
)
replace_once(
    runner,
    '''                    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
                ]
''',
    '''                    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
                    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",
                    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",
                ]
''',
    "include summary and pending coverage gaps in acceptance",
)

comparator = ROOT / "src/ashare_f10/cross_validation/comparator.py"
replace_once(
    comparator,
    '                    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",\n',
    '                    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",\n'
    '                    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",\n'
    '                    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",\n',
    "exclude summary and pending report gaps from comparable count",
)
replace_once(
    comparator,
    '''                        else:
                            status, grade = "MISMATCH", "E"
''',
    '''                        else:
                            status, grade = "MISMATCH", "E"
                            if east_num == 0 and official_num != 0:
                                notes = (
                                    f"{notes}；东方财富明确返回0，但免费官方正式披露为非零；"
                                    "保留为可追溯来源冲突，不自动覆盖或隐藏"
                                )
''',
    "explain explicit-zero source conflicts",
)

exporter = ROOT / "src/ashare_f10/cross_validation/exporter.py"
replace_once(
    exporter,
    '''                        "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
                    ]
''',
    '''                        "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
                        "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",
                        "OFFICIAL_REPORT_NOT_YET_DISCLOSED",
                    ]
''',
    "export summary and pending report gaps",
)

index = ROOT / "src/ashare_f10/web/index.html"
replace_once(
    index,
    '<option value="OFFICIAL_DOCUMENT_EXTRACTION_FAILED">官方文档已找到但解析失败（OFFICIAL_DOCUMENT_EXTRACTION_FAILED）</option>',
    '<option value="OFFICIAL_DOCUMENT_EXTRACTION_FAILED">官方文档已找到但解析失败（OFFICIAL_DOCUMENT_EXTRACTION_FAILED）</option>'
    '<option value="OFFICIAL_REPORT_SUMMARY_SCOPE_GAP">旧版报告仅披露摘要（OFFICIAL_REPORT_SUMMARY_SCOPE_GAP）</option>'
    '<option value="OFFICIAL_REPORT_NOT_YET_DISCLOSED">官方报告尚未披露（OFFICIAL_REPORT_NOT_YET_DISCLOSED）</option>',
    "add summary and pending statuses to Web filter",
)

# Regression tests.
test_path = ROOT / "tests/test_sse_summary_scope.py"
if not test_path.exists():
    test_path.write_text(
        '''from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import financial_scope_from_texts


def test_old_quarter_report_is_classified_as_summary_only() -> None:
    assert financial_scope_from_texts([
        "二、公司主要财务数据和股东变化\\n2.1 主要财务数据\\n总资产 3,145,094,219.81"
    ]) == "SUMMARY_ONLY"


def test_full_statement_heading_takes_priority() -> None:
    assert financial_scope_from_texts([
        "二、公司主要财务数据",
        "合并资产负债表\\n单位：元",
    ]) == "FULL_STATEMENTS"
''',
        encoding="utf-8",
    )

status_test = ROOT / "tests/test_security_lifecycle_statuses.py"
with status_test.open("a", encoding="utf-8") as handle:
    handle.write(
        '''


def test_pending_and_summary_only_statuses_are_not_generic_missing() -> None:
    comparison = pd.DataFrame(
        [
            {"report_date": "2021-03-31", "status": "MISSING_OFFICIAL", "verification_grade": "E", "notes": ""},
            {"report_date": "2026-06-30", "status": "OFFICIAL_PERIOD_NOT_LOADED", "verification_grade": "E", "notes": ""},
        ]
    )
    source_status = {
        "available_report_dates": ["2026-03-31"],
        "summary_only_report_dates": ["2021-03-31"],
    }
    result = apply_lifecycle_statuses(comparison, source_status)
    assert result["status"].tolist() == [
        "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",
        "OFFICIAL_REPORT_NOT_YET_DISCLOSED",
    ]
'''
    )

print("SSE summary-only and pending-period fixes materialized")
