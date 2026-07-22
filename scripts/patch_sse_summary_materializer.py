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
old_function = '''def _select_summary_amount(
    values: list[tuple[float, int, str]],
    target: TargetField,
    document: OfficialDocument,
    context: str,
    page_text: str = "",
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
        if not (abs(value[0]) < 100 and bool(re.fullmatch(r"[（(]\\s*\\d{1,2}\\s*[）)]", value[2].strip())))
    ]
    usable = usable or values
    if document.report_kind != "q3" or target.semantics == "point_in_time":
        return usable[0]
    compact_page = _compact(page_text)
    modern_q3_layout = bool(re.search(r"本报告期(?:比上年同期|同比)", compact_page))
    if not modern_q3_layout:
        # Pre-2021 SSE summary-only reports expose YTD, prior-year YTD and change.
        # Their first amount is already the cumulative value; the third is a rate.
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
new_function = '''def _select_summary_amount(
    values: list[tuple[float, int, str]],
    target: TargetField,
    document: OfficialDocument,
    context: str,
    page_text: str = "",
) -> tuple[float, int, str] | None:
    """Select the comparable amount from SSE key-financial-data summary rows.

    Legacy Q3 summaries expose ``YTD / prior YTD / change`` and therefore use the
    first amount. Modern Q3 summaries expose ``current quarter / change / YTD /
    change`` and therefore use the third numeric token. PDF text extraction can
    interleave column headings, so the decision is based on the row's value shape
    rather than fragile header word order. Point-in-time facts always use the first
    period-end amount.
    """

    del page_text  # Retained for backward-compatible callers and evidence tests.
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

    # Four numeric tokens unambiguously identify the modern Q3 layout:
    # current-quarter amount, current-quarter change, YTD amount, YTD change.
    if len(usable) >= 4:
        return usable[2]

    compact = _compact(context)
    if len(usable) == 3 and "不适用" in compact:
        # One modern current-quarter column can be unavailable.  When the marker
        # sits between the first and second numeric token, the second amount is YTD.
        first_pos = compact.find(_compact(usable[0][2]))
        second_pos = compact.find(_compact(usable[1][2]), max(first_pos + 1, 0))
        unavailable_pos = compact.find("不适用", max(first_pos + 1, 0))
        if first_pos >= 0 and second_pos > first_pos and first_pos < unavailable_pos < second_pos:
            return usable[1]

    # Legacy Q3: YTD, prior-year YTD, change.  Modern rows with both current-quarter
    # columns unavailable also leave the YTD amount as the first numeric token.
    return usable[0]
'''
replace_once(parser, old_function, new_function, "replace Q3 summary amount selector")

runner = ROOT / "src/ashare_f10/cross_validation/runner.py"
replace_once(
    runner,
    'PARSER_CACHE_VERSION = "1.9.0"\n',
    'PARSER_CACHE_VERSION = "1.10.0"\n',
    "invalidate pre-row-shape parse cache",
)

test_path = ROOT / "tests/test_sse_q3_summary_values.py"
text = test_path.read_text(encoding="utf-8")
extra = '''


def test_modern_q3_with_one_unavailable_change_column_uses_second_amount() -> None:
    context = "营业收入 671,661,479.01 不适用 1,884,150,580.19 23.87"
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        _target(),
        _document("q3"),
        context,
        page_text="交错列标题不影响基于行形状的选择",
    )
    assert selected is not None
    assert selected[0] == 1_884_150_580.19
'''
if "test_modern_q3_with_one_unavailable_change_column_uses_second_amount" not in text:
    text += extra
    test_path.write_text(text, encoding="utf-8")
