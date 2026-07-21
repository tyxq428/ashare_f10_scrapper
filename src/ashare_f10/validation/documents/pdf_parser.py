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
_NUMBER_PATTERN = re.compile(
    r"(?:[-−]?\(\s*\d+(?:[,，]\d{3})*(?:\.\d+)?\s*\)|"
    r"[-−]?\d+(?:[,，]\d{3})*(?:\.\d+)?)"
)
_NOTE_REFERENCE_PATTERN = re.compile(
    r"[一二三四五六七八九十百]+(?:[（(]\d+(?:[-—]\d+)?[）)])+(?:[（(][A-Za-z][）)])?"
)


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
        if not (abs(value[0]) < 100 and re.fullmatch(r"[（(]\s*\d{1,2}\s*[）)]", value[2].strip()))
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
    text = re.sub(r"(^|\s)[一二三四五六七八九十百]+(?=\s|$)", " ", text)
    text = re.sub(r"[/／]+", " ", text)
    text = text.replace("%", " ")
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


def _tolerance(scale: float, decimals: int) -> float:
    return max(1.0, scale * 0.5 * (10 ** (-decimals)))


def _heading_context(line: str) -> tuple[str, str] | None:
    compact = _compact(line).replace("(", "（").replace(")", "）")
    compact = re.sub(r"^\d+[、.．]", "", compact)
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
        merged: dict[tuple[str, str], TargetField] = {}
        for target in targets:
            identity = (target.statement_type, target.field_key)
            aliases = target.aliases
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
            if identity == ("income_statement", "OTHER_COMPRE_INCOME"):
                aliases = tuple(dict.fromkeys(("其他综合收益的税后净额", *aliases)))
            if identity == ("cash_flow", "FINANCE_EXPENSE"):
                aliases = tuple(
                    dict.fromkeys(
                        (
                            "财务费用（收益以“－”号填列）",
                            *aliases,
                        )
                    )
                )
            existing = merged.get(identity)
            if existing is None:
                merged[identity] = TargetField(
                    target.field_key,
                    target.field_name_cn,
                    target.statement_type,
                    aliases,
                    target.eastmoney_keys,
                    target.eastmoney_families,
                    target.semantics,
                )
            else:
                merged[identity] = TargetField(
                    existing.field_key,
                    existing.field_name_cn,
                    existing.statement_type,
                    tuple(dict.fromkeys((*existing.aliases, *aliases))),
                    tuple(dict.fromkeys((*existing.eastmoney_keys, *target.eastmoney_keys))),
                    tuple(
                        dict.fromkeys(
                            (
                                *existing.eastmoney_families,
                                *target.eastmoney_families,
                            )
                        )
                    ),
                    existing.semantics,
                )
        self.targets = tuple(merged.values())
        self.summary_targets = tuple(target for target in self.targets if target.statement_type == "summary")

    def extract(self, pdf_path: Path | str, document: OfficialDocument) -> list[OfficialFact]:
        pdf_path = Path(pdf_path)
        candidates: dict[tuple[str, str], list[tuple[int, OfficialFact]]] = {
            (target.statement_type, target.field_key): [] for target in self.targets
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
                explicit_unit = _explicit_unit_info(text) is not None
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
                        candidates[(target.statement_type, target.field_key)].append((score, extracted))
                        continue

                    is_cashflow_supplement = (
                        target.statement_type == "cash_flow"
                        and target.field_key == "FINANCE_EXPENSE"
                        and _compact("财务费用（收益以“－”号填列）") in compact_text
                    )
                    allowed_text = (
                        target.statement_type == "summary"
                        or (page_section == target.statement_type and page_scope != "parent")
                        or is_cashflow_supplement
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
                        candidates[(target.statement_type, target.field_key)].append((score, extracted))

                if events:
                    active_section, active_scope = events[-1][1], events[-1][2]
                    active_until = page_number + 5

        facts: list[OfficialFact] = []
        for target in self.targets:
            found = candidates[(target.statement_type, target.field_key)]
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
