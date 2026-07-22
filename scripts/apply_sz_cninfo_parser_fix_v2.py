from __future__ import annotations

from pathlib import Path


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"start marker not found: {start}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise SystemExit(f"end marker not found: {end}")
    return text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:]


root = Path(__file__).resolve().parents[1]
parser_path = root / "src/ashare_f10/validation/documents/pdf_parser.py"
text = parser_path.read_text(encoding="utf-8")

choose_block = '''def _choose_amounts(
    values: list[tuple[float, int, str]],
) -> tuple[tuple[float, int, str], tuple[float, int, str] | None] | None:
    if not values:
        return None

    def is_note_token(value: tuple[float, int, str]) -> bool:
        number, _decimals, raw = value
        return abs(number) < 100 and bool(
            re.fullmatch(r"[（(]\\s*\\d{1,2}\\s*[）)]", raw.strip())
        )

    non_note = [value for value in values if not is_note_token(value)]
    if not non_note:
        return None
    plausible: list[tuple[float, int, str]] = []
    for value in non_note:
        number, _, raw = value
        if abs(number) >= 100 or "," in raw or "." in raw or "(" in raw or "（" in raw:
            plausible.append(value)
    selected = plausible or non_note
    if len(selected) >= 2:
        return selected[0], selected[1]
    return selected[0], None
'''
text = replace_between(text, "def _choose_amounts(\n", "def _label_context(", choose_block)

label_block = '''def _label_context(value: Any) -> str:
    text = _clean_row(value)
    text = _NOTE_REFERENCE_PATTERN.sub(" ", text)
    text = _NUMBER_PATTERN.sub(" ", text)
    text = re.sub(r"(^|\\s)[一二三四五六七八九十百]+(?=\\s|$)", " ", text)
    text = re.sub(r"[/／]+", " ", text)
    text = re.sub(r"[—–-]+", " ", text)
    text = text.replace("%", " ")
    return _clean_row(text)
'''
text = replace_between(text, "def _label_context(", "def _explicit_unit_info(", label_block)

unit_block = '''ABSOLUTE_PRESENTATION_FIELDS = {
    "TREASURY_SHARES",
    "OPERATE_COST",
    "TOTAL_OPERATE_COST",
    "OPERATE_TAX_ADD",
    "SALE_EXPENSE",
    "MANAGE_EXPENSE",
    "RESEARCH_EXPENSE",
    "FINANCE_EXPENSE",
    "FE_INTEREST_EXPENSE",
    "INTEREST_EXPENSE",
    "INCOME_TAX",
    "NONBUSINESS_EXPENSE",
    "BUY_SERVICES",
    "CONSTRUCT_LONG_ASSET",
    "INVEST_PAY_CASH",
    "REPAY_DEBT_CASH",
    "ASSIGN_DIVIDEND_PORFIT",
    "DISTRIBUTE_DIVIDEND_CASH",
    "SUBSIDIARY_PAY_DIVIDEND",
}


def _unit_scale(unit: str) -> float:
    return {"元": 1.0, "千元": 1_000.0, "万元": 10_000.0, "亿元": 100_000_000.0}[unit]


def _page_unit_info(text: str) -> tuple[str, float] | None:
    compact = _compact(text)
    match = re.search(
        r"(?:单位[：:]?|金额单位(?:为|[：:]))(?:人民币)?(亿元|万元|千元|元)",
        compact,
    )
    if match is None:
        return None
    unit = match.group(1)
    return unit, _unit_scale(unit)


def _row_unit_info(text: str) -> tuple[str, float] | None:
    page_unit = _page_unit_info(text)
    if page_unit is not None:
        return page_unit
    compact = _compact(text)
    match = re.search(r"[（(](?:人民币)?(亿元|万元|千元|元)[）)]", compact)
    if match is None:
        return None
    unit = match.group(1)
    return unit, _unit_scale(unit)


def _explicit_unit_info(text: str) -> tuple[str, float] | None:
    return _row_unit_info(text)


def _unit_info(text: str) -> tuple[str, float]:
    return _page_unit_info(text) or ("元", 1.0)


def _canonical_value(field_key: str, value: float) -> float:
    if (
        field_key in ABSOLUTE_PRESENTATION_FIELDS
        or field_key.startswith("PAY_")
        or field_key.endswith("_OUTFLOW")
    ):
        return abs(value)
    return value
'''
text = replace_between(text, "def _explicit_unit_info(", "def _tolerance(", unit_block)
text = text.replace(
    "explicit_unit = _explicit_unit_info(text) is not None",
    "explicit_unit = _page_unit_info(text) is not None",
)
text = text.replace(
    "row_unit = _explicit_unit_info(joined) or unit",
    "row_unit = _row_unit_info(joined) or unit",
)
text = text.replace(
    "value=current[0] * row_unit[1],",
    "value=_canonical_value(target.field_key, current[0]) * row_unit[1],",
)

