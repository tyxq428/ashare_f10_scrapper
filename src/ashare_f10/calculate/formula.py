from __future__ import annotations

import ast
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

from ashare_f10.calculate.ttm import compute_ttm


class FormulaError(ValueError):
    pass


# Multiple endpoints can expose the same raw key. Prefer the authoritative
# statement for direct values, keep derived/summary endpoints as fallbacks,
# and use the same precedence consistently across VALUE/QOQ/AVG/CAGR.
FAMILY_PRIORITY_SQL = """
CASE family
    WHEN 'RPT_F10_FINANCE_GBALANCE' THEN 0
    WHEN 'RPT_F10_FINANCE_GINCOME' THEN 1
    WHEN 'RPT_F10_FINANCE_GCASHFLOW' THEN 2
    WHEN 'RPT_F10_FINANCE_MAINFINADATA' THEN 3
    WHEN 'RPT_F10_FINANCE_GRATIO' THEN 4
    WHEN 'RPT_F10_QTR_MAINFINADATA' THEN 5
    WHEN 'RPT_F10_FINANCE_QGRATIO' THEN 6
    WHEN 'RPT_F10_FINANCE_GINCOMEQC' THEN 7
    WHEN 'RPT_F10_FINANCE_GCASHFLOWQC' THEN 8
    WHEN 'RPT_F10_FINANCE_DUPONT' THEN 90
    WHEN 'PageAjax' THEN 99
    ELSE 50
END
"""


