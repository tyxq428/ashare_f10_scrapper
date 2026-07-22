from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser_path = root / "src/ashare_f10/validation/documents/pdf_parser.py"
text = parser_path.read_text(encoding="utf-8")

old = '''    text = re.sub(r"[/／]+", " ", text)
    text = re.sub(r"[—–-]+", " ", text)
    text = text.replace("%", " ")
    return _clean_row(text)
'''
new = '''    text = re.sub(r"[/／]+", " ", text)
    text = re.sub(r"[—–-]+", " ", text)
    text = text.replace("%", " ")
    text = re.sub(r"[一二三四五六七八九十百]+$", " ", text)
    return _clean_row(text)
'''
if old not in text and 're.sub(r"[一二三四五六七八九十百]+$"' not in text:
    raise SystemExit("label note suffix marker not found")
text = text.replace(old, new, 1)

old = '''                if events and events[0][0] <= float(page.height) * 0.45:
                    page_section, page_scope = events[0][1], events[0][2]

                unit = _unit_info(text)
'''
new = '''                if events and events[0][0] <= float(page.height) * 0.45:
                    page_section, page_scope = events[0][1], events[0][2]
                elif not events and any(
                    token in _compact(text)
                    for token in ("股东权益变动表", "所有者权益变动表", "财务报表附注")
                ):
                    page_section, page_scope = None, None
                    active_section, active_scope = None, None

                unit = _unit_info(text)
'''
if old not in text and 'for token in ("股东权益变动表"' not in text:
    raise SystemExit("statement boundary marker not found")
text = text.replace(old, new, 1)

old = '''                    if extracted:
                        score = 100 + (15 if extracted.scope == "consolidated" else 0)
                        candidates[(target.statement_type, target.field_key)].append((score, extracted))
                        continue

                    is_cashflow_supplement = (
'''
new = '''                    if extracted:
                        score = 100 + (15 if extracted.scope == "consolidated" else 0)
                        candidates[(target.statement_type, target.field_key)].append((score, extracted))
                        if document.source != "CNINFO":
                            continue

                    is_cashflow_supplement = (
'''
if old not in text and 'if document.source != "CNINFO":' not in text:
    raise SystemExit("CNINFO table/text preference marker not found")
text = text.replace(old, new, 1)

old = '''                    if extracted:
                        score = 60 + (15 if page_scope == "consolidated" else 0)
                        candidates[(target.statement_type, target.field_key)].append((score, extracted))
'''
new = '''                    if extracted:
                        base_score = 140 if document.source == "CNINFO" else 60
                        score = base_score + (15 if page_scope == "consolidated" else 0)
                        candidates[(target.statement_type, target.field_key)].append((score, extracted))
'''
if old not in text and 'base_score = 140 if document.source == "CNINFO" else 60' not in text:
    raise SystemExit("CNINFO text score marker not found")
text = text.replace(old, new, 1)
parser_path.write_text(text, encoding="utf-8")

runner_path = root / "src/ashare_f10/cross_validation/runner.py"
runner = runner_path.read_text(encoding="utf-8")
runner = runner.replace('PARSER_CACHE_VERSION = "1.5.0"', 'PARSER_CACHE_VERSION = "1.6.0"')
runner_path.write_text(runner, encoding="utf-8")

test_path = root / "tests/test_cninfo_row_alignment.py"
test_path.write_text(
    '''from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
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


def _fact(field_key: str, label: str, text: str):
    target = TargetField(
        field_key,
        label,
        "cash_flow" if "现金" in label else "income_statement",
        (label,),
        (field_key,),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    )
    return PdfStatementParser((target,))._extract_from_text(
        text,
        target,
        _document(),
        1,
        ("千元", 1000.0),
        "consolidated",
    )


def test_note_column_after_label_does_not_block_preceding_value() -> None:
    fact = _fact(
        "INVEST_PAY_CASH",
        "投资支付的现金",
        "(56)(d) (1,630,616) (129,979) – (3,000,000)\\n投资支付的现金 四\\n"
        "(56)(f) (28,251) (696,654) – –\\n取得子公司支付的现金净额 四",
    )
    assert fact is not None
    assert fact.value == 1_630_616_000


def test_nonbusiness_rows_use_preceding_values() -> None:
    income = _fact(
        "NONBUSINESS_INCOME",
        "营业外收入",
        "(52)(a) 386,539 311,972 – –\\n加：营业外收入 四\\n"
        "(52)(b) (232,129) (373,060) – –\\n减：营业外支出 四",
    )
    expense = _fact(
        "NONBUSINESS_EXPENSE",
        "营业外支出",
        "(52)(a) 386,539 311,972 – –\\n加：营业外收入 四\\n"
        "(52)(b) (232,129) (373,060) – –\\n减：营业外支出 四\\n"
        "14,917,877 13,607,261 2,485,980 5,042,321\\n三、利润总额",
    )
    assert income is not None and income.value == 386_539_000
    assert expense is not None and expense.value == 232_129_000
''',
    encoding="utf-8",
)
