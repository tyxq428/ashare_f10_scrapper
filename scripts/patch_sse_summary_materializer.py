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
summary_selector = '''


def _select_summary_amount(
    values: list[tuple[float, int, str]],
    target: TargetField,
    document: OfficialDocument,
    context: str,
) -> tuple[float, int, str] | None:
    """Select the comparable value from key-financial-data summary rows.

    SSE Q3 reports place four logical columns after the item label:
    current quarter, current-quarter change, year-to-date, year-to-date change.
    Flow and per-share facts used by cumulative statement endpoints must therefore
    use the third numeric value when it exists. Point-in-time rows continue to use
    the first value. If the two current-quarter columns are explicitly unavailable,
    the first numeric value is already the year-to-date amount.
    """

    if not values:
        return None
    usable = [
        value
        for value in values
        if not (
            abs(value[0]) < 100
            and bool(re.fullmatch(r"[（(]\\s*\\d{1,2}\\s*[）)]", value[2].strip()))
        )
    ]
    usable = usable or values
    if document.report_kind != "q3" or target.semantics == "point_in_time":
        return usable[0]
    if len(usable) >= 3:
        return usable[2]
    compact = _compact(context)
    first_token = _compact(usable[0][2])
    first_position = compact.find(first_token)
    prefix = compact[:first_position] if first_position >= 0 else ""
    if prefix.count("不适用") >= 2:
        return usable[0]
    return usable[-1]
'''
replace_once(
    parser,
    "\n\ndef financial_scope_from_texts(texts: Iterable[str]) -> str:\n",
    summary_selector + "\n\ndef financial_scope_from_texts(texts: Iterable[str]) -> str:\n",
    "add Q3 summary value selector",
)
replace_once(
    parser,
    '''                        max_width=6 if is_summary_direct else 3,
                    )
''',
    '''                        max_width=6 if is_summary_direct else 3,
                        summary_direct=is_summary_direct,
                    )
''',
    "pass summary-direct extraction mode",
)
replace_once(
    parser,
    '''        scope: str,
        max_width: int = 3,
    ) -> OfficialFact | None:
''',
    '''        scope: str,
        max_width: int = 3,
        summary_direct: bool = False,
    ) -> OfficialFact | None:
''',
    "add summary-direct extractor parameter",
)
replace_once(
    parser,
    '''                    amounts = _choose_amounts(_numeric_candidates([numeric_source]))
                    if not amounts:
                        continue
                    current, _previous = amounts
''',
    '''                    numeric_values = _numeric_candidates([numeric_source])
                    amounts = _choose_amounts(numeric_values)
                    if not amounts:
                        continue
                    current, _previous = amounts
                    if summary_direct:
                        current = (
                            _select_summary_amount(numeric_values, target, document, numeric_source)
                            or current
                        )
''',
    "select Q3 cumulative summary values",
)
replace_once(
    parser,
    '            extraction_method="PDF_TEXT_WINDOW",\n',
    '''            extraction_method=(
                "PDF_SUMMARY_TEXT_WINDOW" if summary_direct else "PDF_TEXT_WINDOW"
            ),
''',
    "mark summary extraction evidence",
)

runner = ROOT / "src/ashare_f10/cross_validation/runner.py"
replace_once(
    runner,
    'PARSER_CACHE_VERSION = "1.7.0"\n',
    'PARSER_CACHE_VERSION = "1.8.0"\n',
    "invalidate pre-Q3-selection parse cache",
)

test_path = ROOT / "tests/test_sse_q3_summary_values.py"
test_path.write_text(
    '''from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import (
    _numeric_candidates,
    _select_summary_amount,
)
from ashare_f10.validation.models import OfficialDocument, TargetField


def _document(report_kind: str) -> OfficialDocument:
    return OfficialDocument(
        source="SSE",
        security_code="688521",
        title="测试报告",
        publish_date="2023-10-28",
        report_date="2023-09-30" if report_kind == "q3" else "2023-03-31",
        report_kind=report_kind,
        version_label="original",
        url="https://example.invalid/report.pdf",
    )


def _target(semantics: str = "flow") -> TargetField:
    return TargetField(
        "OPERATE_INCOME",
        "营业收入",
        "income_statement",
        ("营业收入",),
        ("OPERATE_INCOME",),
        ("RPT_F10_FINANCE_GINCOME",),
        semantics,
    )


def test_q3_flow_summary_selects_year_to_date_value() -> None:
    context = "营业收入 671,661,479.01 3.66 1,884,150,580.19 23.87"
    selected = _select_summary_amount(
        _numeric_candidates([context]), _target(), _document("q3"), context
    )
    assert selected is not None
    assert selected[0] == 1_884_150_580.19


def test_q3_flow_summary_with_unavailable_quarter_columns_uses_first_number() -> None:
    context = "经营活动产生的现金流量净额 不适用 不适用 -306,604,109.75 18.20"
    target = TargetField(
        "NETCASH_OPERATE",
        "经营活动产生的现金流量净额",
        "cash_flow",
        ("经营活动产生的现金流量净额",),
        ("NETCASH_OPERATE",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
        "flow",
    )
    selected = _select_summary_amount(
        _numeric_candidates([context]), target, _document("q3"), context
    )
    assert selected is not None
    assert selected[0] == -306_604_109.75


def test_q3_point_in_time_summary_keeps_period_end_value() -> None:
    context = "总资产 4,457,634,651.81 3,858,272,515.48 15.53"
    selected = _select_summary_amount(
        _numeric_candidates([context]), _target("point_in_time"), _document("q3"), context
    )
    assert selected is not None
    assert selected[0] == 4_457_634_651.81


def test_q1_summary_keeps_first_value() -> None:
    context = "营业收入 580,891,974.65 -13.51"
    selected = _select_summary_amount(
        _numeric_candidates([context]), _target(), _document("q1"), context
    )
    assert selected is not None
    assert selected[0] == 580_891_974.65
''',
    encoding="utf-8",
)
