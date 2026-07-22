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
replace_once(
    parser,
    '''    document: OfficialDocument,
    context: str,
) -> tuple[float, int, str] | None:
''',
    '''    document: OfficialDocument,
    context: str,
    page_text: str = "",
) -> tuple[float, int, str] | None:
''',
    "add page-layout input to summary selector",
)
replace_once(
    parser,
    '''    if document.report_kind != "q3" or target.semantics == "point_in_time":
        return usable[0]
    if len(usable) >= 3:
''',
    '''    if document.report_kind != "q3" or target.semantics == "point_in_time":
        return usable[0]
    compact_page = _compact(page_text)
    modern_q3_layout = bool(re.search(r"本报告期(?:比上年同期|同比)", compact_page))
    if not modern_q3_layout:
        # Pre-2021 SSE summary-only reports expose YTD, prior-year YTD and change.
        # Their first amount is already the cumulative value; the third is a rate.
        return usable[0]
    if len(usable) >= 3:
''',
    "distinguish legacy and modern Q3 summary layouts",
)
replace_once(
    parser,
    '''                            _select_summary_amount(numeric_values, target, document, numeric_source)
                            or current
''',
    '''                            _select_summary_amount(
                                numeric_values,
                                target,
                                document,
                                numeric_source,
                                page_text=text,
                            )
                            or current
''',
    "pass page text to summary selector",
)

runner = ROOT / "src/ashare_f10/cross_validation/runner.py"
replace_once(
    runner,
    'PARSER_CACHE_VERSION = "1.8.0"\n',
    'PARSER_CACHE_VERSION = "1.9.0"\n',
    "invalidate legacy-Q3 parse cache",
)

test_path = ROOT / "tests/test_sse_q3_summary_values.py"
text = test_path.read_text(encoding="utf-8")
text = text.replace(
    '''        _numeric_candidates([context]), _target(), _document("q3"), context
''',
    '''        _numeric_candidates([context]),
        _target(),
        _document("q3"),
        context,
        page_text="本报告期比上年同期增减 年初至报告期末",
''',
    1,
)
text = text.replace(
    '''        _numeric_candidates([context]), target, _document("q3"), context
''',
    '''        _numeric_candidates([context]),
        target,
        _document("q3"),
        context,
        page_text="本报告期比上年同期增减 年初至报告期末",
''',
    1,
)
legacy_test = '''


def test_legacy_q3_summary_uses_first_year_to_date_amount() -> None:
    context = "营业收入 1,060,887,323.03 950,580,713.27 11.60"
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        _target(),
        _document("q3"),
        context,
        page_text=(
            "本报告期末 上年度末 本报告期末比上年度末增减 "
            "年初至报告期末 上年初至上年报告期末 比上年同期增减"
        ),
    )
    assert selected is not None
    assert selected[0] == 1_060_887_323.03
'''
if "test_legacy_q3_summary_uses_first_year_to_date_amount" not in text:
    text += legacy_test

test_path.write_text(text, encoding="utf-8")
