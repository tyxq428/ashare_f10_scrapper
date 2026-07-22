from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import duckdb

from ashare_f10.validation.documents.pdf_parser import DEFAULT_TARGETS
from ashare_f10.validation.models import (
    LogicCheck,
    OfficialFact,
    ReconciliationResult,
    TTMValidation,
    TargetField,
)


def _relative_difference(left: float, right: float) -> float | None:
    denominator = max(abs(left), abs(right))
    return 0.0 if denominator == 0 else abs(left - right) / denominator


def _fetch_eastmoney_value(
    connection: duckdb.DuckDBPyConnection, target: TargetField, report_date: str
) -> tuple[float | None, str, str]:
    key_placeholders = ",".join("?" for _ in target.eastmoney_keys)
    family_placeholders = ",".join("?" for _ in target.eastmoney_families)
    query = f"""SELECT field_key, value_num, family, coalesce(unit, '') FROM facts WHERE report_date = ? AND field_key IN ({key_placeholders}) AND family IN ({family_placeholders}) AND value_num IS NOT NULL ORDER BY CASE family {"".join(f" WHEN ? THEN {index}" for index, _ in enumerate(target.eastmoney_families))} ELSE 999 END, CASE field_key {"".join(f" WHEN ? THEN {index}" for index, _ in enumerate(target.eastmoney_keys))} ELSE 999 END LIMIT 1"""
    parameters: list[Any] = [
        report_date,
        *target.eastmoney_keys,
        *target.eastmoney_families,
        *target.eastmoney_families,
        *target.eastmoney_keys,
    ]
    row = connection.execute(query, parameters).fetchone()
    return (float(row[1]), str(row[2]), str(row[3])) if row else (None, "", "")


def reconcile_official_facts(
    db_path: Path | str, official_facts: list[OfficialFact]
) -> list[ReconciliationResult]:
    connection = duckdb.connect(str(db_path), read_only=True)
    results: list[ReconciliationResult] = []
    try:
        lookup = {(fact.report_date, fact.field_key): fact for fact in official_facts}
        for report_date in sorted({fact.report_date for fact in official_facts}):
            for target in DEFAULT_TARGETS:
                fact = lookup.get((report_date, target.field_key))
                eastmoney_value, family, _unit = _fetch_eastmoney_value(connection, target, report_date)
                if fact is None and eastmoney_value is None:
                    continue
                official_value = fact.value if fact else None
                tolerance = fact.precision_tolerance if fact else 1.0
                difference = (
                    eastmoney_value - official_value
                    if eastmoney_value is not None and official_value is not None
                    else None
                )
                relative = (
                    _relative_difference(eastmoney_value, official_value)
                    if eastmoney_value is not None and official_value is not None
                    else None
                )
                if fact is None:
                    status, grade, notes = "MISSING_OFFICIAL", "E", "官方报告中未可靠提取该字段"
                elif eastmoney_value is None:
                    status, grade, notes = (
                        "MISSING_EASTMONEY",
                        "E",
                        "东方财富标准事实表未找到相同报告期和字段",
                    )
                elif abs(difference or 0.0) <= tolerance:
                    status = "EXACT_MATCH" if abs(difference or 0.0) <= 1.0 else "WITHIN_ROUNDING"
                    grade, notes = "A", "官方正式披露与东方财富值一致"
                else:
                    status, grade, notes = "MISMATCH", "E", "超出官方披露精度容差"
                results.append(
                    ReconciliationResult(
                        fact.security_code if fact else "",
                        report_date,
                        target.statement_type,
                        target.field_key,
                        target.field_name_cn,
                        eastmoney_value,
                        official_value,
                        difference,
                        tolerance,
                        relative,
                        status,
                        grade,
                        fact.source_document if fact else "",
                        fact.source_page if fact else None,
                        fact.source_row if fact else "",
                        family,
                        notes,
                    )
                )
    finally:
        connection.close()
    return results


def _logic_result(
    security_code: str,
    report_date: str,
    check_id: str,
    description: str,
    left_value: float | None,
    right_value: float | None,
    tolerance: float,
    source: str,
    components: dict[str, float | None],
) -> LogicCheck:
    if left_value is None or right_value is None:
        status, difference = "UNRESOLVED", None
    else:
        difference = left_value - right_value
        status = "PASS" if abs(difference) <= tolerance else "FAIL"
    return LogicCheck(
        security_code,
        report_date,
        check_id,
        description,
        left_value,
        right_value,
        difference,
        tolerance,
        status,
        source,
        components,
    )


