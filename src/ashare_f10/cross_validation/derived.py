from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

import pandas as pd

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Name,
    ast.Constant,
    ast.Load,
)


class DerivedFormulaError(ValueError):
    pass


def evaluate_simple_formula(formula: str, values: Mapping[str, float]) -> float:
    tree = ast.parse(formula, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise DerivedFormulaError(f"不支持的公式节点：{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in values:
            raise DerivedFormulaError(f"缺少公式字段：{node.id}")
    result = eval(compile(tree, "<official-derived>", "eval"), {"__builtins__": {}}, dict(values))
    if isinstance(result, bool) or not isinstance(result, (int, float)):
        raise DerivedFormulaError("公式结果不是数值")
    return float(result)


NON_ADDITIVE_CASH_FLOW_FIELDS = {
    "BEGIN_CCE",
    "END_CCE",
    "BEGIN_CASH",
    "END_CASH",
    "BEGIN_CASH_EQUIVALENTS",
    "END_CASH_EQUIVALENTS",
}


def derive_independent_quarters(official: pd.DataFrame) -> pd.DataFrame:
    """Derive Q2/Q3/Q4 single-quarter flow facts from official cumulative statements."""
    if official.empty:
        return official.iloc[0:0].copy()
    flow = official[
        official["statement_type"].isin(["income_statement", "cash_flow"])
        & ~official["field_key"].isin(NON_ADDITIVE_CASH_FLOW_FIELDS)
    ].copy()
    if flow.empty:
        return flow
    output: list[dict[str, Any]] = []
    for (security_code, statement_type, _scope, field_key), group in flow.groupby(
        ["security_code", "statement_type", "scope", "field_key"], dropna=False
    ):
        records = {str(row.report_date)[:10]: row for row in group.itertuples(index=False)}
        years = sorted({int(date[:4]) for date in records if len(date) >= 10})
        for year in years:
            q1 = records.get(f"{year}-03-31")
            h1 = records.get(f"{year}-06-30")
            q3c = records.get(f"{year}-09-30")
            fy = records.get(f"{year}-12-31")
            pairs = [
                (h1, q1, "Q2"),
                (q3c, h1, "Q3"),
                (fy, q3c, "Q4"),
            ]
            for current, previous, period_type in pairs:
                if current is None or previous is None:
                    continue
                if pd.isna(current.value_num) or pd.isna(previous.value_num):
                    continue
                record = current._asdict()
                record["value_num"] = float(current.value_num) - float(previous.value_num)
                record["value_text"] = str(record["value_num"])
                record["period_type"] = period_type
                record["source_status"] = "FACT_CALCULATED"
                record["confidence"] = "high"
                record["source_row"] = f"{current.report_date}累计值 - {previous.report_date}累计值"
                record["record_key"] = (
                    f"{security_code}|{current.report_date}|{statement_type}|{field_key}|{period_type}"
                )
                output.append(record)
    return pd.DataFrame(output, columns=official.columns) if output else official.iloc[0:0].copy()


def derive_formula_facts(
    official: pd.DataFrame,
    formulas: Mapping[str, str],
    field_names: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    if official.empty or not formulas:
        return official.iloc[0:0].copy()
    field_names = dict(field_names or {})
    output: list[dict[str, Any]] = []
    direct = official[official["value_num"].notna()].copy()
    for (security_code, report_date, _scope), group in direct.groupby(
        ["security_code", "report_date", "scope"], dropna=False
    ):
        values = {
            str(row.field_key): float(row.value_num)
            for row in group.itertuples(index=False)
            if row.field_key and not pd.isna(row.value_num)
        }
        template = group.iloc[0].to_dict()
        for key, formula in formulas.items():
            try:
                value = evaluate_simple_formula(formula, values)
            except (DerivedFormulaError, ZeroDivisionError):
                continue
            record = dict(template)
            record.update(
                {
                    "theme": "官方披露/派生指标",
                    "family": "OFFICIAL_DERIVED",
                    "dataset": "官方披露派生指标",
                    "record_key": f"{security_code}|{report_date}|derived|{key}",
                    "statement_type": "financial_ratio",
                    "field_key": key,
                    "field_name_cn": field_names.get(key, key),
                    "value_num": value,
                    "value_text": str(value),
                    "unit": "%" if "* 100" in formula else "倍",
                    "normalized_unit": "%" if "* 100" in formula else "倍",
                    "source_status": "FACT_CALCULATED",
                    "source_document": "由官方披露基础字段计算",
                    "source_row": formula,
                    "precision_tolerance": max(1e-9, abs(value) * 1e-8),
                    "confidence": "high",
                }
            )
            output.append(record)
    return pd.DataFrame(output, columns=official.columns) if output else official.iloc[0:0].copy()


def derive_document_metadata(documents: pd.DataFrame) -> pd.DataFrame:
    """Create comparable official report metadata, including derived quarter labels.

    Annual, half-year and Q3 cumulative reports are also the authoritative inputs for
    Eastmoney's independently derived Q4/Q2/Q3 datasets.  Synthetic metadata rows keep
    those period labels comparable without pretending that a separate official report
    exists.
    """
    if documents.empty:
        return pd.DataFrame()
    labels = {
        "SECUCODE": "证券代码（含市场）",
        "SECURITY_CODE": "证券代码",
        "REPORT_DATE": "报告期",
        "REPORT_TYPE": "报告类型",
        "REPORT_DATE_NAME": "报告期名称",
        "NOTICE_DATE": "公告日期",
        "PUBLISH_DATE": "发布日期",
    }
    period_variants = {
        "annual": (("FY", "年报", "年报", False), ("Q4", "四季度", "四季度", True)),
        "q1": (("Q1", "一季报", "一季报", False),),
        "half": (("H1", "中报", "中报", False), ("Q2", "二季度", "二季度", True)),
        "q3": (("Q3C", "三季报", "三季报", False), ("Q3", "三季度", "三季度", True)),
    }
    output: list[dict[str, Any]] = []
    for document in documents.to_dict("records"):
        code = str(document.get("security_code") or "")
        report_date = str(document.get("report_date") or "")[:10]
        report_kind = str(document.get("report_kind") or "")
        publish_date = str(document.get("publish_date") or "")[:10]
        source = str(document.get("source") or "OFFICIAL")
        market = {"SSE": ".SH", "SZSE": ".SZ", "CNINFO": ".SZ", "BSE": ".BJ"}.get(source.upper(), "")
        year = report_date[:4]
        variants = period_variants.get(report_kind)
        if not variants:
            month = report_date[5:7] if len(report_date) >= 7 else ""
            variants = (
                (
                    {"03": "Q1", "06": "H1", "09": "Q3C", "12": "FY"}.get(month, "OTHER"),
                    report_kind,
                    report_kind,
                    False,
                ),
            )
        for period_type, report_type, report_name_suffix, calculated in variants:
            values = {
                "SECUCODE": f"{code}{market}" if code else "",
                "SECURITY_CODE": code,
                "REPORT_DATE": report_date,
                "REPORT_TYPE": report_type,
                "REPORT_DATE_NAME": f"{year}{report_name_suffix}" if year else report_name_suffix,
                "NOTICE_DATE": publish_date,
                "PUBLISH_DATE": publish_date,
            }
            for field_key, value_text in values.items():
                if not value_text:
                    continue
                output.append(
                    {
                        "security_code": code,
                        "theme": "官方披露/报告元数据",
                        "family": "OFFICIAL_DISCLOSURE",
                        "dataset": str(document.get("title") or "官方报告"),
                        "record_key": f"{code}|{report_date}|metadata|{period_type}|{field_key}",
                        "report_date": report_date,
                        "event_date": publish_date or None,
                        "period_type": period_type,
                        "statement_type": "metadata",
                        "scope": "entity",
                        "data_semantics": "metadata",
                        "field_key": field_key,
                        "field_name_cn": labels[field_key],
                        "field_category": "PAGE_DISPLAY_FIELD",
                        "value_text": value_text,
                        "value_num": None,
                        "unit": "",
                        "normalized_unit": "",
                        "source_url": str(document.get("url") or ""),
                        "source_document": str(document.get("title") or ""),
                        "source_page": 1,
                        "source_row": f"报告元数据：{labels[field_key]}={value_text}",
                        "precision_tolerance": None,
                        "confidence": "high",
                        "source_status": "FACT_CALCULATED" if calculated else "FACT_DIRECT",
                    }
                )
    return pd.DataFrame(output)
