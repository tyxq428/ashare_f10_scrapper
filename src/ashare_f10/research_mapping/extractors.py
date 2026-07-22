from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "") for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _contains(row: dict[str, Any], patterns: tuple[str, ...]) -> bool:
    haystack = "|".join(
        _text(row.get(key)).upper()
        for key in ("family", "dataset", "field_key", "field_name_cn", "metric_id")
    )
    return any(pattern.upper() in haystack for pattern in patterns)


def _fact_row(
    *,
    security_code: str,
    topic: str,
    metric_id: str,
    name_cn: str,
    report_date: str | None,
    event_date: str | None,
    period_type: str,
    value_num: float | None,
    value_text: str | None,
    unit: str,
    status: str,
    formula: str = "",
    input_ids: list[str] | None = None,
    source_fact_id: str = "",
    observation_id: str = "",
    notes: str = "",
) -> dict[str, Any]:
    research_fact_id = _stable_id(
        "rf",
        security_code,
        topic,
        metric_id,
        report_date,
        event_date,
        period_type,
        source_fact_id,
        observation_id,
        formula,
    )
    return {
        "research_fact_id": research_fact_id,
        "security_code": security_code,
        "topic": topic,
        "metric_id": metric_id,
        "name_cn": name_cn,
        "report_date": report_date,
        "event_date": event_date,
        "period_type": period_type,
        "value_num": value_num,
        "value_text": value_text,
        "unit": unit,
        "status": status,
        "formula": formula,
        "input_ids": json.dumps(input_ids or [], ensure_ascii=False),
        "source_fact_id": source_fact_id,
        "observation_id": observation_id,
        "notes": notes,
    }


@dataclass(slots=True)
class ResearchSectionPack:
    profit_quality: pd.DataFrame
    segments_and_kpis: pd.DataFrame
    research_and_development: pd.DataFrame
    capital_structure: pd.DataFrame
    capital_events: pd.DataFrame
    corporate_governance: pd.DataFrame
    risk_events: pd.DataFrame
    coverage_gaps: pd.DataFrame
    summary: dict[str, Any]

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "profit_quality": self.profit_quality,
            "segments_and_kpis": self.segments_and_kpis,
            "research_and_development": self.research_and_development,
            "capital_structure": self.capital_structure,
            "capital_events": self.capital_events,
            "corporate_governance": self.corporate_governance,
            "risk_events": self.risk_events,
            "coverage_gaps": self.coverage_gaps,
        }


