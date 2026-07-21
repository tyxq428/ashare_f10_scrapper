from __future__ import annotations

import math
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pdfplumber

from ashare_f10.validation.models import OfficialDocument, OfficialFact, TargetField

DEFAULT_TARGETS: tuple[TargetField, ...] = (
    TargetField("MONETARYFUNDS", "货币资金", "balance_sheet", ("货币资金",), ("MONETARYFUNDS",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("ACCOUNTS_RECE", "应收账款", "balance_sheet", ("应收账款",), ("ACCOUNTS_RECE",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("INVENTORY", "存货", "balance_sheet", ("存货",), ("INVENTORY",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("CIP", "在建工程", "balance_sheet", ("在建工程",), ("CIP",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("FIXED_ASSET", "固定资产", "balance_sheet", ("固定资产",), ("FIXED_ASSET",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("GOODWILL", "商誉", "balance_sheet", ("商誉",), ("GOODWILL",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("TOTAL_ASSETS", "资产总计", "balance_sheet", ("资产总计",), ("TOTAL_ASSETS",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("TOTAL_LIABILITIES", "负债合计", "balance_sheet", ("负债合计",), ("TOTAL_LIABILITIES",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("TOTAL_EQUITY", "所有者权益合计", "balance_sheet", ("所有者权益合计", "股东权益合计"), ("TOTAL_EQUITY",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("TOTAL_LIAB_EQUITY", "负债和所有者权益总计", "balance_sheet", ("负债和所有者权益总计", "负债和股东权益总计", "负债和所有者权益（或股东权益）总计"), ("TOTAL_LIAB_EQUITY",), ("RPT_F10_FINANCE_GBALANCE",), "point_in_time"),
    TargetField("OPERATE_INCOME", "营业收入", "income_statement", ("营业收入",), ("OPERATE_INCOME", "TOTAL_OPERATE_INCOME"), ("RPT_F10_FINANCE_GINCOME",)),
    TargetField("OPERATE_COST", "营业成本", "income_statement", ("营业成本",), ("OPERATE_COST",), ("RPT_F10_FINANCE_GINCOME",)),
    TargetField("RESEARCH_EXPENSE", "研发费用", "income_statement", ("研发费用",), ("RESEARCH_EXPENSE",), ("RPT_F10_FINANCE_GINCOME",)),
    TargetField("OPERATE_PROFIT", "营业利润", "income_statement", ("营业利润",), ("OPERATE_PROFIT",), ("RPT_F10_FINANCE_GINCOME",)),
    TargetField("NETPROFIT", "净利润", "income_statement", ("净利润",), ("NETPROFIT",), ("RPT_F10_FINANCE_GINCOME",)),
    TargetField("PARENT_NETPROFIT", "归属于母公司股东的净利润", "income_statement", ("归属于母公司股东的净利润", "归属于上市公司股东的净利润"), ("PARENT_NETPROFIT",), ("RPT_F10_FINANCE_GINCOME", "RPT_F10_FINANCE_MAINFINADATA")),
    TargetField("DEDUCT_PARENT_NETPROFIT", "扣非归母净利润", "summary", ("归属于上市公司股东的扣除非经常性损益的净利润", "归属于母公司股东的扣除非经常性损益的净利润", "扣除非经常性损益后的净利润"), ("DEDUCT_PARENT_NETPROFIT", "KCFJCXSYJLR", "DEDU_PARENT_PROFIT"), ("RPT_F10_FINANCE_MAINFINADATA", "RPT_F10_QTR_MAINFINADATA")),
    TargetField("NETCASH_OPERATE", "经营活动产生的现金流量净额", "cash_flow", ("经营活动产生的现金流量净额",), ("NETCASH_OPERATE",), ("RPT_F10_FINANCE_GCASHFLOW",)),
    TargetField("NETCASH_INVEST", "投资活动产生的现金流量净额", "cash_flow", ("投资活动产生的现金流量净额",), ("NETCASH_INVEST",), ("RPT_F10_FINANCE_GCASHFLOW",)),
    TargetField("NETCASH_FINANCE", "筹资活动产生的现金流量净额", "cash_flow", ("筹资活动产生的现金流量净额",), ("NETCASH_FINANCE",), ("RPT_F10_FINANCE_GCASHFLOW",)),
    TargetField("RATE_CHANGE_EFFECT", "汇率变动对现金及现金等价物的影响", "cash_flow", ("汇率变动对现金及现金等价物的影响",), ("RATE_CHANGE_EFFECT",), ("RPT_F10_FINANCE_GCASHFLOW",)),
    TargetField("CCE_ADD", "现金及现金等价物净增加额", "cash_flow", ("现金及现金等价物净增加额",), ("CCE_ADD",), ("RPT_F10_FINANCE_GCASHFLOW",)),
    TargetField("BEGIN_CCE", "期初现金及现金等价物余额", "cash_flow", ("期初现金及现金等价物余额",), ("BEGIN_CCE",), ("RPT_F10_FINANCE_GCASHFLOW",)),
    TargetField("END_CCE", "期末现金及现金等价物余额", "cash_flow", ("期末现金及现金等价物余额",), ("END_CCE",), ("RPT_F10_FINANCE_GCASHFLOW",)),
)

_SECTION_HEADINGS = {
    "balance_sheet": ("合并资产负债表", "资产负债表"),
    "income_statement": ("合并利润表", "利润表"),
    "cash_flow": ("合并现金流量表", "现金流量表"),
}
_PARENT_HEADINGS = ("母公司资产负债表", "母公司利润表", "母公司现金流量表")
_NUMBER_PATTERN = re.compile(r"(?:[-−]?\(?\d[\d,， ]*(?:\.\d+)?\)?|[-−]?\(\d+(?:\.\d+)?\))")


def _compact(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ").replace("，", ",")
    return re.sub(r"\s+", "", text)


def _clean_row(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()


def _parse_number(text: str) -> tuple[float, int] | None:
    raw = text.strip().replace("，", ",").replace("−", "-").replace(" ", "")
    if raw in {"", "-", "—", "--", "不适用"}:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()")
    raw = re.sub(r"[^0-9.\-]", "", raw)
    if raw in {"", "-", "."}:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if negative:
        value = -abs(value)
    decimals = len(raw.rsplit(".", 1)[1]) if "." in raw else 0
    return value, decimals


def _numeric_candidates(cells: Iterable[str]) -> list[tuple[float, int, str]]:
    values: list[tuple[float, int, str]] = []
    for cell in cells:
        clean = _clean_row(cell)
        if not clean:
            continue
        direct = _parse_number(clean)
        if direct is not None:
            values.append((direct[0], direct[1], clean))
            continue
        for token in _NUMBER_PATTERN.findall(clean):
            parsed = _parse_number(token)
            if parsed is not None:
                values.append((parsed[0], parsed[1], token))
    return values


def _choose_amounts(values: list[tuple[float, int, str]]) -> tuple[tuple[float, int, str], tuple[float, int, str] | None] | None:
    if not values:
        return None
    plausible: list[tuple[float, int, str]] = []
    for value in values:
        number, _, raw = value
        if abs(number) >= 100 or "," in raw or "." in raw or "(" in raw:
            plausible.append(value)
    selected = plausible or values
    if len(selected) >= 2:
        return selected[0], selected[1]
    return selected[0], None


def _unit_info(text: str) -> tuple[str, float]:
    compact = _compact(text)
    if "单位：亿元" in compact or "单位:亿元" in compact:
        return "亿元", 100_000_000.0
    if "单位：万元" in compact or "单位:万元" in compact:
        return "万元", 10_000.0
    if "单位：千元" in compact or "单位:千元" in compact:
        return "千元", 1_000.0
    return "元", 1.0


def _tolerance(scale: float, decimals: int) -> float:
    return max(1.0, scale * 0.5 * (10 ** (-decimals)))


def _section_from_text(text: str) -> tuple[str | None, str | None]:
    compact = _compact(text)
    for parent in _PARENT_HEADINGS:
        if parent in compact:
            for section, headings in _SECTION_HEADINGS.items():
                if any(heading in parent for heading in headings):
                    return section, "parent"
    for section, headings in _SECTION_HEADINGS.items():
        if any(heading in compact for heading in headings):
            return section, "consolidated"
    return None, None


class PdfStatementParser:
    def __init__(self, targets: Iterable[TargetField] = DEFAULT_TARGETS) -> None:
        self.targets = tuple(targets)

    def extract(self, pdf_path: Path | str, document: OfficialDocument) -> list[OfficialFact]:
        pdf_path = Path(pdf_path)
        candidates: dict[str, list[tuple[int, OfficialFact]]] = {target.field_key: [] for target in self.targets}
        active_section: str | None = None
        active_scope: str | None = None
        active_until = 0
        previous_unit = ("元", 1.0)

        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=1.5, y_tolerance=3, layout=True) or page.extract_text() or ""
                section, scope = _section_from_text(text)
                if section:
                    active_section = section
                    active_scope = scope
                    active_until = page_number + 5
                elif page_number > active_until:
                    active_section = None
                    active_scope = None

                unit = _unit_info(text)
                if unit[1] == 1.0 and previous_unit[1] != 1.0 and active_section:
                    unit = previous_unit
                else:
                    previous_unit = unit

                tables: list[list[list[Any]]] = []
                if active_section is not None and active_scope != "parent":
                    try:
                        tables = page.extract_tables() or []
                    except Exception:  # noqa: BLE001
                        tables = []

                for target in self.targets:
                    allowed = target.statement_type == "summary" or (
                        active_section == target.statement_type and active_scope != "parent"
                    )
                    if not allowed:
                        continue
                    extracted = self._extract_from_tables(tables, target, document, page_number, unit, active_scope or "consolidated")
                    if extracted:
                        candidates[target.field_key].append((100 + (15 if active_scope == "consolidated" else 0), extracted))
                        continue
                    extracted = self._extract_from_text(text, target, document, page_number, unit, active_scope or "consolidated")
                    if extracted:
                        candidates[target.field_key].append((60 + (15 if active_scope == "consolidated" else 0), extracted))

        facts: list[OfficialFact] = []
        for target in self.targets:
            found = candidates[target.field_key]
            if not found:
                continue
            found.sort(key=lambda item: (-item[0], item[1].source_page))
            facts.append(found[0][1])
        return facts

    def _extract_from_tables(self, tables: list[list[list[Any]]], target: TargetField, document: OfficialDocument, page_number: int, unit: tuple[str, float], scope: str) -> OfficialFact | None:
        for table in tables:
            for raw_row in table:
                cells = [_clean_row(cell) for cell in raw_row if cell not in (None, "")]
                if not cells:
                    continue
                joined = " ".join(cells)
                alias = next((name for name in target.aliases if _compact(name) in _compact(joined)), None)
                if not alias:
                    continue
                alias_index = next((index for index, cell in enumerate(cells) if _compact(alias) in _compact(cell)), 0)
                amounts = _choose_amounts(_numeric_candidates(cells[alias_index + 1 :]))
                if not amounts:
                    continue
                current, _previous = amounts
                return OfficialFact(document.security_code, document.report_date, target.statement_type, scope, target.field_key, alias, current[0] * unit[1], unit[0], "元", document.title, document.url, page_number, joined, "PDF_TABLE", _tolerance(unit[1], current[1]), "high")
        return None

    def _extract_from_text(self, text: str, target: TargetField, document: OfficialDocument, page_number: int, unit: tuple[str, float], scope: str) -> OfficialFact | None:
        lines = [_clean_row(line) for line in text.splitlines() if _clean_row(line)]
        for index, line in enumerate(lines):
            alias = next((name for name in target.aliases if _compact(name) in _compact(line)), None)
            if not alias:
                continue
            context = line
            if not _NUMBER_PATTERN.search(context) and index + 1 < len(lines):
                context = f"{line} {lines[index + 1]}"
            compact_context = _compact(context)
            position = compact_context.find(_compact(alias))
            after_alias = compact_context[position + len(_compact(alias)) :] if position >= 0 else compact_context
            amounts = _choose_amounts(_numeric_candidates([after_alias]))
            if not amounts:
                continue
            current, _previous = amounts
            if not math.isfinite(current[0]):
                continue
            return OfficialFact(document.security_code, document.report_date, target.statement_type, scope, target.field_key, alias, current[0] * unit[1], unit[0], "元", document.title, document.url, page_number, context, "PDF_TEXT_LINE", _tolerance(unit[1], current[1]), "medium")
        return None
