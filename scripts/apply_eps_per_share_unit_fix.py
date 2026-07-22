from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing replacement anchor: {label}")
    return text.replace(old, new, 1)


def patch_parser() -> None:
    path = Path("src/ashare_f10/validation/documents/pdf_parser.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''def _row_unit_info(text: str) -> tuple[str, float] | None:
    page_unit = _page_unit_info(text)
    if page_unit is not None:
        return page_unit
    compact = _compact(text)
    match = re.search(r"[（(](?:人民币)?(亿元|万元|千元|元)[）)]", compact)
    if match is None:
        return None
    unit = match.group(1)
    return unit, _unit_scale(unit)
''',
        '''def _row_unit_info(text: str) -> tuple[str, float] | None:
    compact = _compact(text)
    # Per-share rows override the page-level monetary presentation unit.  CNINFO
    # commonly presents the statement in 千元 while EPS remains 元/股.
    if re.search(r"[（(](?:人民币)?元[/／]股[）)]", compact):
        return "元/股", 1.0
    page_unit = _page_unit_info(text)
    if page_unit is not None:
        return page_unit
    match = re.search(r"[（(](?:人民币)?(亿元|万元|千元|元)[）)]", compact)
    if match is None:
        return None
    unit = match.group(1)
    return unit, _unit_scale(unit)
''',
        "row-specific per-share unit",
    )

    text = replace_once(
        text,
        '''def _tolerance(scale: float, decimals: int) -> float:
    return max(1.0, scale * 0.5 * (10 ** (-decimals)))
''',
        '''def _tolerance(scale: float, decimals: int, unit: str = "元") -> float:
    if unit == "元/股":
        return max(1e-9, 0.5 * (10 ** (-decimals)))
    return max(1.0, scale * 0.5 * (10 ** (-decimals)))
''',
        "unit-aware tolerance",
    )

    old_fact = '''                unit=row_unit[0],
                normalized_unit="元",
                source_document=document.title,
                source_url=document.url,
                source_page=page_number,
                source_row=joined,
                extraction_method="PDF_TABLE",
                precision_tolerance=_tolerance(row_unit[1], current[1]),
'''
    new_fact = '''                unit=row_unit[0],
                normalized_unit=row_unit[0] if row_unit[0] == "元/股" else "元",
                source_document=document.title,
                source_url=document.url,
                source_page=page_number,
                source_row=joined,
                extraction_method="PDF_TABLE",
                precision_tolerance=_tolerance(row_unit[1], current[1], row_unit[0]),
'''
    text = replace_once(text, old_fact, new_fact, "table fact unit")

    old_text_fact = '''            unit=row_unit[0],
            normalized_unit="元",
            source_document=document.title,
            source_url=document.url,
            source_page=page_number,
            source_row=context,
            extraction_method=("PDF_SUMMARY_TEXT_WINDOW" if summary_direct else "PDF_TEXT_WINDOW"),
            precision_tolerance=_tolerance(row_unit[1], current[1]),
'''
    new_text_fact = '''            unit=row_unit[0],
            normalized_unit=row_unit[0] if row_unit[0] == "元/股" else "元",
            source_document=document.title,
            source_url=document.url,
            source_page=page_number,
            source_row=context,
            extraction_method=("PDF_SUMMARY_TEXT_WINDOW" if summary_direct else "PDF_TEXT_WINDOW"),
            precision_tolerance=_tolerance(row_unit[1], current[1], row_unit[0]),
'''
    text = replace_once(text, old_text_fact, new_text_fact, "text fact unit")
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = Path("tests/test_cninfo_pdf_variants.py")
    text = path.read_text(encoding="utf-8")
    marker = "def test_eps_row_unit_overrides_thousand_yuan_page_unit"
    if marker in text:
        return
    text += '''


def test_eps_row_unit_overrides_thousand_yuan_page_unit() -> None:
    target = TargetField(
        "BASIC_EPS",
        "基本每股收益",
        "summary",
        ("基本每股收益",),
        ("BASIC_EPS",),
        ("RPT_F10_FINANCE_MAINFINADATA",),
    )
    document = OfficialDocument(
        "CNINFO",
        "002352",
        "2026年一季度报告",
        "2026-04-29",
        "2026-03-31",
        "q1",
        "original",
        "https://example.invalid/q1.pdf",
    )
    fact = PdfStatementParser((target,))._extract_from_text(
        "基本每股收益（元/股） 0.51 0.45 13.33%",
        target,
        document,
        2,
        ("千元", 1000.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 0.51
    assert fact.unit == "元/股"
    assert fact.normalized_unit == "元/股"
    assert fact.precision_tolerance == 0.005
'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_parser()
    patch_tests()


if __name__ == "__main__":
    main()
