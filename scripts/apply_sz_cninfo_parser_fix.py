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

cninfo_path = root / "src/ashare_f10/validation/sources/cninfo.py"
cninfo = cninfo_path.read_text(encoding="utf-8")
cninfo = cninfo.replace(
    "from datetime import UTC, date, datetime\n",
    "from datetime import UTC, date, datetime\nfrom zoneinfo import ZoneInfo\n",
)
if "CNINFO_TIMEZONE = ZoneInfo" not in cninfo:
    cninfo = cninfo.replace(
        'CNINFO_STATIC_HOME = "https://static.cninfo.com.cn/"\n',
        'CNINFO_STATIC_HOME = "https://static.cninfo.com.cn/"\nCNINFO_TIMEZONE = ZoneInfo("Asia/Shanghai")\n',
    )
cninfo = cninfo.replace(
    "return datetime.fromtimestamp(number / 1000, tz=UTC).date().isoformat()",
    "return (\n"
    "                datetime.fromtimestamp(number / 1000, tz=UTC)\n"
    "                .astimezone(CNINFO_TIMEZONE)\n"
    "                .date()\n"
    "                .isoformat()\n"
    "            )",
)
cninfo_path.write_text(cninfo, encoding="utf-8")

parser_path = root / "src/ashare_f10/validation/documents/pdf_parser.py"
text = parser_path.read_text(encoding="utf-8")
text = text.replace(
    '_NUMBER_PATTERN = re.compile(r"(?:[-−]?\\(?\\d[\\d,， ]*(?:\\.\\d+)?\\)?|[-−]?\\(\\d+(?:\\.\\d+)?\\))")',
    '_NUMBER_PATTERN = re.compile(\n'
    '    r"(?:[-−]?\\(\\s*\\d+(?:[,，]\\d{3})*(?:\\.\\d+)?\\s*\\)|"\n'
    '    r"[-−]?\\d+(?:[,，]\\d{3})*(?:\\.\\d+)?)"\n'
    ')\n'
    '_NOTE_REFERENCE_PATTERN = re.compile(\n'
    '    r"[一二三四五六七八九十百]+(?:[（(]\\d+(?:[-—]\\d+)?[）)])+(?:[（(][A-Za-z][）)])?"\n'
    ')',
)

numeric_block = '''def _numeric_candidates(cells: Iterable[str]) -> list[tuple[float, int, str]]:
    values: list[tuple[float, int, str]] = []
    for cell in cells:
        clean = _clean_row(cell)
        if not clean:
            continue
        if _NUMBER_PATTERN.fullmatch(clean):
            direct = _parse_number(clean)
            if direct is not None:
                values.append((direct[0], direct[1], clean))
            continue
        for token in _NUMBER_PATTERN.findall(clean):
            parsed = _parse_number(token)
            if parsed is not None:
                values.append((parsed[0], parsed[1], token))
    return values


def _choose_amounts(
    values: list[tuple[float, int, str]],
) -> tuple[tuple[float, int, str], tuple[float, int, str] | None] | None:
    if not values:
        return None
    non_note = [
        value
        for value in values
        if not (
            abs(value[0]) < 100
            and re.fullmatch(r"[（(]\\s*\\d{1,2}\\s*[）)]", value[2].strip())
        )
    ]
    candidates = non_note or values
    plausible: list[tuple[float, int, str]] = []
    for value in candidates:
        number, _, raw = value
        if abs(number) >= 100 or "," in raw or "." in raw or "(" in raw or "（" in raw:
            plausible.append(value)
    selected = plausible or candidates
    if len(selected) >= 2:
        return selected[0], selected[1]
    return selected[0], None


def _label_context(value: Any) -> str:
    text = _clean_row(value)
    text = _NOTE_REFERENCE_PATTERN.sub(" ", text)
    text = _NUMBER_PATTERN.sub(" ", text)
    text = re.sub(r"(^|\\s)[一二三四五六七八九十百]+(?=\\s|$)", " ", text)
    text = re.sub(r"[/／]+", " ", text)
    return _clean_row(text)


def _explicit_unit_info(text: str) -> tuple[str, float] | None:
    compact = _compact(text)
    match = re.search(
        r"(?:单位[：:]?|金额单位(?:为|[：:]))(?:人民币)?(亿元|万元|千元|元)",
        compact,
    )
    if match is None:
        match = re.search(r"[（(](?:人民币)?(亿元|万元|千元|元)[）)]", compact)
    if match is None:
        return None
    unit = match.group(1)
    scale = {"元": 1.0, "千元": 1_000.0, "万元": 10_000.0, "亿元": 100_000_000.0}[unit]
    return unit, scale


def _unit_info(text: str) -> tuple[str, float]:
    return _explicit_unit_info(text) or ("元", 1.0)
'''
text = replace_between(text, "def _numeric_candidates(", "def _tolerance(", numeric_block)

