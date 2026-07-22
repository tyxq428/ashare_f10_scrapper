from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

SINGLE_QUARTER_FAMILIES = (
    "RPT_F10_FINANCE_GINCOMEQC",
    "RPT_F10_FINANCE_GCASHFLOWQC",
)
CUMULATIVE_FAMILIES = (
    "RPT_F10_FINANCE_GINCOME",
    "RPT_F10_FINANCE_GCASHFLOW",
)


@dataclass
class TTMComponent:
    report_date: str
    value: float
    family: str
    formula_role: str


@dataclass
class TTMResult:
    field_key: str
    field_name_cn: str
    end_period: str
    value: float
    unit: str
    method: str
    formula: str
    components: list[TTMComponent]


def _previous_year(period: str) -> str:
    parsed = date.fromisoformat(period)
    return parsed.replace(year=parsed.year - 1).isoformat()


def _previous_fy(period: str) -> str:
    parsed = date.fromisoformat(period)
    return date(parsed.year - 1, 12, 31).isoformat()


def _resolve_field(connection: duckdb.DuckDBPyConnection, field: str) -> tuple[str, str, str]:
    row = connection.execute(
        """
        SELECT field_key, field_name_cn, coalesce(unit, '')
        FROM facts
        WHERE lower(field_key) = lower(?) OR field_name_cn = ?
        ORDER BY CASE WHEN lower(field_key) = lower(?) THEN 0 ELSE 1 END
        LIMIT 1
        """,
        [field, field, field],
    ).fetchone()
    if not row:
        raise ValueError(f"未找到字段：{field}")
    return str(row[0]), str(row[1]), str(row[2])


def compute_ttm(db_path: Path | str, field: str, end_period: str) -> TTMResult:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        field_key, field_name, unit = _resolve_field(connection, field)

        rows = connection.execute(
            """
            SELECT report_date, value_num, family
            FROM facts
            WHERE field_key = ?
              AND family IN (?, ?)
              AND report_date <= ?
              AND value_num IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY report_date ORDER BY family) = 1
            ORDER BY report_date DESC
            LIMIT 4
            """,
            [field_key, *SINGLE_QUARTER_FAMILIES, end_period],
        ).fetchall()
        if len(rows) == 4 and str(rows[0][0])[:10] == end_period:
            components = [
                TTMComponent(str(row[0])[:10], float(row[1]), str(row[2]), "add") for row in reversed(rows)
            ]
            value = sum(component.value for component in components)
            formula = " + ".join(f"{item.report_date}:{item.value:g}" for item in components)
            return TTMResult(
                field_key=field_key,
                field_name_cn=field_name,
                end_period=end_period,
                value=value,
                unit=unit,
                method="FOUR_INDEPENDENT_QUARTERS",
                formula=formula,
                components=components,
            )

        end_month = end_period[5:7]
        current = connection.execute(
            """
            SELECT report_date, value_num, family FROM facts
            WHERE field_key = ? AND family IN (?, ?) AND report_date = ? AND value_num IS NOT NULL
            LIMIT 1
            """,
            [field_key, *CUMULATIVE_FAMILIES, end_period],
        ).fetchone()
        if not current:
            raise ValueError(f"字段 {field_name} 在 {end_period} 没有累计口径数据")

        if end_month == "12":
            component = TTMComponent(end_period, float(current[1]), str(current[2]), "current_fy")
            return TTMResult(
                field_key=field_key,
                field_name_cn=field_name,
                end_period=end_period,
                value=float(current[1]),
                unit=unit,
                method="FULL_YEAR_EQUALS_TTM",
                formula=f"{end_period}年报累计值",
                components=[component],
            )

        previous_fy_date = _previous_fy(end_period)
        previous_same_date = _previous_year(end_period)
        previous_fy = connection.execute(
            """
            SELECT value_num, family FROM facts
            WHERE field_key = ? AND family IN (?, ?) AND report_date = ? AND value_num IS NOT NULL LIMIT 1
            """,
            [field_key, *CUMULATIVE_FAMILIES, previous_fy_date],
        ).fetchone()
        previous_same = connection.execute(
            """
            SELECT value_num, family FROM facts
            WHERE field_key = ? AND family IN (?, ?) AND report_date = ? AND value_num IS NOT NULL LIMIT 1
            """,
            [field_key, *CUMULATIVE_FAMILIES, previous_same_date],
        ).fetchone()
        if not previous_fy or not previous_same:
            raise ValueError("缺少上年年报或上年同期累计数据，无法可靠计算TTM")

        value = float(previous_fy[0]) - float(previous_same[0]) + float(current[1])
        components = [
            TTMComponent(previous_fy_date, float(previous_fy[0]), str(previous_fy[1]), "add_previous_fy"),
            TTMComponent(
                previous_same_date, float(previous_same[0]), str(previous_same[1]), "subtract_previous_same"
            ),
            TTMComponent(end_period, float(current[1]), str(current[2]), "add_current_cumulative"),
        ]
        formula = (
            f"{previous_fy_date}:{previous_fy[0]:g} - "
            f"{previous_same_date}:{previous_same[0]:g} + {end_period}:{current[1]:g}"
        )
        return TTMResult(
            field_key=field_key,
            field_name_cn=field_name,
            end_period=end_period,
            value=value,
            unit=unit,
            method="FY_MINUS_PRIOR_SAME_PLUS_CURRENT",
            formula=formula,
            components=components,
        )
    finally:
        connection.close()
