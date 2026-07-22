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


# Preserve signed SSE financial expenses while retaining the existing CNINFO
# presentation normalization that was verified on 002352.
parser = ROOT / "src/ashare_f10/validation/documents/pdf_parser.py"
replace_once(
    parser,
    '''def _canonical_value(field_key: str, value: float) -> float:
    if (
        field_key in ABSOLUTE_PRESENTATION_FIELDS
        or field_key.startswith("PAY_")
        or field_key.endswith("_OUTFLOW")
    ):
        return abs(value)
    return value
''',
    '''def _canonical_value(field_key: str, value: float, source: str = "") -> float:
    # SSE reports preserve the sign of financial expense and cash-flow supplement
    # finance expense.  CNINFO layouts sometimes present the same expense rows in
    # parentheses/negative form while Eastmoney stores their presentation magnitude;
    # retain the verified CNINFO behavior without changing SSE facts.
    if field_key == "FINANCE_EXPENSE" and source.upper() == "SSE":
        return value
    if (
        field_key in ABSOLUTE_PRESENTATION_FIELDS
        or field_key.startswith("PAY_")
        or field_key.endswith("_OUTFLOW")
    ):
        return abs(value)
    return value
''',
    "make financial-expense sign source-aware",
)
replace_once(
    parser,
    "value=_canonical_value(target.field_key, current[0]) * row_unit[1],",
    "value=_canonical_value(target.field_key, current[0], document.source) * row_unit[1],",
    "pass source into table canonicalization",
)
replace_once(
    parser,
    "value=_canonical_value(target.field_key, current[0]) * row_unit[1],",
    "value=_canonical_value(target.field_key, current[0], document.source) * row_unit[1],",
    "pass source into text canonicalization",
)

# Stop a blank row such as 资产处置收益 from borrowing the amount belonging to
# the following 营业利润 row in SSE PDFs.
alias_helper = '''

def _bounded_alias_value_segment(
    context: str,
    alias: str,
    all_aliases: Iterable[str],
) -> tuple[str, bool]:
    compact = _compact(context)
    target = _compact(alias)
    start = compact.find(target)
    if start < 0:
        return context, False
    value_start = start + len(target)
    value_end = len(compact)
    bounded = False
    for other in all_aliases:
        candidate = _compact(other)
        if not candidate or candidate == target:
            continue
        position = compact.find(candidate, value_start)
        if position >= 0 and position < value_end:
            value_end = position
            bounded = True
    return compact[value_start:value_end], bounded
'''
replace_once(
    parser,
    "\n\ndef _tolerance(scale: float, decimals: int) -> float:\n",
    alias_helper + "\n\ndef _tolerance(scale: float, decimals: int) -> float:\n",
    "add bounded alias value helper",
)
replace_once(
    parser,
    '''        self.targets = tuple(merged.values())
        self.summary_targets = tuple(target for target in self.targets if target.statement_type == "summary")
''',
    '''        self.targets = tuple(merged.values())
        self.summary_targets = tuple(target for target in self.targets if target.statement_type == "summary")
        self.statement_aliases = tuple(
            sorted(
                {
                    alias
                    for target in self.targets
                    if target.statement_type != "summary"
                    for alias in target.aliases
                },
                key=len,
                reverse=True,
            )
        )
''',
    "cache statement aliases for row boundary detection",
)
replace_once(
    parser,
    '''                for numeric_index in range(start, end):
                    amounts = _choose_amounts(_numeric_candidates([lines[numeric_index]]))
                    if not amounts:
                        continue
''',
    '''                value_segment, bounded_by_next_label = _bounded_alias_value_segment(
                    context,
                    alias,
                    self.statement_aliases,
                )
                for numeric_index in range(start, end):
                    numeric_source = value_segment if bounded_by_next_label else lines[numeric_index]
                    amounts = _choose_amounts(_numeric_candidates([numeric_source]))
                    if not amounts:
                        continue
''',
    "prevent adjacent statement row amount borrowing",
)