heading_block = '''def _heading_context(line: str) -> tuple[str, str] | None:
    compact = _compact(line).replace("(", "（").replace(")", "）")
    compact = re.sub(r"^\\d+[、.．]", "", compact)
    match = re.search(
        r"(?P<scope>合并及公司|合并|母公司|公司)?"
        r"(?P<statement>资产负债表|利润表|现金流量表)(?:（续）)?$",
        compact,
    )
    if match is None:
        return None
    statement = {
        "资产负债表": "balance_sheet",
        "利润表": "income_statement",
        "现金流量表": "cash_flow",
    }[match.group("statement")]
    scope = "parent" if match.group("scope") in {"母公司", "公司"} else "consolidated"
    return statement, scope


def _heading_events(page: Any | None, text: str) -> list[tuple[float, str, str]]:
    lines = [_clean_row(line) for line in text.splitlines() if _clean_row(line)]
    events: list[tuple[float, str, str]] = []
    used: set[tuple[str, float]] = set()
    for line_index, line in enumerate(lines):
        context = _heading_context(line)
        if context is None:
            continue
        approximate_top = float(line_index)
        if page is not None:
            try:
                matches = page.search(re.escape(line), regex=True) or []
            except Exception:  # noqa: BLE001
                matches = []
            if matches:
                approximate_top = float(matches[0].get("top", approximate_top))
            else:
                approximate_top = (line_index / max(len(lines), 1)) * float(page.height)
        identity = (_compact(line), approximate_top)
        if identity in used:
            continue
        used.add(identity)
        events.append((approximate_top, context[0], context[1]))
    events.sort(key=lambda item: item[0])
    return events
'''
text = replace_between(text, "def _heading_events(", "def _section_from_text(", heading_block)

old_alias_line = "            aliases = target.aliases\n"
new_alias_block = '''            aliases = target.aliases
            special_aliases = {
                ("balance_sheet", "TOTAL_LIAB_EQUITY"): ("负债及股东权益总计",),
                ("income_statement", "FINANCE_EXPENSE"): ("财务（费用）/收入", "财务（费用）收入"),
                ("income_statement", "PARENT_NETPROFIT"): ("归属于母公司所有者的净利润",),
                ("cash_flow", "NETCASH_OPERATE"): (
                    "经营活动产生/（使用）的现金流量净额",
                    "经营活动产生（使用）的现金流量净额",
                ),
                ("cash_flow", "NETCASH_INVEST"): (
                    "投资活动（使用）/产生的现金流量净额",
                    "投资活动（使用）产生的现金流量净额",
                    "投资活动使用的现金流量净额",
                ),
                ("cash_flow", "NETCASH_FINANCE"): ("筹资活动使用的现金流量净额",),
                ("cash_flow", "CCE_ADD"): (
                    "现金及现金等价物净（减少）/增加额",
                    "现金及现金等价物净（减少）增加额",
                ),
                ("cash_flow", "BEGIN_CCE"): ("年初现金及现金等价物余额",),
                ("cash_flow", "END_CCE"): ("年末现金及现金等价物余额",),
            }
            if identity in special_aliases:
                aliases = tuple(dict.fromkeys((*special_aliases[identity], *aliases)))
'''
if old_alias_line not in text:
    raise SystemExit("target alias marker not found")
text = text.replace(old_alias_line, new_alias_block, 1)
text = text.replace(
    'explicit_unit = bool(re.search(r"单位[：:](?:亿元|万元|千元|元)", _compact(text)))',
    "explicit_unit = _explicit_unit_info(text) is not None",
)

extract_methods = '''    def _extract_from_table(
        self,
        table: list[list[Any]],
        target: TargetField,
        document: OfficialDocument,
        page_number: int,
        unit: tuple[str, float],
        scope: str,
    ) -> OfficialFact | None:
        for raw_row in table:
            cells = [_clean_row(cell) for cell in raw_row if cell not in (None, "")]
            if not cells:
                continue
            alias_index = -1
            alias = None
            for index, cell in enumerate(cells):
                alias = next((name for name in target.aliases if _label_matches(cell, name)), None)
                if alias:
                    alias_index = index
                    break
            if alias is None:
                continue
            amounts = _choose_amounts(_numeric_candidates(cells[alias_index + 1 :]))
            if not amounts:
                continue
            current, _previous = amounts
            joined = " ".join(cells)
            row_unit = _explicit_unit_info(joined) or unit
            return OfficialFact(
                security_code=document.security_code,
                report_date=document.report_date,
                statement_type=target.statement_type,
                scope=scope,
                field_key=target.field_key,
                field_name_report=alias,
                value=current[0] * row_unit[1],
                unit=row_unit[0],
                normalized_unit="元",
                source_document=document.title,
                source_url=document.url,
                source_page=page_number,
                source_row=joined,
                extraction_method="PDF_TABLE",
                precision_tolerance=_tolerance(row_unit[1], current[1]),
                confidence="high",
            )
        return None

    def _extract_from_text(
        self,
        text: str,
        target: TargetField,
        document: OfficialDocument,
        page_number: int,
        unit: tuple[str, float],
        scope: str,
    ) -> OfficialFact | None:
        lines = [_clean_row(line) for line in text.splitlines() if _clean_row(line)]
        for index in range(len(lines)):
            windows = (
                (index, index + 1),
                (max(0, index - 1), index + 1),
                (index, min(len(lines), index + 2)),
                (index, min(len(lines), index + 3)),
                (max(0, index - 1), min(len(lines), index + 2)),
            )
            seen_windows: set[tuple[int, int]] = set()
            for start, end in windows:
                if (start, end) in seen_windows:
                    continue
                seen_windows.add((start, end))
                context = " ".join(lines[start:end])
                label_context = _label_context(context)
                alias = next(
                    (name for name in target.aliases if _label_matches(label_context, name)),
                    None,
                )
                if not alias:
                    continue
                amounts = _choose_amounts(_numeric_candidates([context]))
                if not amounts:
                    continue
                current, _previous = amounts
                if not math.isfinite(current[0]):
                    continue
                row_unit = _explicit_unit_info(context) or unit
                return OfficialFact(
                    security_code=document.security_code,
                    report_date=document.report_date,
                    statement_type=target.statement_type,
                    scope=scope,
                    field_key=target.field_key,
                    field_name_report=alias,
                    value=current[0] * row_unit[1],
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
        return None
'''
text = replace_between(text, "    def _extract_from_table(\n", "", extract_methods) if False else text
# The table and text extraction methods are the final methods in the module.
method_start = text.find("    def _extract_from_table(\n")
if method_start < 0:
    raise SystemExit("extract method marker not found")
