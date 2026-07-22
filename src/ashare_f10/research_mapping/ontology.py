from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: str
    name_cn: str
    research_module: str
    field_keys: tuple[str, ...]
    canonical_unit: str = ""
    data_semantics: str = ""
    preferred_scope: str = "consolidated"


_DEFAULT_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        "company.security_code",
        "证券代码",
        "company_master",
        ("SECURITY_CODE", "SECUCODE"),
        data_semantics="entity",
        preferred_scope="entity",
    ),
    MetricDefinition(
        "company.security_name",
        "证券简称",
        "company_master",
        ("SECURITY_NAME_ABBR", "SECURITY_NAME"),
        data_semantics="entity",
        preferred_scope="entity",
    ),
    MetricDefinition(
        "financial.revenue",
        "营业收入",
        "financial_statements",
        ("OPERATE_INCOME", "TOTAL_OPERATE_INCOME"),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "financial.operating_cost",
        "营业成本",
        "financial_statements",
        ("OPERATE_COST",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "financial.operating_profit",
        "营业利润",
        "financial_statements",
        ("OPERATE_PROFIT",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "financial.net_profit",
        "净利润",
        "financial_statements",
        ("NETPROFIT",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "financial.parent_net_profit",
        "归母净利润",
        "financial_statements",
        ("PARENT_NETPROFIT",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "profit_quality.adjusted_parent_net_profit",
        "扣非归母净利润",
        "profit_quality",
        ("DEDUCT_PARENT_NETPROFIT", "KCFJCXSYJLR", "DEDU_PARENT_PROFIT"),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "profit_quality.non_recurring_profit",
        "非经常性损益",
        "profit_quality",
        ("NON_RECURRING_PROFIT", "NONRECURRING_PROFIT"),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "cashflow.operating_cash_flow",
        "经营活动现金流量净额",
        "profit_quality",
        ("NETCASH_OPERATE",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "cashflow.investing_cash_flow",
        "投资活动现金流量净额",
        "financial_statements",
        ("NETCASH_INVEST",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "cashflow.financing_cash_flow",
        "筹资活动现金流量净额",
        "financial_statements",
        ("NETCASH_FINANCE",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "cashflow.capital_expenditure",
        "购建长期资产支付现金",
        "profit_quality",
        ("CONSTRUCT_LONG_ASSET",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "balance.cash",
        "货币资金",
        "financial_statements",
        ("MONETARYFUNDS",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.accounts_receivable",
        "应收账款",
        "profit_quality",
        ("ACCOUNTS_RECE",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.inventory",
        "存货",
        "profit_quality",
        ("INVENTORY",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.contract_assets",
        "合同资产",
        "profit_quality",
        ("CONTRACT_ASSET", "CONTRACT_ASSETS"),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.fixed_assets",
        "固定资产",
        "financial_statements",
        ("FIXED_ASSET",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.construction_in_progress",
        "在建工程",
        "financial_statements",
        ("CIP",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.goodwill",
        "商誉",
        "profit_quality",
        ("GOODWILL",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.total_assets",
        "资产总计",
        "financial_statements",
        ("TOTAL_ASSETS",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.total_liabilities",
        "负债合计",
        "financial_statements",
        ("TOTAL_LIABILITIES",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "balance.total_equity",
        "所有者权益合计",
        "financial_statements",
        ("TOTAL_EQUITY",),
        canonical_unit="元",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "research.rd_expense",
        "研发费用",
        "profit_quality",
        ("RESEARCH_EXPENSE",),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "research.rd_investment",
        "研发投入",
        "segments_and_kpis",
        ("RD_EXPENSE", "R&D_EXPENSE", "TOTAL_RD_EXPENSE"),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "research.capitalized_rd",
        "资本化研发投入",
        "profit_quality",
        ("CAPITALIZED_RD", "CAPITALIZED_RESEARCH_EXPENSE"),
        canonical_unit="元",
        data_semantics="flow",
    ),
    MetricDefinition(
        "profitability.gross_margin",
        "毛利率",
        "profit_quality",
        ("GROSS_MARGIN", "XSMLL"),
        canonical_unit="%",
    ),
    MetricDefinition(
        "profitability.roe",
        "净资产收益率",
        "profit_quality",
        ("ROE", "ROE_WEIGHT"),
        canonical_unit="%",
    ),
    MetricDefinition(
        "per_share.basic_eps",
        "基本每股收益",
        "quarterly_and_ttm",
        ("BASIC_EPS",),
        canonical_unit="元/股",
        data_semantics="flow",
    ),
    MetricDefinition(
        "capital.total_shares",
        "总股本",
        "capital_structure",
        ("TOTAL_SHARES", "TOTAL_SHARE", "TOTAL_EQUITY_SHARES"),
        canonical_unit="股",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "capital.free_float_shares",
        "流通股本",
        "capital_structure",
        ("FREE_SHARES", "FREE_FLOAT_SHARES"),
        canonical_unit="股",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "capital.holder_count",
        "股东户数",
        "capital_structure",
        ("HOLDER_TOTAL_NUM", "HOLDER_NUM"),
        canonical_unit="户",
        data_semantics="point_in_time",
    ),
    MetricDefinition(
        "governance.pledge_ratio",
        "质押比例",
        "governance_and_events",
        ("PLEDGE_RATIO",),
        canonical_unit="%",
        data_semantics="event",
        preferred_scope="entity",
    ),
    MetricDefinition(
        "market.close_price",
        "收盘价",
        "market_and_consensus",
        ("CLOSE_PRICE", "CLOSE"),
        canonical_unit="元/股",
        data_semantics="event",
        preferred_scope="entity",
    ),
    MetricDefinition(
        "consensus.revenue_forecast",
        "一致预期营业收入",
        "market_and_consensus",
        ("PREDICT_OPERATE_INCOME", "FORECAST_REVENUE"),
        canonical_unit="元",
        data_semantics="forecast",
        preferred_scope="entity",
    ),
    MetricDefinition(
        "consensus.parent_profit_forecast",
        "一致预期归母净利润",
        "market_and_consensus",
        ("PREDICT_PARENT_NETPROFIT", "FORECAST_PARENT_NETPROFIT"),
        canonical_unit="元",
        data_semantics="forecast",
        preferred_scope="entity",
    ),
)


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip()).strip("_").lower()
    return text or "unknown"


class ResearchOntology:
    def __init__(self, definitions: tuple[MetricDefinition, ...] = _DEFAULT_METRICS) -> None:
        self.definitions = definitions
        self.by_field_key: dict[str, MetricDefinition] = {}
        for definition in definitions:
            for key in definition.field_keys:
                self.by_field_key[key.upper()] = definition

    def resolve(self, fact: dict[str, Any]) -> tuple[MetricDefinition, bool]:
        field_key = str(fact.get("field_key") or "").upper()
        definition = self.by_field_key.get(field_key)
        if definition is not None:
            return definition, True
        family = _slug(str(fact.get("family") or "source"))
        fallback = MetricDefinition(
            metric_id=f"source.{family}.{_slug(field_key)}",
            name_cn=str(fact.get("field_name_cn") or field_key or "未命名字段"),
            research_module="coverage_and_gaps",
            field_keys=(field_key,),
            canonical_unit=str(fact.get("unit") or ""),
            data_semantics=str(fact.get("data_semantics") or ""),
            preferred_scope=str(fact.get("scope") or "entity"),
        )
        return fallback, False

    def definition_for_metric(self, metric_id: str) -> MetricDefinition | None:
        return next((item for item in self.definitions if item.metric_id == metric_id), None)
