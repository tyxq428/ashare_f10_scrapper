from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

import pandas as pd

from ashare_f10.cross_validation.models import ComparisonRecord, RegistryEntry

TRUE_CONFLICT_STATUSES = {
    "MISMATCH",
    "VERSION_CONFLICT",
    "SCOPE_CONFLICT",
    "PERIOD_CONFLICT",
    "UNIT_CONFLICT",
}
MATCH_STATUSES = {
    "EXACT_MATCH",
    "WITHIN_ROUNDING",
    "DERIVED_MATCH",
    "TEXT_MATCH_NORMALIZED",
    "SET_MATCH",
}

FAMILY_PRIORITY = {
    "RPT_F10_FINANCE_GBALANCE": 0,
    "RPT_F10_FINANCE_GINCOME": 0,
    "RPT_F10_FINANCE_GCASHFLOW": 0,
    "RPT_F10_FINANCE_GINCOMEQC": 1,
    "RPT_F10_FINANCE_GCASHFLOWQC": 1,
    "RPT_F10_FINANCE_MAINFINADATA": 2,
    "RPT_F10_QTR_MAINFINADATA": 2,
    "RPT_F10_FINANCE_GRATIO": 3,
    "RPT_F10_FINANCE_QGRATIO": 3,
    "RPT_F10_FINANCE_DUPONT": 4,
}

UNIT_SCALES = {
    "元": 1.0,
    "千元": 1_000.0,
    "万元": 10_000.0,
    "亿元": 100_000_000.0,
}


def _text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value)


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_report_label(text: str) -> str:
    """Normalize report labels without conflating cumulative and single-quarter periods."""
    if not text:
        return ""
    if any(token in text for token in ("四季度", "第4季度", "第四季度", "q4")):
        return "q4"
    if any(token in text for token in ("三季度", "第3季度", "第三季度", "q3")):
        return "q3"
    if any(token in text for token in ("二季度", "第2季度", "第二季度", "q2")):
        return "q2"
    if any(token in text for token in ("一季度", "第1季度", "第一季度", "一季报", "q1")):
        return "q1"
    if any(token in text for token in ("半年度", "半年报", "中报", "h1")):
        return "h1"
    if any(token in text for token in ("三季报", "前三季度", "q3c")):
        return "q3c"
    if any(token in text for token in ("年度报告", "年报", "年度", "fy")):
        return "fy"
    return text


def _normalize_text(value: Any, field_key: str = "") -> str:
    raw = str(value or "").strip().lower()
    if field_key in {"REPORT_DATE", "NOTICE_DATE", "PUBLISH_DATE", "UPDATE_DATE"}:
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
        if date_match:
            return date_match.group(0)
    text = re.sub(r"[\s\u3000]+", "", raw)
    text = text.replace("（", "(").replace("）", ")").replace("，", ",")
    if field_key in {"REPORT_TYPE", "REPORT_DATE_NAME"}:
        return _normalize_report_label(text)
    if field_key == "SECURITY_CODE":
        digits = re.sub(r"\D", "", text)
        return digits[-6:] if len(digits) >= 6 else text
    if field_key == "SECUCODE":
        return text.replace("sh", "sh").replace("sz", "sz").replace("bj", "bj")
    return text


def _normalize_numeric(value: float | None, unit: str) -> tuple[float | None, str]:
    if value is None:
        return None, unit
    clean_unit = str(unit or "").strip()
    if clean_unit in UNIT_SCALES:
        return value * UNIT_SCALES[clean_unit], "元"
    return value, clean_unit


def _relative(left: float, right: float) -> float:
    denominator = max(abs(left), abs(right))
    return 0.0 if denominator == 0 else abs(left - right) / denominator


def _comparison_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        str(row.get(column) or "")
        for column in (
            "security_code",
            "report_date",
            "event_date",
            "period_type",
            "family",
            "dataset",
            "record_key",
            "field_key",
        )
    )


