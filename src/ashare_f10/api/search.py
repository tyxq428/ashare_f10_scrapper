from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import threading
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import duckdb
from rapidfuzz.fuzz import WRatio

from ashare_f10.models import SearchColumnFilter, SearchQueryRequest, SearchStep

RESULT_COLUMNS = (
    "security_code",
    "theme",
    "family",
    "dataset",
    "report_date",
    "event_date",
    "field_key",
    "field_name_cn",
    "value_text",
    "value_num",
    "unit",
    "source_url",
)
TEXT_SEARCH_COLUMNS = (
    "field_name_cn",
    "field_key",
    "theme",
    "family",
    "dataset",
    "value_text",
    "unit",
    "source_url",
)
FILTER_COLUMNS = set(RESULT_COLUMNS) | {"effective_date", "score", "base_score", "secondary_score"}
SORT_COLUMNS = FILTER_COLUMNS
COLUMN_SQL = {
    **{column: column for column in RESULT_COLUMNS},
    "effective_date": "coalesce(report_date, event_date)",
}
NUMERIC_COLUMNS = {"value_num", "score", "base_score", "secondary_score"}
DATE_COLUMNS = {"report_date", "event_date", "effective_date"}
CACHE_MAX_ENTRIES = 6
CACHE_MAX_ROWS = 100_000
_CACHE: OrderedDict[str, tuple[list[dict[str, Any]], list[dict[str, Any]], int]] = OrderedDict()
_CACHE_LOCK = threading.Lock()