# Cash and cash-equivalent beginning/ending balances are point-in-time bridge
# values, not additive cumulative flows.  They must never be quarter-differenced.
derived = ROOT / "src/ashare_f10/cross_validation/derived.py"
replace_once(
    derived,
    "\n\ndef derive_independent_quarters(official: pd.DataFrame) -> pd.DataFrame:\n",
    '''

NON_ADDITIVE_CASH_FLOW_FIELDS = {
    "BEGIN_CCE",
    "END_CCE",
    "BEGIN_CASH",
    "END_CASH",
    "BEGIN_CASH_EQUIVALENTS",
    "END_CASH_EQUIVALENTS",
}


def derive_independent_quarters(official: pd.DataFrame) -> pd.DataFrame:
''',
    "declare non-additive cash-flow fields",
)
replace_once(
    derived,
    '''    flow = official[official["statement_type"].isin(["income_statement", "cash_flow"])].copy()
''',
    '''    flow = official[
        official["statement_type"].isin(["income_statement", "cash_flow"])
        & ~official["field_key"].isin(NON_ADDITIVE_CASH_FLOW_FIELDS)
    ].copy()
''',
    "exclude non-additive cash balances from quarter derivation",
)

# Any cached facts from the old parser are invalid after sign and row-boundary fixes.
runner = ROOT / "src/ashare_f10/cross_validation/runner.py"
replace_once(
    runner,
    'PARSER_CACHE_VERSION = "1.6.0"',
    'PARSER_CACHE_VERSION = "1.7.0"',
    "bump parser cache version",
)

# Regression tests.  The parser helpers are intentionally tested directly because
# they are deterministic and protect both SSE and CNINFO layouts.
test_path = ROOT / "tests/test_sse_full_history_false_conflicts.py"
if not test_path.exists():
    test_path.write_text(
        '''from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.derived import derive_independent_quarters
from ashare_f10.validation.documents.pdf_parser import (
    _bounded_alias_value_segment,
    _canonical_value,
)


def test_sse_finance_expense_preserves_reported_sign() -> None:
    assert _canonical_value("FINANCE_EXPENSE", -744126.44, "SSE") == -744126.44
    assert _canonical_value("FINANCE_EXPENSE", -744126.44, "CNINFO") == 744126.44


def test_blank_asset_disposal_row_cannot_borrow_operating_profit() -> None:
    context = (
        "资产处置收益（损失以‘－’号填列） "
        "三、营业利润（亏损以‘－’号填列） -42,379,273.29 -58,877,172.26"
    )
    segment, bounded = _bounded_alias_value_segment(
        context,
        "资产处置收益",
        ["资产处置收益", "营业利润"],
    )
    assert bounded is True
    assert "42,379,273.29" not in segment


def test_non_additive_cash_balances_are_not_quarter_differenced() -> None:
    columns = [
        "security_code", "report_date", "period_type", "statement_type", "scope",
        "field_key", "value_num", "value_text", "source_status", "source_row",
        "record_key",
    ]
    frame = pd.DataFrame(
        [
            ["688521", "2022-03-31", "Q1", "cash_flow", "consolidated", "BEGIN_CCE", 921.0, "921", "FACT_DIRECT", "Q1", "q1-begin"],
            ["688521", "2022-06-30", "H1", "cash_flow", "consolidated", "BEGIN_CCE", 921.0, "921", "FACT_DIRECT", "H1", "h1-begin"],
            ["688521", "2022-03-31", "Q1", "cash_flow", "consolidated", "NETCASH_OPERATE", 10.0, "10", "FACT_DIRECT", "Q1", "q1-flow"],
            ["688521", "2022-06-30", "H1", "cash_flow", "consolidated", "NETCASH_OPERATE", 25.0, "25", "FACT_DIRECT", "H1", "h1-flow"],
        ],
        columns=columns,
    )
    result = derive_independent_quarters(frame)
    assert set(result["field_key"]) == {"NETCASH_OPERATE"}
    assert result.iloc[0]["value_num"] == 15.0
''',
        encoding="utf-8",
    )

print("SSE false-conflict fixes materialized")
