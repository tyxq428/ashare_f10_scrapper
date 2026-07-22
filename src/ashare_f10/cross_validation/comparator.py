from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

import pandas as pd

from ashare_f10.cross_validation.models import ComparisonRecord, RegistryEntry
from ashare_f10.validation.point_in_time import normalize_date

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
NON_COMPARABLE_STATUSES = {
    "NOT_IN_OFFICIAL_SCOPE",
    "SOURCE_SPECIFIC",
    "FUTURE_FREE_SOURCE_REQUIRED",
    "OFFICIAL_PERIOD_NOT_LOADED",
    "OFFICIAL_SOURCE_UNAVAILABLE",
    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",
    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",
}
UNRESOLVED_STATUSES = {
    "MISSING_OFFICIAL",
    "MISSING_EASTMONEY",
    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
    "UNRESOLVED",
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


def _optional_float(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and math.isfinite(number) else None


def _normalize_report_label(text: str) -> str:
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
        try:
            return normalize_date(raw)
        except ValueError:
            pass
    text = re.sub(r"[\s\u3000]+", "", raw)
    text = text.replace("（", "(").replace("）", ")").replace("，", ",")
    if field_key in {"REPORT_TYPE", "REPORT_DATE_NAME"}:
        return _normalize_report_label(text)
    if field_key == "SECURITY_CODE":
        digits = re.sub(r"\D", "", text)
        return digits[-6:] if len(digits) >= 6 else text
    return text


def _normalize_set(value: Any, field_key: str = "") -> set[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return set()
    result: set[str] = set()
    for token in re.split(r"[,，;；、|\n]+", str(value)):
        normalized = _normalize_text(token, field_key)
        if normalized:
            result.add(normalized)
    return result


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
    keys = ["security_code", "family", "dataset", "record_key", "field_key"]
    work = work.drop_duplicates(keys, keep="first")
    return work.drop(columns=["_family_priority", "_has_numeric"])


def _policy(entry: RegistryEntry, official_row: Mapping[str, Any] | None = None) -> dict[str, Any]:
    method = str(entry.comparison_method or "auto")
    if method == "auto":
        method = "numeric" if official_row and _number(official_row.get("value_num")) is not None else "text"
    official_precision = _optional_float(official_row.get("precision_tolerance")) if official_row else None
    configured_absolute = _optional_float(entry.absolute_tolerance)
    absolute = max(
        [value for value in (official_precision, configured_absolute) if value is not None] or [0.0]
    )
    relative = _optional_float(entry.relative_tolerance) or 0.0
    return {
        "method": method,
        "canonical_unit": str(entry.canonical_unit or ""),
        "absolute_tolerance": absolute,
        "relative_tolerance": relative,
        "display_decimals": entry.display_decimals,
    }


def _numeric_match(
    east_value: float,
    official_value: float,
    entry: RegistryEntry,
    official_row: Mapping[str, Any],
) -> tuple[str, str, float, float, float, float]:
    difference = east_value - official_value
    relative = _relative(east_value, official_value)
    policy = _policy(entry, official_row)
    absolute_tolerance = float(policy["absolute_tolerance"])
    relative_tolerance = float(policy["relative_tolerance"])
    allowed = max(
        absolute_tolerance,
        max(abs(east_value), abs(official_value)) * relative_tolerance,
    )
    if difference == 0:
        status = "DERIVED_MATCH" if entry.validation_mode == "OFFICIAL_DERIVED" else "EXACT_MATCH"
        return status, "VALUE_MATCH", difference, relative, allowed, relative_tolerance
    if abs(difference) <= allowed:
        status = "DERIVED_MATCH" if entry.validation_mode == "OFFICIAL_DERIVED" else "WITHIN_ROUNDING"
        return status, "WITHIN_CONFIGURED_TOLERANCE", difference, relative, allowed, relative_tolerance
    return "MISMATCH", "OUTSIDE_CONFIGURED_TOLERANCE", difference, relative, allowed, relative_tolerance


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
        report_date = str(eastmoney.get("report_date") or "")[:10]
        period_type = str(eastmoney.get("period_type") or "")
        field_key = str(eastmoney.get("field_key") or "")
        statement = entry.statement_type or str(eastmoney.get("statement_type") or "")

        candidates = index.get((code, report_date, period_type, statement, field_key), [])
        if candidates:
            preferred = [row for row in candidates if str(row.get("scope") or "") != "parent"]
            if entry.scope == "consolidated" and not preferred:
                return None, "SCOPE_CONFLICT"
            return (preferred or candidates)[0], None

        primary_statement_families = {
            "RPT_F10_FINANCE_GBALANCE",
            "RPT_F10_FINANCE_GINCOME",
            "RPT_F10_FINANCE_GCASHFLOW",
        }
        family = str(eastmoney.get("family") or "")
        if family in primary_statement_families and entry.validation_mode == "OFFICIAL_DIRECT":
            return None, None
        if family == "RPT_F10_BUSINESS_RDEXPENSE" and field_key == "RESEARCH_EXPENSE":
            return None, None

        same_period_key = [
            row
            for lookup, rows in index.items()
            if lookup[0] == code
            and lookup[1] == report_date
            and lookup[2] == period_type
            and lookup[4] == field_key
            for row in rows
        ]
        if field_key == "FINANCE_EXPENSE" and entry.validation_mode == "OFFICIAL_DERIVED" and same_period_key:
            income_candidates = [
                row for row in same_period_key if str(row.get("statement_type") or "") == "income_statement"
            ]
            if income_candidates:
                preferred = [row for row in income_candidates if str(row.get("scope") or "") != "parent"]
                return (preferred or income_candidates)[0], None

        if same_period_key:
            preferred = [row for row in same_period_key if str(row.get("scope") or "") != "parent"]
            if entry.scope == "consolidated" and not preferred:
                return None, "SCOPE_CONFLICT"
            return (preferred or same_period_key)[0], None

        same_date_key = [
            row
            for lookup, rows in index.items()
            if lookup[0] == code and lookup[1] == report_date and lookup[4] == field_key
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
            root_cause = ""
            notes = entry.reason
            difference = relative = tolerance = relative_tolerance = None
            official_value_num = official_value_text = official_unit = None
            source_document = source_url = source_row = ""
            source_page = None
            comparison_method = entry.comparison_method or "auto"

            if mode == "NOT_IN_PERIODIC_REPORT_SCOPE":
                status, grade, root_cause = "NOT_IN_OFFICIAL_SCOPE", "N/A", "NOT_PERIODIC_DISCLOSURE"
            elif mode == "EASTMONEY_SOURCE_SPECIFIC":
                status, grade, root_cause = "SOURCE_SPECIFIC", "D", "EASTMONEY_SPECIFIC_METRIC"
            elif mode == "FUTURE_FREE_SOURCE_REQUIRED":
                status, grade, root_cause = (
                    "FUTURE_FREE_SOURCE_REQUIRED",
                    "D",
                    "FREE_OFFICIAL_SOURCE_NOT_ROUTED",
                )
            elif period_not_loaded:
                status, grade, root_cause = (
                    "OFFICIAL_PERIOD_NOT_LOADED",
                    "N/A",
                    "REPORT_PERIOD_NOT_LOADED",
                )
                notes = f"{notes}；当前验证批次未加载该报告期的官方报告，不参与一致性判断"
            elif official_row is None:
                status = diagnostic or "MISSING_OFFICIAL"
                grade = "E"
                root_cause = diagnostic or "OFFICIAL_VALUE_NOT_EXTRACTED"
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
                policy = _policy(entry, official_row)
                comparison_method = str(policy["method"])
                tolerance = float(policy["absolute_tolerance"])
                relative_tolerance = float(policy["relative_tolerance"])

                east_num, east_unit = _normalize_numeric(
                    _number(east.get("value_num")), str(east.get("unit") or "")
                )
                official_num, official_unit = _normalize_numeric(official_value_num, official_unit)
                if (
                    comparison_method == "text"
                    and mode == "OFFICIAL_DERIVED"
                    and east_num is not None
                    and official_num is not None
                ):
                    comparison_method = "numeric"
                is_text_method = comparison_method in {"date", "text", "set"}
                if east_num is not None and official_num is not None and not is_text_method:
                    if east_unit.lower() in {"", "文本", "text", "none"}:
                        east_unit = official_unit
                    if official_unit.lower() in {"", "文本", "text", "none"}:
                        official_unit = east_unit
                    if east_unit and official_unit and east_unit != official_unit:
                        status, grade, root_cause = "UNIT_CONFLICT", "E", "NORMALIZED_UNIT_MISMATCH"
                    else:
                        (
                            status,
                            root_cause,
                            difference,
                            relative,
                            tolerance,
                            relative_tolerance,
                        ) = _numeric_match(east_num, official_num, entry, official_row)
                        grade = "A" if status in MATCH_STATUSES else "E"
                        if status == "MISMATCH" and east_num == 0 and official_num != 0:
                            notes = (
                                f"{notes}；东方财富明确返回0，但免费官方正式披露为非零；"
                                "保留为可追溯来源冲突，不自动覆盖或隐藏"
                            )
                else:
                    field_key = str(east.get("field_key") or "")
                    east_raw = east.get("value_text")
                    official_raw = official_value_text
                    if comparison_method == "date":
                        try:
                            east_text = normalize_date(str(east_raw or ""))
                            official_text = normalize_date(str(official_raw or ""))
                        except ValueError:
                            east_text = _normalize_text(east_raw, field_key)
                            official_text = _normalize_text(official_raw, field_key)
                        status = "TEXT_MATCH_NORMALIZED" if east_text and east_text == official_text else "MISMATCH"
                    elif comparison_method == "set":
                        east_set = _normalize_set(east_raw, field_key)
                        official_set = _normalize_set(official_raw, field_key)
                        status = "SET_MATCH" if east_set and east_set == official_set else "MISMATCH"
                    else:
                        east_text = _normalize_text(east_raw, field_key)
                        official_text = _normalize_text(official_raw, field_key)
                        if not east_text and (official_num is not None or official_text):
                            status = "MISSING_EASTMONEY"
                        elif east_text and not official_text and official_num is None:
                            status = "MISSING_OFFICIAL"
                        elif east_text and official_text and east_text == official_text:
                            status = "TEXT_MATCH_NORMALIZED"
                        else:
                            status = "MISMATCH"
                    grade = "A" if status in MATCH_STATUSES else "E"
                    root_cause = (
                        "NORMALIZED_VALUE_MATCH"
                        if status in MATCH_STATUSES
                        else "EASTMONEY_VALUE_MISSING"
                        if status == "MISSING_EASTMONEY"
                        else "OFFICIAL_VALUE_NOT_EXTRACTED"
                        if status == "MISSING_OFFICIAL"
                        else "NORMALIZED_VALUE_MISMATCH"
                    )

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
                comparison_method=comparison_method,
                root_cause=root_cause,
                absolute_tolerance=tolerance,
                relative_tolerance=relative_tolerance,
            )
            records.append(item.to_dict())

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
                    comparison_method="official_only",
                    root_cause="EASTMONEY_VALUE_MISSING",
                    absolute_tolerance=_number(row.get("precision_tolerance")),
                    relative_tolerance=None,
                ).to_dict()
            )
        return pd.DataFrame(records)

    @staticmethod
    def summary(frame: pd.DataFrame) -> dict[str, Any]:
        status_counts = Counter(frame.get("status", []))
        root_cause_counts = Counter(frame.get("root_cause", []))
        if frame.empty:
            return {
                "status_counts": {},
                "root_cause_counts": {},
                "comparison_count": 0,
                "comparable_count": 0,
                "matched_count": 0,
                "true_conflict_count": 0,
                "attempted_comparison_count": 0,
                "comparison_coverage": None,
                "comparison_accuracy": None,
                "comparable_match_rate": None,
                "comparable_match_rate_deprecated": True,
                "target_extraction_coverage": None,
                "evidence_completeness": None,
                "unresolved_rate": None,
                "manual_review_required": False,
            }
        eligible = frame[~frame["status"].isin(NON_COMPARABLE_STATUSES)]
        attempted = frame[frame["status"].isin(MATCH_STATUSES | TRUE_CONFLICT_STATUSES)]
        matched = frame[frame["status"].isin(MATCH_STATUSES)]
        true_conflicts = int(frame["status"].isin(TRUE_CONFLICT_STATUSES).sum())
        unresolved = frame[frame["status"].isin(UNRESOLVED_STATUSES)]
        official_observed = eligible[eligible["status"] != "MISSING_OFFICIAL"]

        source_document = attempted.get(
            "source_document", pd.Series("", index=attempted.index, dtype="object")
        ).fillna("")
        source_url = attempted.get(
            "source_url", pd.Series("", index=attempted.index, dtype="object")
        ).fillna("")
        source_page = attempted.get(
            "source_page", pd.Series(None, index=attempted.index, dtype="object")
        )
        source_row = attempted.get(
            "source_row", pd.Series("", index=attempted.index, dtype="object")
        ).fillna("")
        evidence_complete = attempted[
            source_document.astype(str).ne("")
            & source_url.astype(str).ne("")
            & (source_page.notna() | source_row.astype(str).ne(""))
        ]
        comparison_accuracy = None if len(attempted) == 0 else len(matched) / len(attempted)
        return {
            "status_counts": dict(status_counts),
            "root_cause_counts": {key: value for key, value in root_cause_counts.items() if key},
            "comparison_count": len(frame),
            "comparable_count": len(eligible),
            "matched_count": len(matched),
            "true_conflict_count": true_conflicts,
            "attempted_comparison_count": len(attempted),
            "comparison_coverage": None if len(eligible) == 0 else len(attempted) / len(eligible),
            "comparison_accuracy": comparison_accuracy,
            "comparable_match_rate": comparison_accuracy,
            "comparable_match_rate_deprecated": True,
            "target_extraction_coverage": (
                None if len(eligible) == 0 else len(official_observed) / len(eligible)
            ),
            "evidence_completeness": (
                None if len(attempted) == 0 else len(evidence_complete) / len(attempted)
            ),
            "unresolved_rate": None if len(eligible) == 0 else len(unresolved) / len(eligible),
            "manual_review_required": bool(true_conflicts),
        }