class ResearchSectionExtractor:
    PROFIT_METRICS = {
        "financial.parent_net_profit": "归母净利润",
        "profit_quality.adjusted_parent_net_profit": "扣非归母净利润",
        "profit_quality.non_recurring_profit": "非经常性损益",
        "cashflow.operating_cash_flow": "经营活动现金流量净额",
        "cashflow.capital_expenditure": "购建长期资产支付现金",
        "balance.accounts_receivable": "应收账款",
        "balance.inventory": "存货",
        "balance.contract_assets": "合同资产",
        "balance.goodwill": "商誉",
        "research.rd_expense": "研发费用",
        "research.capitalized_rd": "资本化研发投入",
    }
    REQUIRED = {
        "profit_quality": (
            "financial.parent_net_profit",
            "profit_quality.adjusted_parent_net_profit",
            "cashflow.operating_cash_flow",
            "cashflow.capital_expenditure",
        ),
        "research_and_development": ("research.rd_expense",),
        "capital_structure": ("capital.total_shares",),
    }
    SEGMENT_NAME_PATTERNS = (
        "ITEM_NAME",
        "BUSINESS_NAME",
        "MAIN_BUSINESS",
        "PRODUCT_NAME",
        "INDUSTRY_NAME",
        "REGION_NAME",
        "主营构成",
        "分部名称",
        "产品名称",
        "行业名称",
        "地区名称",
    )
    SEGMENT_REVENUE_PATTERNS = ("REVENUE", "INCOME", "SALES", "营业收入", "主营收入")
    SEGMENT_COST_PATTERNS = ("COST", "营业成本", "主营成本")
    SEGMENT_PROFIT_PATTERNS = ("PROFIT", "毛利", "利润")
    SEGMENT_MARGIN_PATTERNS = ("MARGIN", "毛利率")
    RD_PATTERNS = ("RESEARCH", "R&D", "RD_", "研发")
    CAPITAL_PATTERNS = (
        "SHARE",
        "HOLDER",
        "CAPITAL",
        "PLEDGE",
        "BUYBACK",
        "REPURCHASE",
        "CONVERTIBLE",
        "RESTRICT",
        "LOCKUP",
        "UNLOCK",
        "股本",
        "股东",
        "质押",
        "回购",
        "可转债",
        "限售",
        "解禁",
    )
    CAPITAL_EVENT_PATTERNS = (
        "DIVIDEND",
        "PLACEMENT",
        "RIGHTS_ISSUE",
        "REFINANCE",
        "MERGER",
        "RESTRUCT",
        "减持",
        "增持",
        "分红",
        "定增",
        "配股",
        "再融资",
        "重组",
    )
    GOVERNANCE_PATTERNS = (
        "DIRECTOR",
        "MANAGER",
        "EXECUTIVE",
        "RELATED_PARTY",
        "GUARANTEE",
        "CONTROL_PERSON",
        "董事",
        "监事",
        "高管",
        "关联交易",
        "担保",
        "实际控制人",
    )
    RISK_PATTERNS = (
        "PENALTY",
        "VIOLATION",
        "LITIGATION",
        "LAWSUIT",
        "ARBITRATION",
        "DEFAULT",
        "BANKRUPTCY",
        "处罚",
        "违规",
        "诉讼",
        "仲裁",
        "违约",
        "破产",
    )

    @staticmethod
    def _direct_topic_rows(
        observations: pd.DataFrame,
        topic: str,
        metric_names: dict[str, str],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if observations.empty:
            return rows
        subset = observations[observations["metric_id"].isin(metric_names)]
        for row in subset.to_dict("records"):
            rows.append(
                _fact_row(
                    security_code=_text(row.get("security_code")),
                    topic=topic,
                    metric_id=_text(row.get("metric_id")),
                    name_cn=metric_names.get(_text(row.get("metric_id")), _text(row.get("metric_name_cn"))),
                    report_date=row.get("report_date"),
                    event_date=row.get("event_date"),
                    period_type=_text(row.get("period_type")),
                    value_num=_number(row.get("value_num")),
                    value_text=_text(row.get("value_text")) or None,
                    unit=_text(row.get("unit")),
                    status=_text(row.get("status")),
                    observation_id=_text(row.get("observation_id")),
                )
            )
        return rows

    @staticmethod
    def _derived_profit_quality(observations: pd.DataFrame) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if observations.empty:
            return rows
        keys = ["security_code", "report_date", "event_date", "period_type", "scope"]
        relevant = observations[
            observations["metric_id"].isin(
                {
                    "financial.parent_net_profit",
                    "profit_quality.adjusted_parent_net_profit",
                    "cashflow.operating_cash_flow",
                    "cashflow.capital_expenditure",
                    "research.rd_investment",
                    "research.capitalized_rd",
                }
            )
        ]
        for group_key, group in relevant.groupby(keys, dropna=False, sort=True):
            by_metric = {row["metric_id"]: row for row in group.to_dict("records")}
            security_code, report_date, event_date, period_type, _scope = group_key

            def add_ratio(
                metric_id: str,
                name_cn: str,
                numerator_metric: str,
                denominator_metric: str,
                formula: str,
                unit: str = "%",
                scale: float = 100.0,
            ) -> None:
                numerator = by_metric.get(numerator_metric)
                denominator = by_metric.get(denominator_metric)
                numerator_value = _number(numerator.get("value_num")) if numerator else None
                denominator_value = _number(denominator.get("value_num")) if denominator else None
                input_ids = [
                    _text(item.get("observation_id"))
                    for item in (numerator, denominator)
                    if item is not None
                ]
                if numerator_value is None or denominator_value in (None, 0.0):
                    value, status = None, "UNRESOLVED"
                    notes = "缺少计算所需的已核验规范事实，未补零"
                else:
                    value, status = numerator_value / denominator_value * scale, "FACT_CALCULATED"
                    notes = "由规范事实确定性计算"
                rows.append(
                    _fact_row(
                        security_code=_text(security_code),
                        topic="profit_quality",
                        metric_id=metric_id,
                        name_cn=name_cn,
                        report_date=_text(report_date) or None,
                        event_date=_text(event_date) or None,
                        period_type=_text(period_type),
                        value_num=value,
                        value_text=None,
                        unit=unit,
                        status=status,
                        formula=formula,
                        input_ids=input_ids,
                        notes=notes,
                    )
                )

            parent = by_metric.get("financial.parent_net_profit")
            adjusted = by_metric.get("profit_quality.adjusted_parent_net_profit")
            parent_value = _number(parent.get("value_num")) if parent else None
            adjusted_value = _number(adjusted.get("value_num")) if adjusted else None
            input_ids = [
                _text(item.get("observation_id")) for item in (parent, adjusted) if item is not None
            ]
            if parent_value is not None and adjusted_value is not None:
                non_recurring = parent_value - adjusted_value
                status, notes = "FACT_CALCULATED", "归母净利润减扣非归母净利润"
            else:
                non_recurring = None
                status, notes = "UNRESOLVED", "缺少归母或扣非归母净利润，未补零"
            rows.append(
                _fact_row(
                    security_code=_text(security_code),
                    topic="profit_quality",
                    metric_id="profit_quality.non_recurring_amount_calculated",
                    name_cn="计算口径非经常性损益",
                    report_date=_text(report_date) or None,
                    event_date=_text(event_date) or None,
                    period_type=_text(period_type),
                    value_num=non_recurring,
                    value_text=None,
                    unit="元",
                    status=status,
                    formula="parent_net_profit - adjusted_parent_net_profit",
                    input_ids=input_ids,
                    notes=notes,
                )
            )
            add_ratio(
                "profit_quality.non_recurring_share",
                "非经常性损益占归母净利润",
                "profit_quality.non_recurring_amount_calculated",
                "financial.parent_net_profit",
                "(parent_net_profit - adjusted_parent_net_profit) / abs(parent_net_profit)",
            )
            # The calculated amount is not an observation, so calculate this ratio directly.
            if non_recurring is None or parent_value in (None, 0.0):
                share_value, share_status = None, "UNRESOLVED"
            else:
                share_value, share_status = non_recurring / abs(parent_value) * 100.0, "FACT_CALCULATED"
            rows[-1]["value_num"] = share_value
            rows[-1]["status"] = share_status
            rows[-1]["input_ids"] = json.dumps(input_ids, ensure_ascii=False)

            add_ratio(
                "profit_quality.cfo_to_adjusted_profit",
                "经营现金流/扣非归母净利润",
                "cashflow.operating_cash_flow",
                "profit_quality.adjusted_parent_net_profit",
                "operating_cash_flow / adjusted_parent_net_profit",
                unit="x",
                scale=1.0,
            )

            cfo = by_metric.get("cashflow.operating_cash_flow")
            capex = by_metric.get("cashflow.capital_expenditure")
            cfo_value = _number(cfo.get("value_num")) if cfo else None
            capex_value = _number(capex.get("value_num")) if capex else None
            fcf_input_ids = [
                _text(item.get("observation_id")) for item in (cfo, capex) if item is not None
            ]
            if cfo_value is None or capex_value is None:
                fcf_value, fcf_status = None, "UNRESOLVED"
            else:
                fcf_value, fcf_status = cfo_value - capex_value, "FACT_CALCULATED"
            rows.append(
                _fact_row(
                    security_code=_text(security_code),
                    topic="profit_quality",
                    metric_id="profit_quality.simplified_free_cash_flow",
                    name_cn="简化自由现金流",
                    report_date=_text(report_date) or None,
                    event_date=_text(event_date) or None,
                    period_type=_text(period_type),
                    value_num=fcf_value,
                    value_text=None,
                    unit="元",
                    status=fcf_status,
                    formula="operating_cash_flow - capital_expenditure",
                    input_ids=fcf_input_ids,
                    notes="简化口径，不替代完整现金流标准化",
                )
            )

            rd = by_metric.get("research.rd_investment")
            capitalized = by_metric.get("research.capitalized_rd")
            rd_value = _number(rd.get("value_num")) if rd else None
            cap_rd_value = _number(capitalized.get("value_num")) if capitalized else None
            if rd_value not in (None, 0.0) and cap_rd_value is not None:
                ratio, ratio_status = cap_rd_value / rd_value * 100.0, "FACT_CALCULATED"
            else:
                ratio, ratio_status = None, "UNRESOLVED"
            rows.append(
                _fact_row(
                    security_code=_text(security_code),
                    topic="profit_quality",
                    metric_id="profit_quality.rd_capitalization_rate",
                    name_cn="研发投入资本化率",
                    report_date=_text(report_date) or None,
                    event_date=_text(event_date) or None,
                    period_type=_text(period_type),
                    value_num=ratio,
                    value_text=None,
                    unit="%",
                    status=ratio_status,
                    formula="capitalized_rd / rd_investment",
                    input_ids=[
                        _text(item.get("observation_id"))
                        for item in (capitalized, rd)
                        if item is not None
                    ],
                    notes="缺少任一输入时保持UNRESOLVED",
                )
            )
        return rows

    @classmethod
    def _segments(cls, source_facts: pd.DataFrame) -> pd.DataFrame:
        if source_facts.empty:
            return pd.DataFrame()
        segment_candidates = source_facts[
            source_facts.apply(
                lambda row: _contains(
                    row.to_dict(),
                    ("BUSINESS", "SEGMENT", "MAINOP", "主营", "分部", "产品构成", "行业构成"),
                ),
                axis=1,
            )
        ]
        records: list[dict[str, Any]] = []
        group_columns = [
            "security_code",
            "report_date",
            "event_date",
            "period_type",
            "family",
            "dataset",
            "record_key",
        ]
        for group_key, group in segment_candidates.groupby(group_columns, dropna=False, sort=True):
            fields = group.to_dict("records")

            def first_text(patterns: tuple[str, ...]) -> str:
                for item in fields:
                    if _contains(item, patterns):
                        value = _text(item.get("value_text"))
                        if value:
                            return value
                return ""

            def first_number(patterns: tuple[str, ...]) -> float | None:
                for item in fields:
                    if _contains(item, patterns):
                        value = _number(item.get("normalized_value_num"))
                        if value is not None:
                            return value
                return None

            segment_name = first_text(cls.SEGMENT_NAME_PATTERNS)
            revenue = first_number(cls.SEGMENT_REVENUE_PATTERNS)
            cost = first_number(cls.SEGMENT_COST_PATTERNS)
            profit = first_number(cls.SEGMENT_PROFIT_PATTERNS)
            margin = first_number(cls.SEGMENT_MARGIN_PATTERNS)
            if not segment_name and revenue is None and cost is None and profit is None and margin is None:
                continue
            if profit is None and revenue is not None and cost is not None:
                profit = revenue - cost
            if margin is None and profit is not None and revenue not in (None, 0.0):
                margin = profit / revenue * 100.0
            security_code, report_date, event_date, period_type, family, dataset, record_key = group_key
            records.append(
                {
                    "segment_record_id": _stable_id(
                        "segment",
                        security_code,
                        report_date,
                        event_date,
                        period_type,
                        family,
                        dataset,
                        record_key,
                    ),
                    "security_code": _text(security_code),
                    "report_date": _text(report_date) or None,
                    "event_date": _text(event_date) or None,
                    "period_type": _text(period_type),
                    "segment_name": segment_name or "UNRESOLVED_SEGMENT_NAME",
                    "revenue": revenue,
                    "cost": cost,
                    "profit": profit,
                    "margin_pct": margin,
                    "unit": "元",
                    "status": "FACT_DIRECT" if segment_name else "UNRESOLVED",
                    "family": _text(family),
                    "dataset": _text(dataset),
                    "record_key": _text(record_key),
                    "source_fact_ids": json.dumps(
                        sorted(group["source_fact_id"].astype(str).tolist()), ensure_ascii=False
                    ),
                }
            )
        return pd.DataFrame(records)

    @staticmethod
    def _route(source_facts: pd.DataFrame, patterns: tuple[str, ...], topic: str) -> pd.DataFrame:
        if source_facts.empty:
            return pd.DataFrame()
        subset = source_facts[
            source_facts.apply(lambda row: _contains(row.to_dict(), patterns), axis=1)
        ].copy()
        if subset.empty:
            return subset
        subset.insert(0, "research_fact_id", subset["source_fact_id"].map(lambda value: _stable_id("rf", topic, value)))
        subset.insert(2, "topic", topic)
        return subset.reset_index(drop=True)

    @classmethod
    def _coverage_gaps(
        cls,
        observations: pd.DataFrame,
        source_facts: pd.DataFrame,
        segments: pd.DataFrame,
    ) -> pd.DataFrame:
        security_codes = sorted(
            set(observations.get("security_code", pd.Series(dtype="object")).dropna().astype(str))
            | set(source_facts.get("security_code", pd.Series(dtype="object")).dropna().astype(str))
        )
        observed_metrics = set(observations.get("metric_id", pd.Series(dtype="object")).astype(str))
        rows: list[dict[str, Any]] = []
        for security_code in security_codes:
            for topic, required_metrics in cls.REQUIRED.items():
                for metric_id in required_metrics:
                    status = "PRESENT" if metric_id in observed_metrics else "MISSING"
                    rows.append(
                        {
                            "gap_id": _stable_id("gap", security_code, topic, metric_id),
                            "security_code": security_code,
                            "topic": topic,
                            "required_metric_id": metric_id,
                            "status": status,
                            "notes": (
                                "规范事实已存在"
                                if status == "PRESENT"
                                else "当前数据包未形成可靠规范事实；不得解释为数值为0"
                            ),
                        }
                    )
            segment_status = "PRESENT" if not segments.empty else "MISSING"
            rows.append(
                {
                    "gap_id": _stable_id("gap", security_code, "segments_and_kpis", "segment_records"),
                    "security_code": security_code,
                    "topic": "segments_and_kpis",
                    "required_metric_id": "segment_records",
                    "status": segment_status,
                    "notes": (
                        "已形成分部记录"
                        if segment_status == "PRESENT"
                        else "当前通用源未形成分部记录，需要官方附注或行业KPI补充"
                    ),
                }
            )
        return pd.DataFrame(rows)

    def extract(
        self,
        canonical_observations: pd.DataFrame,
        source_facts: pd.DataFrame,
    ) -> ResearchSectionPack:
        observations = canonical_observations.copy() if canonical_observations is not None else pd.DataFrame()
        facts = source_facts.copy() if source_facts is not None else pd.DataFrame()
        profit_rows = self._direct_topic_rows(observations, "profit_quality", self.PROFIT_METRICS)
        profit_rows.extend(self._derived_profit_quality(observations))
        profit_quality = pd.DataFrame(profit_rows)
        segments = self._segments(facts)
        rd = self._route(facts, self.RD_PATTERNS, "research_and_development")
        capital = self._route(facts, self.CAPITAL_PATTERNS, "capital_structure")
        capital_events = self._route(facts, self.CAPITAL_EVENT_PATTERNS, "capital_events")
        governance = self._route(facts, self.GOVERNANCE_PATTERNS, "corporate_governance")
        risks = self._route(facts, self.RISK_PATTERNS, "risk_events")
        gaps = self._coverage_gaps(observations, facts, segments)
        tables = {
            "profit_quality": profit_quality,
            "segments_and_kpis": segments,
            "research_and_development": rd,
            "capital_structure": capital,
            "capital_events": capital_events,
            "corporate_governance": governance,
            "risk_events": risks,
            "coverage_gaps": gaps,
        }
        summary = {
            "schema_version": "1.0.0",
            "table_counts": {name: len(frame) for name, frame in tables.items()},
            "calculated_fact_count": int(
                (profit_quality.get("status", pd.Series(dtype="object")) == "FACT_CALCULATED").sum()
            ),
            "unresolved_fact_count": int(
                (profit_quality.get("status", pd.Series(dtype="object")) == "UNRESOLVED").sum()
                + (gaps.get("status", pd.Series(dtype="object")) == "MISSING").sum()
            ),
            "gap_status_counts": dict(Counter(gaps.get("status", []))),
        }
        return ResearchSectionPack(
            profit_quality,
            segments,
            rd,
            capital,
            capital_events,
            governance,
            risks,
            gaps,
            summary,
        )