def canonical_eastmoney_facts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    work = frame.copy()
    work["_family_priority"] = work["family"].map(FAMILY_PRIORITY).fillna(100)
    work["_has_numeric"] = work["value_num"].notna().astype(int)
    work = work.sort_values(
        [
            "security_code",
            "report_date",
            "event_date",
            "field_key",
            "_family_priority",
            "_has_numeric",
        ],
        ascending=[True, True, True, True, True, False],
        na_position="last",
    )
    # Financial families have duplicate values in summary endpoints. Keep one authoritative row
    # per family/context; event records retain their record key.
    keys = ["security_code", "family", "dataset", "record_key", "field_key"]
    work = work.drop_duplicates(keys, keep="first")
    return work.drop(columns=["_family_priority", "_has_numeric"])


class CrossSourceComparator:
    def __init__(self, registry_frame: pd.DataFrame) -> None:
        self.registry = {
            (
                str(row.theme),
                str(row.family),
                str(row.dataset),
                str(row.field_key),
            ): RegistryEntry(**row._asdict())
            for row in registry_frame.itertuples(index=False)
        }

    def _entry(self, row: Mapping[str, Any]) -> RegistryEntry:
        key = (
            str(row.get("theme") or ""),
            str(row.get("family") or ""),
            str(row.get("dataset") or ""),
            str(row.get("field_key") or ""),
        )
        return self.registry[key]

    @staticmethod
    def _official_index(
        official: pd.DataFrame,
    ) -> dict[tuple[str, str, str, str, str], list[dict[str, Any]]]:
        index: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
        for row in official.to_dict("records"):
            key = (
                str(row.get("security_code") or ""),
                str(row.get("report_date") or "")[:10],
                str(row.get("period_type") or ""),
                str(row.get("statement_type") or ""),
                str(row.get("field_key") or ""),
            )
            index.setdefault(key, []).append(row)
        return index

    @staticmethod
    def _find_official(
        index: dict[tuple[str, str, str, str, str], list[dict[str, Any]]],
        eastmoney: Mapping[str, Any],
        entry: RegistryEntry,
    ) -> tuple[dict[str, Any] | None, str | None]:
        code = str(eastmoney.get("security_code") or "")
        date = str(eastmoney.get("report_date") or "")[:10]
        period_type = str(eastmoney.get("period_type") or "")
        field_key = str(eastmoney.get("field_key") or "")
        statement = entry.statement_type or str(eastmoney.get("statement_type") or "")

        candidates = index.get((code, date, period_type, statement, field_key), [])
        if candidates:
            preferred = [row for row in candidates if str(row.get("scope") or "") != "parent"]
            if entry.scope == "consolidated" and not preferred:
                return None, "SCOPE_CONFLICT"
            return (preferred or candidates)[0], None

        # Summary, cash-flow supplements and ratio endpoints can repeat a canonical
        # fact whose authoritative official location is another statement. Permit a
        # same-period, same-key fallback across statement types, but never across
        # reporting periods. This prevents an FY cumulative amount from being
        # compared with a Q4 single-quarter amount.
        same_period_key = [
            row
            for lookup, rows in index.items()
            if lookup[0] == code and lookup[1] == date and lookup[2] == period_type and lookup[4] == field_key
            for row in rows
        ]
        if same_period_key:
            preferred = [row for row in same_period_key if str(row.get("scope") or "") != "parent"]
            if entry.scope == "consolidated" and not preferred:
                return None, "SCOPE_CONFLICT"
            return (preferred or same_period_key)[0], None

        # A fact in the same report date and field but under a different period type
        # is a real cumulative/single-quarter conflict.  Merely having the same key in
        # another year is not a period conflict; that is simply not yet extracted.
        same_date_key = [
            row
            for lookup, rows in index.items()
            if lookup[0] == code and lookup[1] == date and lookup[4] == field_key
            for row in rows
        ]
        if same_date_key and entry.validation_mode not in {
            "OFFICIAL_DERIVED",
            "OFFICIAL_METADATA",
        }:
            return None, "PERIOD_CONFLICT"
        return None, None

    def compare(self, eastmoney: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
        eastmoney = canonical_eastmoney_facts(eastmoney)
        official_index = self._official_index(official)
        official_dates = {
            str(value)[:10]
            for value in official.get("report_date", pd.Series(dtype="object"))
            if value not in (None, "") and not pd.isna(value)
        }
        records: list[dict[str, Any]] = []
        matched_official_identities: set[tuple[str, str, str, str, str, str]] = set()

        for east in eastmoney.to_dict("records"):
            entry = self._entry(east)
            mode = entry.validation_mode
            official_row: dict[str, Any] | None = None
            diagnostic: str | None = None
            report_date = str(east.get("report_date") or "")[:10]
            period_not_loaded = bool(
                entry.expected_official
                and report_date
                and official_dates
                and report_date not in official_dates
            )
            if entry.expected_official and not period_not_loaded:
                official_row, diagnostic = self._find_official(official_index, east, entry)

            status: str
            grade: str
            notes = entry.reason
            difference = relative = tolerance = None
            official_value_num = official_value_text = official_unit = None
            source_document = source_url = source_row = ""
            source_page = None

            if mode == "NOT_IN_PERIODIC_REPORT_SCOPE":
                status, grade = "NOT_IN_OFFICIAL_SCOPE", "N/A"
            elif mode == "EASTMONEY_SOURCE_SPECIFIC":
                status, grade = "SOURCE_SPECIFIC", "D"
            elif mode == "FUTURE_FREE_SOURCE_REQUIRED":
                status, grade = "FUTURE_FREE_SOURCE_REQUIRED", "D"
            elif period_not_loaded:
                status, grade = "OFFICIAL_PERIOD_NOT_LOADED", "N/A"
                notes = f"{notes}；当前验证批次未加载该报告期的官方报告，不参与一致性判断"
            elif official_row is None:
                status = diagnostic or "MISSING_OFFICIAL"
                grade = "E"
                notes = f"{notes}；当前官方事实集中未找到可比值"
            else:
                identity = (
                    str(official_row.get("security_code") or ""),
                    str(official_row.get("report_date") or ""),
                    str(official_row.get("period_type") or ""),
                    str(official_row.get("statement_type") or ""),
                    str(official_row.get("scope") or ""),
                    str(official_row.get("field_key") or ""),
                )
                matched_official_identities.add(identity)
                official_value_num = _number(official_row.get("value_num"))
                official_value_text = _text(official_row.get("value_text"))
                official_unit = str(official_row.get("normalized_unit") or official_row.get("unit") or "")
                source_document = str(official_row.get("source_document") or "")
                source_url = str(official_row.get("source_url") or "")
                source_page = (
                    int(official_row["source_page"]) if pd.notna(official_row.get("source_page")) else None
                )
                source_row = str(official_row.get("source_row") or "")
                east_num, east_unit = _normalize_numeric(
                    _number(east.get("value_num")), str(east.get("unit") or "")
                )
                official_num, official_unit = _normalize_numeric(official_value_num, official_unit)
                if east_num is not None and official_num is not None:
                    if east_unit and official_unit and east_unit != official_unit:
                        status, grade = "UNIT_CONFLICT", "E"
                    else:
                        difference = east_num - official_num
                        relative = _relative(east_num, official_num)
                        tolerance = _number(official_row.get("precision_tolerance")) or 1.0
                        if abs(difference) <= 1.0:
                            status, grade = (
                                ("DERIVED_MATCH", "B") if mode == "OFFICIAL_DERIVED" else ("EXACT_MATCH", "A")
                            )
                        elif abs(difference) <= tolerance:
                            status, grade = "WITHIN_ROUNDING", "A"
                        else:
                            status, grade = "MISMATCH", "E"
                else:
                    field_key = str(east.get("field_key") or "")
                    east_text = _normalize_text(east.get("value_text"), field_key)
                    official_text = _normalize_text(official_value_text, field_key)
                    if not east_text and (official_num is not None or official_text):
                        status, grade = "MISSING_EASTMONEY", "E"
                    elif east_text and not official_text and official_num is None:
                        status, grade = "MISSING_OFFICIAL", "E"
                    elif east_text and official_text and east_text == official_text:
                        status, grade = "TEXT_MATCH_NORMALIZED", "A"
                    else:
                        status, grade = "MISMATCH", "E"

            item = ComparisonRecord(
                comparison_key=_comparison_key(east),
                security_code=str(east.get("security_code") or ""),
                report_date=_text(east.get("report_date")),
                event_date=_text(east.get("event_date")),
                period_type=str(east.get("period_type") or ""),
                statement_type=entry.statement_type or str(east.get("statement_type") or ""),
                scope=entry.scope or str(east.get("scope") or ""),
                theme=str(east.get("theme") or ""),
                family=str(east.get("family") or ""),
                dataset=str(east.get("dataset") or ""),
                field_key=str(east.get("field_key") or ""),
                field_name_cn=str(east.get("field_name_cn") or east.get("field_key") or ""),
                validation_mode=mode,
                eastmoney_value_num=_number(east.get("value_num")),
                eastmoney_value_text=_text(east.get("value_text")),
                eastmoney_unit=str(east.get("unit") or ""),
                official_value_num=official_value_num,
                official_value_text=official_value_text,
                official_unit=official_unit or "",
                difference=difference,
                relative_difference=relative,
                tolerance=tolerance,
                status=status,  # type: ignore[arg-type]
                verification_grade=grade,
                source_document=source_document,
                source_url=source_url,
                source_page=source_page,
                source_row=source_row,
                eastmoney_source_url=str(east.get("source_url") or ""),
                notes=notes,
            )
            records.append(item.to_dict())

        # Official-only facts are useful because an omission in Eastmoney must not disappear.
        for row in official.to_dict("records"):
            identity = (
                str(row.get("security_code") or ""),
                str(row.get("report_date") or ""),
                str(row.get("period_type") or ""),
                str(row.get("statement_type") or ""),
                str(row.get("scope") or ""),
                str(row.get("field_key") or ""),
            )
            if identity in matched_official_identities:
                continue
            comparison_key = "|".join((*identity, "OFFICIAL_ONLY"))
            records.append(
                ComparisonRecord(
                    comparison_key=comparison_key,
                    security_code=identity[0],
                    report_date=identity[1] or None,
                    event_date=None,
                    period_type=identity[2],
                    statement_type=identity[3],
                    scope=identity[4],
                    theme=str(row.get("theme") or "官方披露"),
                    family="OFFICIAL_DISCLOSURE",
                    dataset=str(row.get("source_document") or ""),
                    field_key=identity[5],
                    field_name_cn=str(row.get("field_name_cn") or identity[5]),
                    validation_mode="OFFICIAL_DIRECT",
                    eastmoney_value_num=None,
                    eastmoney_value_text=None,
                    eastmoney_unit="",
                    official_value_num=_number(row.get("value_num")),
                    official_value_text=_text(row.get("value_text")),
                    official_unit=str(row.get("normalized_unit") or row.get("unit") or ""),
                    difference=None,
                    relative_difference=None,
                    tolerance=_number(row.get("precision_tolerance")),
                    status="MISSING_EASTMONEY",
                    verification_grade="E",
                    source_document=str(row.get("source_document") or ""),
                    source_url=str(row.get("source_url") or ""),
                    source_page=int(row["source_page"]) if pd.notna(row.get("source_page")) else None,
                    source_row=str(row.get("source_row") or ""),
                    notes="官方报告存在该事实，但东方财富标准事实表未找到对应值",
                ).to_dict()
            )
        return pd.DataFrame(records)

    @staticmethod
    def summary(frame: pd.DataFrame) -> dict[str, Any]:
        status_counts = Counter(frame.get("status", []))
        comparable = frame[
            ~frame["status"].isin(
                [
                    "NOT_IN_OFFICIAL_SCOPE",
                    "SOURCE_SPECIFIC",
                    "FUTURE_FREE_SOURCE_REQUIRED",
                    "OFFICIAL_PERIOD_NOT_LOADED",
                ]
            )
        ]
        matched = comparable[
            comparable["status"].isin(
                [
                    "EXACT_MATCH",
                    "WITHIN_ROUNDING",
                    "DERIVED_MATCH",
                    "TEXT_MATCH_NORMALIZED",
                    "SET_MATCH",
                ]
            )
        ]
        true_conflicts = int(frame["status"].isin(TRUE_CONFLICT_STATUSES).sum())
        return {
            "status_counts": dict(status_counts),
            "comparison_count": len(frame),
            "comparable_count": len(comparable),
            "matched_count": len(matched),
            "comparable_match_rate": None if len(comparable) == 0 else len(matched) / len(comparable),
            "true_conflict_count": true_conflicts,
            "manual_review_required": bool(true_conflicts),
        }