text_method = '''    def _extract_from_text(
        self,
        text: str,
        target: TargetField,
        document: OfficialDocument,
        page_number: int,
        unit: tuple[str, float],
        scope: str,
    ) -> OfficialFact | None:
        lines = [_clean_row(line) for line in text.splitlines() if _clean_row(line)]
        candidates: list[tuple[int, int, str, tuple[float, int, str], tuple[str, float], str]] = []
        seen: set[tuple[int, int, str, int]] = set()

        for start in range(len(lines)):
            for width in (1, 2, 3):
                end = min(len(lines), start + width)
                if end <= start:
                    continue
                context_lines = lines[start:end]
                context = " ".join(context_lines)
                label_context = _label_context(context)
                alias = next(
                    (
                        name
                        for name in sorted(target.aliases, key=len, reverse=True)
                        if _label_matches(label_context, name)
                    ),
                    None,
                )
                if alias is None:
                    continue

                label_lines = [
                    line_index
                    for line_index in range(start, end)
                    if _label_matches(_label_context(lines[line_index]), alias)
                ]
                for numeric_index in range(start, end):
                    amounts = _choose_amounts(_numeric_candidates([lines[numeric_index]]))
                    if not amounts:
                        continue
                    current, _previous = amounts
                    if not math.isfinite(current[0]):
                        continue

                    if label_lines:
                        first_label = min(label_lines)
                        last_label = max(label_lines)
                        if numeric_index in label_lines:
                            relation_score = 500
                        elif numeric_index < first_label:
                            relation_score = 460 - 10 * (first_label - numeric_index)
                        elif first_label < numeric_index < last_label:
                            relation_score = 450
                        else:
                            relation_score = 340 - 10 * (numeric_index - last_label)
                    else:
                        textual = [
                            line_index
                            for line_index in range(start, end)
                            if not _numeric_candidates([lines[line_index]])
                        ]
                        if textual and min(textual) < numeric_index < max(textual):
                            relation_score = 455
                        else:
                            relation_score = 380

                    normalized_context = _normalized_label(label_context)
                    normalized_alias = _normalized_label(alias)
                    exact_bonus = 40 if normalized_context == normalized_alias else 20
                    width_bonus = {1: 30, 2: 20, 3: 10}[width]
                    score = relation_score + exact_bonus + width_bonus
                    identity = (start, end, alias, numeric_index)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    row_unit = _row_unit_info(context) or unit
                    candidates.append((score, start, alias, current, row_unit, context))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1], -len(item[2])))
        _score, _start, alias, current, row_unit, context = candidates[0]
        return OfficialFact(
            security_code=document.security_code,
            report_date=document.report_date,
            statement_type=target.statement_type,
            scope=scope,
            field_key=target.field_key,
            field_name_report=alias,
            value=_canonical_value(target.field_key, current[0]) * row_unit[1],
            unit=row_unit[0],
            normalized_unit="元",
            source_document=document.title,
            source_url=document.url,
            source_page=page_number,
            source_row=context,
            extraction_method="PDF_TEXT_WINDOW",
            precision_tolerance=_tolerance(row_unit[1], current[1]),
            confidence="high" if target.statement_type != "summary" else "medium",
        )
'''
method_start = text.find("    def _extract_from_text(\n")
if method_start < 0:
    raise SystemExit("text extraction method marker not found")
text = text[:method_start] + text_method.rstrip() + "\n"
parser_path.write_text(text, encoding="utf-8")

comparator_path = root / "src/ashare_f10/cross_validation/comparator.py"
comparator = comparator_path.read_text(encoding="utf-8")
marker = '        same_period_key = [\n'
restriction = '''        if family == "RPT_F10_BUSINESS_RDEXPENSE" and field_key == "RESEARCH_EXPENSE":
            return None, None

'''
if restriction not in comparator:
    if marker not in comparator:
        raise SystemExit("same-period comparator marker not found")
    comparator = comparator.replace(marker, restriction + marker, 1)
