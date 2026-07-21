from __future__ import annotations

import math
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pdfplumber

from ashare_f10.validation.models import OfficialDocument, OfficialFact, TargetField

DEFAULT_TARGETS: tuple[TargetField, ...] = (
    TargetField(
        "MONETARYFUNDS",
        "货币资金",
        "balance_sheet",
        ("货币资金",),
        ("MONETARYFUNDS",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "ACCOUNTS_RECE",
        "应收账款",
        "balance_sheet",
        ("应收账款",),
        ("ACCOUNTS_RECE",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "INVENTORY",
        "存货",
        "balance_sheet",
        ("存货",),
        ("INVENTORY",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "CIP",
        "在建工程",
        "balance_sheet",
        ("在建工程",),
        ("CIP",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "FIXED_ASSET",
        "固定资产",
        "balance_sheet",
        ("固定资产",),
        ("FIXED_ASSET",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "GOODWILL",
        "商誉",
        "balance_sheet",
        ("商誉",),
        ("GOODWILL",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "TOTAL_ASSETS",
        "资产总计",
        "balance_sheet",
        ("资产总计",),
        ("TOTAL_ASSETS",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "TOTAL_LIABILITIES",
        "负债合计",
        "balance_sheet",
        ("负债合计",),
        ("TOTAL_LIABILITIES",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "TOTAL_EQUITY",
        "所有者权益合计",
        "balance_sheet",
        ("所有者权益合计", "股东权益合计", "所有者权益（或股东权益）合计"),
        ("TOTAL_EQUITY",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "TOTAL_LIAB_EQUITY",
        "负债和所有者权益总计",
        "balance_sheet",
        ("负债和所有者权益总计", "负债和股东权益总计", "负债和所有者权益（或股东权益）总计"),
        ("TOTAL_LIAB_EQUITY",),
        ("RPT_F10_FINANCE_GBALANCE",),
        "point_in_time",
    ),
    TargetField(
        "OPERATE_INCOME",
        "营业收入",
        "income_statement",
        ("营业收入",),
        ("OPERATE_INCOME", "TOTAL_OPERATE_INCOME"),
        ("RPT_F10_FINANCE_GINCOME",),
    ),
    TargetField(
        "OPERATE_COST",
        "营业成本",
        "income_statement",
        ("营业成本",),
        ("OPERATE_COST",),
        ("RPT_F10_FINANCE_GINCOME",),
    ),
    TargetField(
        "RESEARCH_EXPENSE",
        "研发费用",
        "income_statement",
        ("研发费用",),
        ("RESEARCH_EXPENSE",),
        ("RPT_F10_FINANCE_GINCOME",),
    ),
    TargetField(
        "OPERATE_PROFIT",
        "营业利润",
        "income_statement",
        ("营业利润",),
        ("OPERATE_PROFIT",),
        ("RPT_F10_FINANCE_GINCOME",),
    ),
    TargetField(
        "NETPROFIT",
        "净利润",
        "income_statement",
        ("净利润",),
        ("NETPROFIT",),
        ("RPT_F10_FINANCE_GINCOME",),
    ),
    TargetField(
        "PARENT_NETPROFIT",
        "归属于母公司股东的净利润",
        "income_statement",
        ("归属于母公司股东的净利润", "归属于上市公司股东的净利润"),
        ("PARENT_NETPROFIT",),
        ("RPT_F10_FINANCE_GINCOME", "RPT_F10_FINANCE_MAINFINADATA"),
    ),
    TargetField(
        "DEDUCT_PARENT_NETPROFIT",
        "扣非归母净利润",
        "summary",
        (
            "归属于上市公司股东的扣除非经常性损益的净利润",
            "归属于母公司股东的扣除非经常性损益的净利润",
            "扣除非经常性损益后的净利润",
        ),
        ("DEDUCT_PARENT_NETPROFIT", "KCFJCXSYJLR", "DEDU_PARENT_PROFIT"),
        ("RPT_F10_FINANCE_MAINFINADATA", "RPT_F10_QTR_MAINFINADATA"),
    ),
    TargetField(
        "NETCASH_OPERATE",
        "经营活动产生的现金流量净额",
        "cash_flow",
        ("经营活动产生的现金流量净额",),
        ("NETCASH_OPERATE",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    ),
    TargetField(
        "NETCASH_INVEST",
        "投资活动产生的现金流量净额",
        "cash_flow",
        ("投资活动产生的现金流量净额",),
        ("NETCASH_INVEST",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    ),
    TargetField(
        "NETCASH_FINANCE",
        "筹资活动产生的现金流量净额",
        "cash_flow",
        ("筹资活动产生的现金流量净额",),
        ("NETCASH_FINANCE",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    ),
    TargetField(
        "RATE_CHANGE_EFFECT",
        "汇率变动对现金及现金等价物的影响",
        "cash_flow",
        ("汇率变动对现金及现金等价物的影响", "汇率变动对现金及现金等价"),
        ("RATE_CHANGE_EFFECT",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    ),
    TargetField(
        "CCE_ADD",
        "现金及现金等价物净增加额",
        "cash_flow",
        ("现金及现金等价物净增加额",),
        ("CCE_ADD",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    ),
    TargetField(
        "BEGIN_CCE",
        "期初现金及现金等价物余额",
        "cash_flow",
        ("期初现金及现金等价物余额",),
        ("BEGIN_CCE",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    ),
    TargetField(
        "END_CCE",
        "期末现金及现金等价物余额",
        "cash_flow",
        ("期末现金及现金等价物余额",),
        ("END_CCE",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    ),
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


def _choose_amounts(
    values: list[tuple[float, int, str]],
) -> tuple[tuple[float, int, str], tuple[float, int, str] | None] | None:
    if not values:
        return None
    plausible: list[tuple[float, int, str]] = []
    for value in values:
        number, _, raw = value
        # Notes usually appear as tiny integers.  Financial statement amounts are
        # normally larger or contain comma/decimal formatting.
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


def _heading_events(page: Any | None, text: str) -> list[tuple[float, str, str]]:
    heading_map = {
        "合并资产负债表": ("balance_sheet", "consolidated"),
        "资产负债表": ("balance_sheet", "consolidated"),
        "母公司资产负债表": ("balance_sheet", "parent"),
        "合并利润表": ("income_statement", "consolidated"),
        "利润表": ("income_statement", "consolidated"),
        "母公司利润表": ("income_statement", "parent"),
        "合并现金流量表": ("cash_flow", "consolidated"),
        "现金流量表": ("cash_flow", "consolidated"),
        "母公司现金流量表": ("cash_flow", "parent"),
    }
    lines = [_compact(line) for line in text.splitlines() if _compact(line)]
    events: list[tuple[float, str, str]] = []
    used: set[tuple[str, float]] = set()
    for line_index, line in enumerate(lines):
        context = heading_map.get(line)
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
        identity = (line, approximate_top)
        if identity in used:
            continue
        used.add(identity)
        events.append((approximate_top, context[0], context[1]))
    events.sort(key=lambda item: item[0])
    return events


def _section_from_text(text: str) -> tuple[str | None, str | None]:
    events = _heading_events(None, text)
    return (events[-1][1], events[-1][2]) if events else (None, None)


def _normalized_label(value: Any) -> str:
    label = _compact(value).replace(":", "：")
    label = re.sub(r"^[一二三四五六七八九十百]+、", "", label)
    label = re.sub(r"^\d+[.、]", "", label)
    for prefix in ("其中：", "加：", "减："):
        if label.startswith(prefix):
            label = label[len(prefix) :]
    return label.rstrip("：")


def _label_matches(label: Any, alias: str) -> bool:
    normalized = _normalized_label(label)
    target = _normalized_label(alias)
    if normalized == target:
        return True
    if normalized.startswith(target):
        suffix = normalized[len(target) :]
        return not suffix or suffix.startswith(("（", "("))
    return False


class PdfStatementParser:
    def __init__(self, targets: Iterable[TargetField] = DEFAULT_TARGETS) -> None:
        self.targets = tuple(targets)
        self.summary_targets = tuple(target for target in self.targets if target.statement_type == "summary")

    def extract(self, pdf_path: Path | str, document: OfficialDocument) -> list[OfficialFact]:
        pdf_path = Path(pdf_path)
        candidates: dict[str, list[tuple[int, OfficialFact]]] = {
            target.field_key: [] for target in self.targets
        }
        active_section: str | None = None
        active_scope: str | None = None
        active_until = 0
        previous_unit = ("元", 1.0)

        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = (
                    page.extract_text(x_tolerance=1.5, y_tolerance=3, layout=True)
                    or page.extract_text()
                    or ""
                )
                events = _heading_events(page, text)
                page_section, page_scope = active_section, active_scope
                if page_number > active_until and not events:
                    page_section, page_scope = None, None
                    active_section, active_scope = None, None

                # A heading in the upper half applies to the current page.  A late
                # heading starts a new table after the preceding statement table.
                if events and events[0][0] <= float(page.height) * 0.45:
                    page_section, page_scope = events[0][1], events[0][2]

                unit = _unit_info(text)
                explicit_unit = bool(re.search(r"单位[：:](?:亿元|万元|千元|元)", _compact(text)))
                if not explicit_unit and unit[1] == 1.0 and previous_unit[1] != 1.0 and page_section:
                    unit = previous_unit
                elif explicit_unit or unit[1] != 1.0 or page_section:
                    previous_unit = unit

                compact_text = _compact(text)
                has_summary_alias = "扣除非经常性损益" in compact_text or any(
                    _compact(alias) in compact_text
                    for target in self.summary_targets
                    for alias in target.aliases
                )
                should_find_tables = bool(page_section or events or has_summary_alias)
                table_contexts: list[tuple[list[list[Any]], str | None, str | None]] = []
                if should_find_tables:
                    try:
                        found_tables = page.find_tables() or []
                    except Exception:  # noqa: BLE001
                        found_tables = []
                    for found_table in found_tables:
                        table_section, table_scope = active_section, active_scope
                        table_top = float(found_table.bbox[1])
                        for event_top, event_section, event_scope in events:
                            if event_top <= table_top:
                                table_section, table_scope = event_section, event_scope
                            else:
                                break
                        table_contexts.append((found_table.extract() or [], table_section, table_scope))

                for target in self.targets:
                    extracted = self._extract_from_table_contexts(
                        table_contexts,
                        target,
                        document,
                        page_number,
                        unit,
                    )
                    if extracted:
                        score = 100 + (15 if extracted.scope == "consolidated" else 0)
                        candidates[target.field_key].append((score, extracted))
                        continue

                    allowed_text = target.statement_type == "summary" or (
                        page_section == target.statement_type and page_scope != "parent"
                    )
                    if not allowed_text:
                        continue
                    extracted = self._extract_from_text(
                        text,
                        target,
                        document,
                        page_number,
                        unit,
                        page_scope or "consolidated",
                    )
                    if extracted:
                        score = 60 + (15 if page_scope == "consolidated" else 0)
                        candidates[target.field_key].append((score, extracted))

                if events:
                    active_section, active_scope = events[-1][1], events[-1][2]
                    active_until = page_number + 5

        facts: list[OfficialFact] = []
        for target in self.targets:
            found = candidates[target.field_key]
            if not found:
                continue
            found.sort(key=lambda item: (-item[0], item[1].source_page))
            facts.append(found[0][1])
        return facts

    def _extract_from_table_contexts(
        self,
        table_contexts: list[tuple[list[list[Any]], str | None, str | None]],
        target: TargetField,
        document: OfficialDocument,
        page_number: int,
        unit: tuple[str, float],
    ) -> OfficialFact | None:
        for table, section, scope in table_contexts:
            if target.statement_type != "summary" and (section != target.statement_type or scope == "parent"):
                continue
            extracted = self._extract_from_table(
                table,
                target,
                document,
                page_number,
                unit,
                scope or "consolidated",
            )
            if extracted:
                return extracted
        return None

    def _extract_from_table(
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
            return OfficialFact(
                security_code=document.security_code,
                report_date=document.report_date,
                statement_type=target.statement_type,
                scope=scope,
                field_key=target.field_key,
                field_name_report=alias,
                value=current[0] * unit[1],
                unit=unit[0],
                normalized_unit="元",
                source_document=document.title,
                source_url=document.url,
                source_page=page_number,
                source_row=joined,
                extraction_method="PDF_TABLE",
                precision_tolerance=_tolerance(unit[1], current[1]),
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
        for index, line in enumerate(lines):
            alias = next((name for name in target.aliases if _label_matches(line, name)), None)
            if not alias:
                continue
            context_lines = lines[index : min(index + 3, len(lines))]
            context = " ".join(context_lines)
            compact_context = _compact(context)
            position = compact_context.find(_compact(alias))
            after_alias = (
                compact_context[position + len(_compact(alias)) :] if position >= 0 else compact_context
            )
            amounts = _choose_amounts(_numeric_candidates([after_alias]))
            if not amounts:
                continue
            current, _previous = amounts
            if not math.isfinite(current[0]):
                continue
            return OfficialFact(
                security_code=document.security_code,
                report_date=document.report_date,
                statement_type=target.statement_type,
                scope=scope,
                field_key=target.field_key,
                field_name_report=alias,
                value=current[0] * unit[1],
                unit=unit[0],
                normalized_unit="元",
                source_document=document.title,
                source_url=document.url,
                source_page=page_number,
                source_row=context,
                extraction_method="PDF_TEXT_LINE",
                precision_tolerance=_tolerance(unit[1], current[1]),
                confidence="medium",
            )
        return None
