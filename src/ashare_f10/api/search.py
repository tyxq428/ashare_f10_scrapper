from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
from rapidfuzz.fuzz import WRatio


def search_facts(
    db_path: Path | str,
    query: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
    theme: str | None = None,
    family: str | None = None,
    numeric_min: float | None = None,
    numeric_max: float | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        conditions = ["1=1"]
        params: list[Any] = []
        if query:
            like = f"%{query}%"
            conditions.append(
                "(field_name_cn ILIKE ? OR field_key ILIKE ? OR theme ILIKE ? OR dataset ILIKE ? OR value_text ILIKE ?)"
            )
            params.extend([like, like, like, like, like])
        if start_date:
            conditions.append("coalesce(report_date, event_date) >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("coalesce(report_date, event_date) <= ?")
            params.append(end_date)
        if theme:
            conditions.append("theme = ?")
            params.append(theme)
        if family:
            conditions.append("family = ?")
            params.append(family)
        if numeric_min is not None:
            conditions.append("value_num >= ?")
            params.append(numeric_min)
        if numeric_max is not None:
            conditions.append("value_num <= ?")
            params.append(numeric_max)

        sql = f"""
            SELECT security_code, theme, family, dataset, report_date, event_date,
                   field_key, field_name_cn, value_text, value_num, unit, source_url
            FROM facts
            WHERE {' AND '.join(conditions)}
            ORDER BY coalesce(report_date, event_date) DESC NULLS LAST
            LIMIT ?
        """
        params.append(max(limit * 3 if query else limit, limit))
        rows = connection.execute(sql, params).fetchall()
        columns = [item[0] for item in connection.description]
        results = [dict(zip(columns, row, strict=True)) for row in rows]
        if query:
            for result in results:
                result["score"] = max(
                    WRatio(query, str(result.get("field_name_cn", ""))),
                    WRatio(query, str(result.get("field_key", ""))),
                    WRatio(query, str(result.get("theme", ""))),
                    WRatio(query, str(result.get("dataset", ""))),
                )
            results.sort(key=lambda item: (item["score"], item.get("report_date") or ""), reverse=True)
        return results[:limit]
    finally:
        connection.close()


def list_fields(db_path: Path | str, query: str = "", limit: int = 200) -> list[dict[str, Any]]:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        like = f"%{query}%"
        rows = connection.execute(
            """
            SELECT field_key, field_name_cn, coalesce(unit, ''),
                   count(*) AS observations,
                   min(report_date) AS min_date,
                   max(report_date) AS max_date
            FROM facts
            WHERE (? = '' OR field_name_cn ILIKE ? OR field_key ILIKE ?)
            GROUP BY field_key, field_name_cn, unit
            ORDER BY observations DESC, field_name_cn
            LIMIT ?
            """,
            [query, like, like, limit],
        ).fetchall()
        return [
            {
                "field_key": row[0],
                "field_name_cn": row[1],
                "unit": row[2],
                "observations": row[3],
                "min_date": str(row[4])[:10] if row[4] else None,
                "max_date": str(row[5])[:10] if row[5] else None,
            }
            for row in rows
        ]
    finally:
        connection.close()


def list_periods(db_path: Path | str) -> list[str]:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = connection.execute(
            "SELECT DISTINCT report_date FROM facts WHERE report_date IS NOT NULL ORDER BY report_date DESC"
        ).fetchall()
        return [str(row[0])[:10] for row in rows]
    finally:
        connection.close()


def overview(db_path: Path | str) -> dict[str, Any]:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        stats = connection.execute(
            """
            SELECT count(*) AS facts,
                   count(DISTINCT field_key) AS fields,
                   count(DISTINCT family) AS families,
                   min(report_date) AS min_report_date,
                   max(report_date) AS max_report_date
            FROM facts
            """
        ).fetchone()
        latest = connection.execute(
            """
            SELECT field_key, field_name_cn, value_num, value_text, unit, report_date, family
            FROM latest_numeric
            WHERE field_key IN (
                'TOTAL_OPERATE_INCOME','PARENT_NETPROFIT','TOTAL_ASSETS','TOTAL_LIABILITIES',
                'MONETARYFUNDS','ACCOUNTS_RECE','INVENTORY','NETCASH_OPERATE','ROEJQ','ZCFZL'
            )
            ORDER BY field_key
            """
        ).fetchall()
        return {
            "fact_count": stats[0],
            "field_count": stats[1],
            "family_count": stats[2],
            "min_report_date": str(stats[3])[:10] if stats[3] else None,
            "max_report_date": str(stats[4])[:10] if stats[4] else None,
            "latest_metrics": [
                {
                    "field_key": row[0],
                    "field_name_cn": row[1],
                    "value_num": row[2],
                    "value_text": row[3],
                    "unit": row[4],
                    "report_date": str(row[5])[:10] if row[5] else None,
                    "family": row[6],
                }
                for row in latest
            ],
        }
    finally:
        connection.close()