old_units = '''                official_num, official_unit = _normalize_numeric(official_value_num, official_unit)
                if east_num is not None and official_num is not None:
                    if east_unit and official_unit and east_unit != official_unit:
'''
new_units = '''                official_num, official_unit = _normalize_numeric(official_value_num, official_unit)
                if east_num is not None and official_num is not None:
                    if east_unit.lower() in {"", "文本", "text", "none"}:
                        east_unit = official_unit
                    if official_unit.lower() in {"", "文本", "text", "none"}:
                        official_unit = east_unit
                    if east_unit and official_unit and east_unit != official_unit:
'''
if old_units not in comparator and 'east_unit.lower() in {"", "文本", "text", "none"}' not in comparator:
    raise SystemExit("numeric unit comparison marker not found")
comparator = comparator.replace(old_units, new_units, 1)
comparator_path.write_text(comparator, encoding="utf-8")

runner_path = root / "src/ashare_f10/cross_validation/runner.py"
runner = runner_path.read_text(encoding="utf-8")
runner = runner.replace('PARSER_CACHE_VERSION = "1.4.0"', 'PARSER_CACHE_VERSION = "1.5.0"')
runner_path.write_text(runner, encoding="utf-8")

test_path = root / "tests/test_cninfo_reconciliation_semantics.py"
test_path.write_text(
    '''from __future__ import annotations

from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.models import RegistryEntry
from ashare_f10.validation.documents.pdf_parser import (
    PdfStatementParser,
    _canonical_value,
    _page_unit_info,
    _row_unit_info,
)
from ashare_f10.validation.models import OfficialDocument, TargetField


def _document() -> OfficialDocument:
    return OfficialDocument(
        "CNINFO",
        "002352",
        "2025年年度报告",
        "2026-03-31",
        "2025-12-31",
        "annual",
        "original",
        "https://example.invalid/report.pdf",
    )


def test_page_unit_ignores_eps_row_unit_and_row_unit_keeps_it() -> None:
    text = "七、综合收益总额 2,291,538\\n基本每股收益（人民币元）0.51"
    assert _page_unit_info(text) is None
    assert _row_unit_info("基本每股收益（人民币元）0.51") == ("元", 1.0)


def test_annual_label_prefers_preceding_value_row() -> None:
    target = TargetField(
        "OPERATE_COST",
        "营业成本",
        "income_statement",
        ("营业成本",),
        ("OPERATE_COST",),
        ("RPT_F10_FINANCE_GINCOME",),
    )
    text = "(42) (267,178,276) (244,809,787) – –\\n减：营业成本 四\\n(43) (764,777) (714,325)"
    fact = PdfStatementParser((target,))._extract_from_text(
        text,
        target,
        _document(),
        159,
        ("千元", 1000.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 267_178_276_000


def test_income_and_cash_outflow_presentation_signs_are_canonicalized() -> None:
    assert _canonical_value("MANAGE_EXPENSE", -19_499_245) == 19_499_245
    assert _canonical_value("TOTAL_OPERATE_OUTFLOW", -395_565_795) == 395_565_795
    assert _canonical_value("TREASURY_SHARES", -1_542_636) == 1_542_636
    assert _canonical_value("FAIRVALUE_CHANGE_INCOME", -48_996) == -48_996


def test_business_rd_does_not_fallback_to_income_statement() -> None:
    official_index = {
        ("002352", "2025-12-31", "FY", "income_statement", "RESEARCH_EXPENSE"): [
            {
                "statement_type": "income_statement",
                "scope": "consolidated",
                "value_num": 2_169_906_000,
            }
        ]
    }
    eastmoney = {
        "security_code": "002352",
        "report_date": "2025-12-31",
        "period_type": "FY",
        "family": "RPT_F10_BUSINESS_RDEXPENSE",
        "field_key": "RESEARCH_EXPENSE",
    }
    entry = RegistryEntry(
        theme="经营业务与研发",
        family="RPT_F10_BUSINESS_RDEXPENSE",
        dataset="研发投入",
        field_key="RESEARCH_EXPENSE",
        field_name_cn="研发投入",
        validation_mode="OFFICIAL_DOCUMENT_EVENT",
        statement_type="business_review",
        scope="consolidated",
    )
    row, diagnostic = CrossSourceComparator._find_official(official_index, eastmoney, entry)
    assert row is None
    assert diagnostic is None
''',
    encoding="utf-8",
)