def _request_cache_key(db_path: Path | str, request: SearchQueryRequest) -> str:
    path = Path(db_path)
    payload = request.model_dump(mode="json")
    payload.pop("page", None)
    payload.pop("page_size", None)
    payload.pop("sort", None)
    raw = json.dumps(
        {"path": str(path.resolve()), "mtime": path.stat().st_mtime_ns, "request": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_column(column: str, allowed: set[str]) -> str:
    if column not in allowed:
        raise ValueError(f"不支持的搜索列：{column}")
    return column


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def _safe_regex(pattern: str) -> re.Pattern[str]:
    if len(pattern) > 100:
        raise ValueError("正则表达式不能超过100个字符")
    if re.search(r"\([^)]*[+*][^)]*\)[+*{]", pattern):
        raise ValueError("不允许可能导致超时的嵌套重复正则")
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"正则表达式无效：{exc}") from exc


def _selected_columns(columns: list[str]) -> list[str]:
    selected = columns or list(TEXT_SEARCH_COLUMNS)
    return [_validate_column(column, set(TEXT_SEARCH_COLUMNS)) for column in selected]


def _match_score(row: dict[str, Any], step: SearchStep) -> float | None:
    columns = _selected_columns(step.columns)
    values = [_as_text(row.get(column)) for column in columns]
    query = step.query.strip()

    if step.match_type == "empty":
        return 100.0 if any(value == "" for value in values) else None
    if step.match_type == "not_empty":
        return 100.0 if any(value != "" for value in values) else None
    if not query:
        return None

    query_lower = query.casefold()
    if step.match_type == "exact":
        return 100.0 if any(value.casefold() == query_lower for value in values) else None
    if step.match_type == "prefix":
        return 100.0 if any(value.casefold().startswith(query_lower) for value in values) else None
    if step.match_type == "contains":
        return 100.0 if any(query_lower in value.casefold() for value in values) else None
    if step.match_type == "regex":
        regex = _safe_regex(query)
        return 100.0 if any(regex.search(value) for value in values) else None

    score = max((float(WRatio(query, value)) for value in values), default=0.0)
    return score if score >= step.threshold else None


def _build_sql_filters(filters: list[SearchColumnFilter]) -> tuple[list[str], list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    for item in filters:
        if not item.enabled or item.column in {"score", "base_score", "secondary_score"}:
            continue
        column = _validate_column(item.column, FILTER_COLUMNS)
        expression = COLUMN_SQL[column]
        operator = item.operator

        if operator in {"in", "not_in"}:
            values = list(item.values)
            if not values:
                if operator == "in":
                    conditions.append("FALSE")
                continue
            placeholders = ",".join("?" for _ in values)
            keyword = "IN" if operator == "in" else "NOT IN"
            list_expression = (
                expression if column in NUMERIC_COLUMNS else f"coalesce(cast({expression} AS VARCHAR), '')"
            )
            conditions.append(f"{list_expression} {keyword} ({placeholders})")
            params.extend(values)
        elif operator in {"contains", "not_contains", "exact", "not_equal", "prefix"}:
            if column in NUMERIC_COLUMNS and operator in {"exact", "not_equal"}:
                comparator = "=" if operator == "exact" else "<>"
                conditions.append(f"{expression} {comparator} ?")
                params.append(item.value)
                continue
            text_expression = f"coalesce(cast({expression} AS VARCHAR), '')"
            value = _as_text(item.value)
            if operator == "contains":
                conditions.append(f"{text_expression} ILIKE ?")
                params.append(f"%{value}%")
            elif operator == "not_contains":
                conditions.append(f"{text_expression} NOT ILIKE ?")
                params.append(f"%{value}%")
            elif operator == "prefix":
                conditions.append(f"{text_expression} ILIKE ?")
                params.append(f"{value}%")
            elif operator == "exact":
                conditions.append(f"lower({text_expression}) = lower(?)")
                params.append(value)
            else:
                conditions.append(f"lower({text_expression}) <> lower(?)")
                params.append(value)
        elif operator in {"gte", "lte"}:
            comparator = ">=" if operator == "gte" else "<="
            conditions.append(f"{expression} {comparator} ?")
            params.append(item.value)
        elif operator == "between":
            conditions.append(f"{expression} BETWEEN ? AND ?")
            params.extend([item.lower, item.upper])
        elif operator == "is_empty":
            conditions.append(f"({expression} IS NULL OR cast({expression} AS VARCHAR) = '')")
        elif operator == "not_empty":
            conditions.append(f"({expression} IS NOT NULL AND cast({expression} AS VARCHAR) <> '')")
        else:  # pragma: no cover - guarded by pydantic Literal
            raise ValueError(f"不支持的筛选操作符：{operator}")
    return conditions, params


def _score_filters(rows: list[dict[str, Any]], filters: list[SearchColumnFilter]) -> list[dict[str, Any]]:
    score_filters = [
        item for item in filters if item.enabled and item.column in {"score", "base_score", "secondary_score"}
    ]
    if not score_filters:
        return rows

    def matches(row: dict[str, Any]) -> bool:
        for item in score_filters:
            value = row.get(item.column)
            if item.operator == "is_empty" and value is not None:
                return False
            if item.operator == "not_empty" and value is None:
                return False
            if value is None:
                return False
            numeric = float(value)
            if item.operator == "gte" and numeric < float(item.value):
                return False
            if item.operator == "lte" and numeric > float(item.value):
                return False
            if item.operator == "between" and not float(item.lower) <= numeric <= float(item.upper):
                return False
            if item.operator == "exact" and numeric != float(item.value):
                return False
            if item.operator == "not_equal" and numeric == float(item.value):
                return False
        return True

    return [row for row in rows if matches(row)]


def _fetch_scope(
    connection: duckdb.DuckDBPyConnection,
    filters: list[SearchColumnFilter],
) -> tuple[list[dict[str, Any]], int]:
    raw_total = int(connection.execute("SELECT count(*) FROM facts").fetchone()[0])
    conditions, params = _build_sql_filters(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT row_number() OVER () AS row_id, {", ".join(RESULT_COLUMNS)}
        FROM facts
        {where}
    """
    rows = connection.execute(sql, params).fetchall()
    columns = [item[0] for item in connection.description]
    return [dict(zip(columns, row, strict=True)) for row in rows], raw_total


def _apply_search_chain(
    scope: list[dict[str, Any]],
    request: SearchQueryRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stage_counts: list[dict[str, Any]] = []
    score_lists: dict[int, list[float]] = {int(row["row_id"]): [] for row in scope}
    base_scores: dict[int, float] = {}
    secondary_scores: dict[int, list[float]] = {}
    current = scope

    if request.base_query or request.base_match_type in {"empty", "not_empty"}:
        base_step = SearchStep(
            query=request.base_query,
            operation="include",
            match_type=request.base_match_type,
            columns=request.base_columns,
            threshold=request.base_threshold,
        )
        matched: list[dict[str, Any]] = []
        for row in current:
            score = _match_score(row, base_step)
            if score is not None:
                row_id = int(row["row_id"])
                base_scores[row_id] = score
                score_lists[row_id].append(score)
                matched.append(row)
        current = matched
        stage_counts.append(
            {
                "stage": "base_query",
                "label": request.base_query or request.base_match_type,
                "count": len(current),
            }
        )

    for index, step in enumerate(request.search_steps, 1):
        if not step.enabled:
            continue
        search_space = scope if step.operation == "or" else current
        matches: dict[int, tuple[dict[str, Any], float]] = {}
        for row in search_space:
            score = _match_score(row, step)
            if score is not None:
                matches[int(row["row_id"])] = (row, score)

        if step.operation == "include":
            current = [row for row in current if int(row["row_id"]) in matches]
        elif step.operation == "exclude":
            current = [row for row in current if int(row["row_id"]) not in matches]
        else:
            union = {int(row["row_id"]): row for row in current}
            union.update({row_id: pair[0] for row_id, pair in matches.items()})
            current = list(union.values())

        if step.operation != "exclude":
            for row_id, (_, score) in matches.items():
                score_lists.setdefault(row_id, []).append(score)
                secondary_scores.setdefault(row_id, []).append(score)

        stage_counts.append(
            {
                "stage": f"search_step_{index}",
                "label": f"{step.operation}:{step.query or step.match_type}",
                "count": len(current),
            }
        )

    output: list[dict[str, Any]] = []
    for row in current:
        row_id = int(row["row_id"])
        scores = score_lists.get(row_id, [])
        secondary = secondary_scores.get(row_id, [])
        item = dict(row)
        item["base_score"] = round(base_scores.get(row_id, 0.0), 4)
        item["secondary_score"] = round(sum(secondary) / len(secondary), 4) if secondary else 0.0
        item["score"] = round(sum(scores) / len(scores), 4) if scores else 0.0
        output.append(item)
    return output, stage_counts


def _get_scored_rows(
    db_path: Path | str,
    request: SearchQueryRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    key = _request_cache_key(db_path, request)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            rows, stages, raw_total = cached
            return [dict(row) for row in rows], [dict(stage) for stage in stages], raw_total

    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        scope, raw_total = _fetch_scope(connection, request.filters)
    finally:
        connection.close()

    stage_counts = [{"stage": "raw", "label": "原始事实记录", "count": raw_total}]
    if len(scope) != raw_total or any(item.enabled for item in request.filters):
        stage_counts.append({"stage": "column_filters", "label": "逐列筛选", "count": len(scope)})
    rows, search_stages = _apply_search_chain(scope, request)
    rows = _score_filters(rows, request.filters)
    stage_counts.extend(search_stages)
    if any(item.enabled and item.column in NUMERIC_COLUMNS for item in request.filters):
        stage_counts.append({"stage": "score_filters", "label": "匹配度筛选", "count": len(rows)})

    if len(rows) <= CACHE_MAX_ROWS:
        with _CACHE_LOCK:
            _CACHE[key] = ([dict(row) for row in rows], [dict(stage) for stage in stage_counts], raw_total)
            _CACHE.move_to_end(key)
            while len(_CACHE) > CACHE_MAX_ENTRIES:
                _CACHE.popitem(last=False)
    return rows, stage_counts, raw_total


def _sort_rows(rows: list[dict[str, Any]], request: SearchQueryRequest) -> list[dict[str, Any]]:
    output = list(rows)
    sorts = request.sort
    if not sorts:
        sorts = []
        if request.base_query or any(
            step.enabled and step.operation != "exclude" for step in request.search_steps
        ):
            from ashare_f10.models import SearchSort

            sorts.append(SearchSort(column="score", direction="desc"))
        from ashare_f10.models import SearchSort

        sorts.append(SearchSort(column="effective_date", direction="desc"))

    for item in reversed(sorts):
        column = _validate_column(item.column, SORT_COLUMNS)

        def value(row: dict[str, Any], selected_column: str = column) -> Any:
            if selected_column == "effective_date":
                return row.get("report_date") or row.get("event_date")
            return row.get(selected_column)

        non_empty = [row for row in output if value(row) is not None]
        empty = [row for row in output if value(row) is None]
        non_empty.sort(key=lambda row: value(row), reverse=item.direction == "desc")
        output = non_empty + empty
    return output


def query_facts(db_path: Path | str, request: SearchQueryRequest) -> dict[str, Any]:
    rows, stage_counts, raw_total = _get_scored_rows(db_path, request)
    rows = _sort_rows(rows, request)
    total = len(rows)
    start = (request.page - 1) * request.page_size
    page_rows = rows[start : start + request.page_size]
    for row in page_rows:
        row.pop("row_id", None)
    return {
        "raw_total": raw_total,
        "total": total,
        "page": request.page,
        "page_size": request.page_size,
        "page_count": (total + request.page_size - 1) // request.page_size,
        "stage_counts": stage_counts,
        "rows": page_rows,
    }


def facet_facts(
    db_path: Path | str,
    request: SearchQueryRequest,
    column: str,
    term: str = "",
    limit: int = 200,
) -> dict[str, Any]:
    column = _validate_column(column, FILTER_COLUMNS)
    cloned = request.model_copy(deep=True)
    cloned.filters = [item for item in cloned.filters if item.column != column]
    rows, _, _ = _get_scored_rows(db_path, cloned)

    def get_value(row: dict[str, Any]) -> Any:
        if column == "effective_date":
            return row.get("report_date") or row.get("event_date")
        return row.get(column)

    values = [get_value(row) for row in rows]
    if column in NUMERIC_COLUMNS:
        numeric = [float(value) for value in values if value is not None]
        return {
            "column": column,
            "kind": "numeric",
            "min": min(numeric) if numeric else None,
            "max": max(numeric) if numeric else None,
            "null_count": len(values) - len(numeric),
            "total": len(values),
        }

    term_lower = term.casefold()
    counts = Counter(_as_text(value) for value in values)
    items = [
        {"value": value, "count": count}
        for value, count in counts.items()
        if not term_lower or term_lower in value.casefold()
    ]
    items.sort(key=lambda item: (-item["count"], item["value"]))
    return {
        "column": column,
        "kind": "date" if column in DATE_COLUMNS else "text",
        "values": items[:limit],
        "truncated": len(items) > limit,
        "total_distinct": len(items),
        "total": len(values),
    }


def export_search_rows(
    db_path: Path | str,
    request: SearchQueryRequest,
    output_format: str = "csv",
    max_rows: int = 100_000,
) -> tuple[bytes, str, str]:
    rows, _, _ = _get_scored_rows(db_path, request)
    rows = _sort_rows(rows, request)[:max_rows]
    for row in rows:
        row.pop("row_id", None)

    if output_format == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        return content, "application/json", "search-results.json"

    buffer = io.StringIO()
    columns = [*RESULT_COLUMNS, "base_score", "secondary_score", "score"]
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", "search-results.csv"


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
    filters: list[SearchColumnFilter] = []
    if start_date or end_date:
        if start_date and end_date:
            filters.append(
                SearchColumnFilter(
                    column="effective_date", operator="between", lower=start_date, upper=end_date
                )
            )
        elif start_date:
            filters.append(SearchColumnFilter(column="effective_date", operator="gte", value=start_date))
        else:
            filters.append(SearchColumnFilter(column="effective_date", operator="lte", value=end_date))
    if theme:
        filters.append(SearchColumnFilter(column="theme", operator="exact", value=theme))
    if family:
        filters.append(SearchColumnFilter(column="family", operator="exact", value=family))
    if numeric_min is not None:
        filters.append(SearchColumnFilter(column="value_num", operator="gte", value=numeric_min))
    if numeric_max is not None:
        filters.append(SearchColumnFilter(column="value_num", operator="lte", value=numeric_max))

    request = SearchQueryRequest(base_query=query, filters=filters, page=1, page_size=limit)
    return query_facts(db_path, request)["rows"]


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