def build_logic_checks(official_facts: list[OfficialFact]) -> list[LogicCheck]:
    grouped: dict[str, dict[str, OfficialFact]] = defaultdict(dict)
    for fact in official_facts:
        grouped[fact.report_date][fact.field_key] = fact
    checks: list[LogicCheck] = []
    for report_date, facts in sorted(grouped.items()):
        security_code = next(iter(facts.values())).security_code
        assets, liabilities, equity, total = (
            facts.get("TOTAL_ASSETS"),
            facts.get("TOTAL_LIABILITIES"),
            facts.get("TOTAL_EQUITY"),
            facts.get("TOTAL_LIAB_EQUITY"),
        )
        tolerance = max(
            [fact.precision_tolerance for fact in (assets, liabilities, equity, total) if fact] or [1.0]
        )
        checks.append(
            _logic_result(
                security_code,
                report_date,
                "BALANCE_ASSETS_EQ_LIAB_PLUS_EQUITY",
                "资产总计 = 负债合计 + 所有者权益合计",
                assets.value if assets else None,
                liabilities.value + equity.value if liabilities and equity else None,
                tolerance * 2,
                "OFFICIAL_DISCLOSURE",
                {
                    "TOTAL_ASSETS": assets.value if assets else None,
                    "TOTAL_LIABILITIES": liabilities.value if liabilities else None,
                    "TOTAL_EQUITY": equity.value if equity else None,
                },
            )
        )
        checks.append(
            _logic_result(
                security_code,
                report_date,
                "BALANCE_ASSETS_EQ_TOTAL_LIAB_EQUITY",
                "资产总计 = 负债和所有者权益总计",
                assets.value if assets else None,
                total.value if total else None,
                tolerance,
                "OFFICIAL_DISCLOSURE",
                {
                    "TOTAL_ASSETS": assets.value if assets else None,
                    "TOTAL_LIAB_EQUITY": total.value if total else None,
                },
            )
        )
        cce, operate, invest, finance, rate = (
            facts.get("CCE_ADD"),
            facts.get("NETCASH_OPERATE"),
            facts.get("NETCASH_INVEST"),
            facts.get("NETCASH_FINANCE"),
            facts.get("RATE_CHANGE_EFFECT"),
        )
        cash_tolerance = max(
            [fact.precision_tolerance for fact in (cce, operate, invest, finance, rate) if fact] or [1.0]
        )
        right = (
            operate.value + invest.value + finance.value + (rate.value if rate else 0.0)
            if operate and invest and finance
            else None
        )
        checks.append(
            _logic_result(
                security_code,
                report_date,
                "CASHFLOW_NET_CHANGE",
                "现金及现金等价物净增加额 = 经营 + 投资 + 筹资 + 汇率影响",
                cce.value if cce else None,
                right,
                cash_tolerance * 3,
                "OFFICIAL_DISCLOSURE",
                {
                    "CCE_ADD": cce.value if cce else None,
                    "NETCASH_OPERATE": operate.value if operate else None,
                    "NETCASH_INVEST": invest.value if invest else None,
                    "NETCASH_FINANCE": finance.value if finance else None,
                    "RATE_CHANGE_EFFECT": rate.value if rate else None,
                },
            )
        )
    return checks


def _one_value(
    connection: duckdb.DuckDBPyConnection, field_key: str, family: str, report_date: str
) -> float | None:
    row = connection.execute(
        "SELECT value_num FROM facts WHERE field_key = ? AND family = ? AND report_date = ? AND value_num IS NOT NULL LIMIT 1",
        [field_key, family, report_date],
    ).fetchone()
    return float(row[0]) if row else None


def build_ttm_checks(
    db_path: Path | str,
    security_code: str,
    end_period: str = "2026-03-31",
    fields: tuple[tuple[str, str], ...] = (
        ("OPERATE_INCOME", "营业收入"),
        ("PARENT_NETPROFIT", "归母净利润"),
    ),
) -> list[TTMValidation]:
    if end_period[5:7] != "03":
        raise ValueError("薄切片TTM双公式验证当前要求结束期为第一季度")
    year = int(end_period[:4])
    independent_dates = (f"{year - 1}-06-30", f"{year - 1}-09-30", f"{year - 1}-12-31", end_period)
    previous_fy, previous_q1 = f"{year - 1}-12-31", f"{year - 1}-03-31"
    results: list[TTMValidation] = []
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        for field_key, field_name in fields:
            independent_components: list[dict[str, Any]] = []
            independent_values: list[float] = []
            for report_date in independent_dates:
                value = _one_value(connection, field_key, "RPT_F10_FINANCE_GINCOMEQC", report_date)
                independent_components.append(
                    {"report_date": report_date, "value": value, "family": "RPT_F10_FINANCE_GINCOMEQC"}
                )
                if value is not None:
                    independent_values.append(value)
            independent_total = sum(independent_values) if len(independent_values) == 4 else None
            fy_value = _one_value(connection, field_key, "RPT_F10_FINANCE_GINCOME", previous_fy)
            prior_q1_value = _one_value(connection, field_key, "RPT_F10_FINANCE_GINCOME", previous_q1)
            current_q1_value = _one_value(connection, field_key, "RPT_F10_FINANCE_GINCOME", end_period)
            cumulative_components = [
                {"report_date": previous_fy, "value": fy_value, "role": "add_previous_fy"},
                {"report_date": previous_q1, "value": prior_q1_value, "role": "subtract_prior_q1"},
                {"report_date": end_period, "value": current_q1_value, "role": "add_current_q1"},
            ]
            cumulative_total = (
                fy_value - prior_q1_value + current_q1_value
                if fy_value is not None and prior_q1_value is not None and current_q1_value is not None
                else None
            )
            if independent_total is None or cumulative_total is None:
                difference, status, tolerance = None, "UNRESOLVED", 1.0
            else:
                difference = independent_total - cumulative_total
                tolerance = max(1.0, max(abs(independent_total), abs(cumulative_total)) * 1e-10)
                status = (
                    "PASS" if math.isclose(independent_total, cumulative_total, abs_tol=tolerance) else "FAIL"
                )
            results.append(
                TTMValidation(
                    security_code,
                    field_key,
                    field_name,
                    end_period,
                    independent_total,
                    cumulative_total,
                    difference,
                    tolerance,
                    status,
                    independent_components,
                    cumulative_components,
                )
            )
    finally:
        connection.close()
    return results