class FormulaEngine:
    def __init__(self, db_path: Path | str, end_period: str | None = None):
        self.db_path = Path(db_path)
        self.end_period = end_period
        self.connection = duckdb.connect(str(self.db_path), read_only=True)
        self.trace: list[dict[str, Any]] = []

    def close(self) -> None:
        self.connection.close()

    def _field_row(self, field: str, period: str | None = None, before: bool = True) -> tuple[Any, ...]:
        selected_period = period or self.end_period
        comparator = "<=" if before else "="
        date_filter = f"AND report_date {comparator} ?" if selected_period else ""
        params: list[Any] = [field, field]
        if selected_period:
            params.append(selected_period)
        params.append(field)
        row = self.connection.execute(
            f"""
            SELECT field_key, field_name_cn, report_date, value_num, coalesce(unit, ''), family
            FROM facts
            WHERE (lower(field_key) = lower(?) OR field_name_cn = ?)
              AND value_num IS NOT NULL
              {date_filter}
            ORDER BY CASE WHEN lower(field_key) = lower(?) THEN 0 ELSE 1 END,
                     report_date DESC NULLS LAST,
                     {FAMILY_PRIORITY_SQL},
                     family,
                     dataset
            LIMIT 1
            """,
            params,
        ).fetchone()
        if not row:
            raise FormulaError(f"未找到字段或期间数据：{field}")
        return row

    def value(self, field: str, period: str | None = None) -> float:
        row = self._field_row(field, period)
        value = float(row[3])
        self.trace.append(
            {
                "function": "VALUE",
                "field_key": row[0],
                "field_name_cn": row[1],
                "report_date": str(row[2])[:10] if row[2] else None,
                "value": value,
                "unit": row[4],
                "family": row[5],
            }
        )
        return value

    def ttm(self, field: str) -> float:
        if not self.end_period:
            raise FormulaError("TTM计算必须指定结束报告期")
        result = compute_ttm(self.db_path, field, self.end_period)
        self.trace.append(
            {
                "function": "TTM",
                "field_key": result.field_key,
                "field_name_cn": result.field_name_cn,
                "end_period": result.end_period,
                "value": result.value,
                "unit": result.unit,
                "method": result.method,
                "formula": result.formula,
            }
        )
        return result.value

    def yoy(self, field: str) -> float:
        if not self.end_period:
            raise FormulaError("同比计算必须指定结束报告期")
        year = int(self.end_period[:4]) - 1
        previous = f"{year}{self.end_period[4:]}"
        current_value = self.value(field, self.end_period)
        previous_value = self.value(field, previous)
        if previous_value == 0:
            raise FormulaError("上年同期值为0，无法计算同比")
        result = current_value / previous_value - 1
        self.trace.append({"function": "YOY", "field": field, "value": result})
        return result

    def qoq(self, field: str) -> float:
        if not self.end_period:
            raise FormulaError("环比计算必须指定结束报告期")
        row = self._field_row(field, self.end_period)
        current_date = str(row[2])[:10]
        previous = self.connection.execute(
            """
            SELECT report_date, value_num FROM facts
            WHERE field_key = ? AND family = ? AND value_num IS NOT NULL AND report_date < ?
            ORDER BY report_date DESC LIMIT 1
            """,
            [row[0], row[5], current_date],
        ).fetchone()
        if not previous or float(previous[1]) == 0:
            raise FormulaError("缺少可用上一期数据或上一期值为0")
        result = float(row[3]) / float(previous[1]) - 1
        self.trace.append(
            {
                "function": "QOQ",
                "field": field,
                "current_date": current_date,
                "previous_date": str(previous[0])[:10],
                "value": result,
            }
        )
        return result

    def average(self, field: str, periods: int = 4) -> float:
        selected_period = self.end_period or "9999-12-31"
        rows = self.connection.execute(
            f"""
            SELECT report_date, value_num FROM facts
            WHERE (lower(field_key) = lower(?) OR field_name_cn = ?)
              AND value_num IS NOT NULL AND report_date <= ?
            QUALIFY row_number() OVER (
                PARTITION BY report_date ORDER BY {FAMILY_PRIORITY_SQL}, family, dataset
            ) = 1
            ORDER BY report_date DESC LIMIT ?
            """,
            [field, field, selected_period, int(periods)],
        ).fetchall()
        if not rows:
            raise FormulaError(f"字段 {field} 没有可用于平均值的数据")
        result = sum(float(row[1]) for row in rows) / len(rows)
        self.trace.append({"function": "AVG", "field": field, "periods": len(rows), "value": result})
        return result

    def cagr(self, field: str, years: int = 3) -> float:
        selected_period = self.end_period or "9999-12-31"
        rows = self.connection.execute(
            f"""
            SELECT report_date, value_num FROM facts
            WHERE (lower(field_key) = lower(?) OR field_name_cn = ?)
              AND value_num IS NOT NULL AND report_date <= ? AND right(report_date, 5) = '12-31'
            QUALIFY row_number() OVER (
                PARTITION BY report_date ORDER BY {FAMILY_PRIORITY_SQL}, family, dataset
            ) = 1
            ORDER BY report_date DESC LIMIT ?
            """,
            [field, field, selected_period, int(years) + 1],
        ).fetchall()
        if len(rows) < 2:
            raise FormulaError("年度数据不足，无法计算CAGR")
        latest = float(rows[0][1])
        oldest = float(rows[-1][1])
        intervals = len(rows) - 1
        if latest <= 0 or oldest <= 0:
            raise FormulaError("CAGR要求期初和期末值均大于0")
        result = (latest / oldest) ** (1 / intervals) - 1
        self.trace.append({"function": "CAGR", "field": field, "years": intervals, "value": result})
        return result

    def evaluate(self, formula: str) -> dict[str, Any]:
        expression = ast.parse(formula, mode="eval")
        value = self._eval_node(expression.body)
        if not math.isfinite(value):
            raise FormulaError("计算结果不是有限数值")
        return {"formula": formula, "end_period": self.end_period, "value": value, "trace": self.trace}

    def _eval_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise FormulaError("字符串只能用于字段函数参数")
        if isinstance(node, ast.Name):
            return self.value(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._eval_node(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise FormulaError("除数不能为0")
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            functions: dict[str, Callable[..., float]] = {
                "F": self.value,
                "VALUE": self.value,
                "TTM": self.ttm,
                "YOY": self.yoy,
                "QOQ": self.qoq,
                "AVG": self.average,
                "CAGR": self.cagr,
            }
            name = node.func.id.upper()
            function = functions.get(name)
            if function is None:
                raise FormulaError(f"不支持的函数：{node.func.id}")
            args: list[Any] = []
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    args.append(arg.value)
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
                    args.append(arg.value)
                elif isinstance(arg, ast.Name):
                    args.append(arg.id)
                else:
                    args.append(self._eval_node(arg))
            return float(function(*args))
        raise FormulaError(f"不支持的表达式节点：{type(node).__name__}")


def evaluate_formula(db_path: Path | str, formula: str, end_period: str | None = None) -> dict[str, Any]:
    engine = FormulaEngine(db_path, end_period)
    try:
        return engine.evaluate(formula)
    finally:
        engine.close()