text = text[:method_start] + extract_methods.rstrip() + "\n"
parser_path.write_text(text, encoding="utf-8")

runner_path = root / "src/ashare_f10/cross_validation/runner.py"
runner = runner_path.read_text(encoding="utf-8")
runner = runner.replace('PARSER_CACHE_VERSION = "1.3.0"', 'PARSER_CACHE_VERSION = "1.4.0"')
runner_path.write_text(runner, encoding="utf-8")

test_path = root / "tests/test_cninfo_pdf_variants.py"
test_path.write_text(
    '''from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import (
    PdfStatementParser,
    _choose_amounts,
    _heading_events,
    _numeric_candidates,
    _unit_info,
)
from ashare_f10.validation.models import OfficialDocument, TargetField
from ashare_f10.validation.sources.cninfo import _date_text


def test_cninfo_timestamp_uses_china_calendar_date() -> None:
    assert _date_text(1774886400000) == "2026-03-31"


def test_cninfo_financial_heading_and_unit_variants() -> None:
    assert _heading_events(None, "2025年12月31日合并资产负债表（续）")[-1][1:] == (
        "balance_sheet",
        "consolidated",
    )
    assert _heading_events(None, "2025年度合并及公司利润表")[-1][1:] == (
        "income_statement",
        "consolidated",
    )
    assert _heading_events(None, "1、合并现金流量表")[-1][1:] == (
        "cash_flow",
        "consolidated",
    )
    assert _unit_info("除特别注明外，金额单位为人民币千元") == ("千元", 1000.0)
    assert _unit_info("归属于上市公司股东的净利润（千元）") == ("千元", 1000.0)


def test_numeric_candidates_do_not_concatenate_columns_or_use_note_number() -> None:
    values = _numeric_candidates(["四(42) 308,226,647 284,420,059"])
    current, previous = _choose_amounts(values) or (None, None)
    assert current is not None and current[0] == 308_226_647
    assert previous is not None and previous[0] == 284_420_059


def test_text_parser_supports_value_before_label_and_row_unit() -> None:
    target = TargetField(
        "OPERATE_INCOME",
        "营业收入",
        "income_statement",
        ("营业收入",),
        ("OPERATE_INCOME",),
        ("RPT_F10_FINANCE_GINCOME",),
    )
    document = OfficialDocument(
        "CNINFO",
        "002352",
        "2025年年度报告",
        "2026-03-31",
        "2025-12-31",
        "annual",
        "original",
        "https://example.invalid/annual.pdf",
    )
    fact = PdfStatementParser((target,))._extract_from_text(
        "四(42) 308,226,647 284,420,059\\n一、营业收入",
        target,
        document,
        159,
        ("千元", 1000.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 308_226_647_000


def test_text_parser_supports_split_summary_with_thousand_yuan_unit() -> None:
    target = TargetField(
        "DEDUCT_PARENT_NETPROFIT",
        "扣非归母净利润",
        "summary",
        ("归属于上市公司股东的扣除非经常性损益的净利润",),
        ("DEDUCT_PARENT_NETPROFIT",),
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
    text = "\\n".join(
        [
            "归属于上市公司股东的扣除非经常性损益",
            "2,317,341 1,973,620 17.42%",
            "的净利润（千元）",
        ]
    )
    fact = PdfStatementParser((target,))._extract_from_text(
        text,
        target,
        document,
        2,
        ("元", 1.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 2_317_341_000
''',
    encoding="utf-8",
)
