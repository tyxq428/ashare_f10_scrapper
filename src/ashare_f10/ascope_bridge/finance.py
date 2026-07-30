from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd

UNIT_SCALES = {
    "": 1.0,
    "元": 1.0,
    "人民币元": 1.0,
    "千元": 1_000.0,
    "万元": 10_000.0,
    "亿元": 100_000_000.0,
}


class IndustryTemplate(StrEnum):
    INDUSTRIAL = "INDUSTRIAL"
    BANK = "BANK"
    INSURANCE = "INSURANCE"
    SECURITIES = "SECURITIES"
    OTHER_FINANCIAL = "OTHER_FINANCIAL"


FINANCIAL_TEMPLATES = {
    IndustryTemplate.BANK,
    IndustryTemplate.INSURANCE,
    IndustryTemplate.SECURITIES,
    IndustryTemplate.OTHER_FINANCIAL,
}


@dataclass(frozen=True, slots=True)
class FieldSpec:
    target: str
    keys: tuple[str, ...]
    semantics: str
    annual: bool = True
    quarterly: bool = True
    not_applicable: frozenset[IndustryTemplate] = frozenset()


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("revenue", ("OPERATE_INCOME", "TOTAL_OPERATE_INCOME"), "flow"),
    FieldSpec("operating_cost", ("OPERATE_COST", "TOTAL_OPERATE_COST"), "flow"),
    FieldSpec(
        "gross_profit",
        ("GROSS_PROFIT",),
        "flow",
        not_applicable=frozenset(FINANCIAL_TEMPLATES),
    ),
    FieldSpec(
        "deducted_net_profit",
        ("DEDUCT_PARENT_NETPROFIT", "KCFJCXSYJLR", "DEDU_PARENT_PROFIT"),
        "flow",
    ),
    FieldSpec("operating_cash_flow", ("NETCASH_OPERATE",), "flow"),
    FieldSpec(
        "accounts_receivable",
        ("ACCOUNTS_RECE", "ACCOUNTS_RECEIVABLE"),
        "point",
        not_applicable=frozenset(FINANCIAL_TEMPLATES),
    ),
    FieldSpec(
        "inventory",
        ("INVENTORY",),
        "point",
        not_applicable=frozenset(FINANCIAL_TEMPLATES),
    ),
    FieldSpec(
        "contract_liabilities",
        ("CONTRACT_LIAB", "CONTRACT_LIABILITY", "CONTRACT_LIABILITIES"),
        "point",
        not_applicable=frozenset(FINANCIAL_TEMPLATES),
    ),
    FieldSpec(
        "capex",
        ("CONSTRUCT_LONG_ASSET",),
        "flow",
        not_applicable=frozenset(FINANCIAL_TEMPLATES),
    ),
    FieldSpec(
        "interest_bearing_debt",
        ("INTEREST_BEARING_DEBT",),
        "point",
        not_applicable=frozenset(FINANCIAL_TEMPLATES),
    ),
    FieldSpec("total_equity", ("TOTAL_EQUITY", "TOTAL_EQUITY_PARENT"), "point"),
    FieldSpec("total_assets", ("TOTAL_ASSETS",), "point"),
    FieldSpec("cash", ("MONETARYFUNDS", "CASH_AND_DEPOSIT_CENTRAL_BANK"), "point"),
    FieldSpec(
        "audit_opinion",
        ("AUDIT_OPINION", "OPINION_TYPE", "AUDIT_RESULT"),
        "text",
        quarterly=False,
    ),
    FieldSpec(
        "internal_control_opinion",
        ("INTERNAL_CONTROL_OPINION", "INTERNAL_CONTROL_AUDIT_OPINION"),
        "text",
        quarterly=False,
    ),
)

DEBT_COMPONENTS = (
    "SHORT_LOAN",
    "LONG_LOAN",
    "NONCURRENT_LIAB_1YEAR",
    "BOND_PAYABLE",
    "LEASE_LIAB",
)
FLOW_TARGETS = {spec.target for spec in FIELD_SPECS if spec.semantics == "flow"}


@dataclass(slots=True)
class FinanceExportResult:
    annual: pd.DataFrame
    quarterly: pd.DataFrame
    field_status: pd.DataFrame
    future_rows: pd.DataFrame
    data_gaps: pd.DataFrame
    duplicate_resolution: pd.DataFrame


def _iso(value: Any) -> str:
    text = str(value or "").strip()[:10]
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return ""


def _number(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _source_priority(row: dict[str, Any]) -> int:
    explicit = _number(row.get("source_priority"))
    if explicit is not None:
        return int(explicit)
    source = str(row.get("source") or row.get("source_name") or "").upper()
    family = str(row.get("family") or "").upper()
    if source == "OFFICIAL_DISCLOSURE" or family == "OFFICIAL_DISCLOSURE":
        return 100
    if str(row.get("source_status") or "").upper() in {"PARSE_SUSPECT", "UNRESOLVED"}:
        return 0
    return 60


def _normalized_value(row: dict[str, Any]) -> tuple[float | None, str | None, str]:
    value_num = _number(row.get("value_num"))
    value_text = None if row.get("value_text") is None else str(row.get("value_text"))
    unit = str(row.get("normalized_unit") or row.get("unit") or "").strip()
    if value_num is not None and unit in UNIT_SCALES:
        return value_num * UNIT_SCALES[unit], value_text, "元"
    return value_num, value_text, unit


def _availability(row: dict[str, Any], disclosures: pd.DataFrame) -> str:
    direct = _iso(row.get("available_at"))
    if direct:
        return direct
    if disclosures.empty:
        return ""
    code = str(row.get("security_code") or "")
    report_date = _iso(row.get("report_date"))
    if not code or not report_date:
        return ""
    matched = disclosures[
        (disclosures["security_code"].astype(str) == code)
        & (disclosures["report_date"].astype(str).str[:10] == report_date)
    ]
    if "record_key" in disclosures and row.get("record_key"):
        exact = matched[disclosures["record_key"].astype(str) == str(row.get("record_key"))]
        if not exact.empty:
            matched = exact
    values = sorted({_iso(value) for value in matched.get("available_at", []) if _iso(value)})
    return values[-1] if values else ""


def _fact_candidates(
    facts: pd.DataFrame,
    disclosures: pd.DataFrame,
    *,
    as_of_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    records: list[dict[str, Any]] = []
    future: list[dict[str, Any]] = []
    missing_availability: list[dict[str, Any]] = []
    cutoff = _iso(as_of_date)
    if not cutoff:
        raise ValueError(f"invalid as_of_date: {as_of_date!r}")
    for raw in facts.to_dict("records"):
        report_date = _iso(raw.get("report_date"))
        if not report_date:
            continue
        available_at = _availability(raw, disclosures)
        item = dict(raw)
        item["report_date"] = report_date
        item["available_at"] = available_at
        item["field_key"] = str(raw.get("field_key") or "").upper()
        item["source_priority"] = _source_priority(raw)
        item["revision_id"] = str(raw.get("revision_id") or available_at or "")
        item["period_basis"] = str(raw.get("period_basis") or "CUMULATIVE").strip().upper()
        value_num, value_text, normalized_unit = _normalized_value(raw)
        item["canonical_value_num"] = value_num
        item["canonical_value_text"] = value_text
        item["canonical_unit"] = normalized_unit
        if not available_at:
            item["exclusion_reason"] = "AVAILABLE_AT_MISSING"
            missing_availability.append(item)
            continue
        if available_at > cutoff:
            item["exclusion_reason"] = "FUTURE_AVAILABLE_AT"
            future.append(item)
            continue
        records.append(item)
    return pd.DataFrame(records), pd.DataFrame(future), pd.DataFrame(missing_availability)


def _same_value(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_num = _number(left.get("canonical_value_num"))
    right_num = _number(right.get("canonical_value_num"))
    if left_num is not None and right_num is not None:
        denominator = max(abs(left_num), abs(right_num), 1.0)
        return abs(left_num - right_num) <= max(1e-8, denominator * 1e-10)
    return str(left.get("canonical_value_text") or "").strip() == str(
        right.get("canonical_value_text") or ""
    ).strip()


def _select_direct(
    candidates: pd.DataFrame,
    *,
    spec: FieldSpec,
    security_code: str,
    report_date: str,
    standalone: bool = False,
) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]]]:
    matched = candidates[
        (candidates["security_code"].astype(str) == security_code)
        & (candidates["report_date"] == report_date)
        & (candidates["field_key"].isin(spec.keys))
    ].copy()
    if spec.semantics == "flow":
        standalone_mask = matched["period_basis"].isin({"STANDALONE", "SINGLE_QUARTER"})
        matched = matched[standalone_mask] if standalone else matched[~standalone_mask]
    if matched.empty:
        return None, "SOURCE_MISSING", []
    usable = matched[matched["source_priority"] > 0].copy()
    if usable.empty:
        return None, "PARSE_SUSPECT", matched.to_dict("records")
    matched = usable
    key_rank = {key: index for index, key in enumerate(spec.keys)}
    matched["key_rank"] = matched["field_key"].map(key_rank).fillna(len(key_rank))
    matched = matched.sort_values(
        ["available_at", "source_priority", "key_rank", "revision_id", "record_key"],
        ascending=[False, False, True, False, True],
        na_position="last",
    )
    selected = matched.iloc[0].to_dict()
    top = matched[
        (matched["available_at"] == selected["available_at"])
        & (matched["source_priority"] == selected["source_priority"])
        & (matched["key_rank"] == selected["key_rank"])
    ]
    disagreements = [
        row for row in top.iloc[1:].to_dict("records") if not _same_value(selected, row)
    ]
    if disagreements:
        return None, "CONFLICTING", top.to_dict("records")
    return selected, "SOURCE_DIRECT", matched.to_dict("records")


def _status_record(
    *,
    security_id: str,
    security_code: str,
    report_date: str,
    field_name: str,
    status: str,
    selected: dict[str, Any] | None = None,
    derivation: str = "",
    source_fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "security_id": security_id,
        "security_code": security_code,
        "report_period": report_date,
        "field_name": field_name,
        "status": status,
        "available_at": str((selected or {}).get("available_at") or ""),
        "source_field_key": str((selected or {}).get("field_key") or ""),
        "source_url": str((selected or {}).get("source_url") or ""),
        "revision_id": str((selected or {}).get("revision_id") or ""),
        "derivation_method": derivation,
        "source_fields": json.dumps(source_fields or [], ensure_ascii=False),
        "value_num": (selected or {}).get("canonical_value_num"),
        "value_text": (selected or {}).get("canonical_value_text"),
        "unit": str((selected or {}).get("canonical_unit") or ""),
    }


def _direct_period_values(
    candidates: pd.DataFrame,
    *,
    security_id: str,
    security_code: str,
    report_date: str,
    template: IndustryTemplate,
    include_annual_only: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    values: dict[str, Any] = {}
    statuses: list[dict[str, Any]] = []
    duplicate_resolution: list[dict[str, Any]] = []
    selected_by_target: dict[str, dict[str, Any]] = {}
    for spec in FIELD_SPECS:
        if include_annual_only is False and not spec.quarterly:
            continue
        if template in spec.not_applicable:
            values[spec.target] = None
            statuses.append(
                _status_record(
                    security_id=security_id,
                    security_code=security_code,
                    report_date=report_date,
                    field_name=spec.target,
                    status="NOT_APPLICABLE",
                )
            )
            continue
        selected, status, all_candidates = _select_direct(
            candidates,
            spec=spec,
            security_code=security_code,
            report_date=report_date,
        )
        if status == "CONFLICTING":
            duplicate_resolution.append(
                {
                    "security_id": security_id,
                    "report_period": report_date,
                    "field_name": spec.target,
                    "status": status,
                    "candidate_count": len(all_candidates),
                    "candidate_values": json.dumps(
                        [
                            {
                                "field_key": item.get("field_key"),
                                "value_num": item.get("canonical_value_num"),
                                "value_text": item.get("canonical_value_text"),
                                "available_at": item.get("available_at"),
                                "source_url": item.get("source_url"),
                            }
                            for item in all_candidates
                        ],
                        ensure_ascii=False,
                    ),
                }
            )
        if selected:
            selected_by_target[spec.target] = selected
            values[spec.target] = (
                selected.get("canonical_value_text")
                if spec.semantics == "text"
                else selected.get("canonical_value_num")
            )
        else:
            values[spec.target] = None
        statuses.append(
            _status_record(
                security_id=security_id,
                security_code=security_code,
                report_date=report_date,
                field_name=spec.target,
                status=status,
                selected=selected,
            )
        )

    if template not in FINANCIAL_TEMPLATES and values.get("gross_profit") is None:
        revenue = values.get("revenue")
        operating_cost = values.get("operating_cost")
        if revenue is not None and operating_cost is not None:
            values["gross_profit"] = revenue - operating_cost
            source = selected_by_target.get("revenue") or selected_by_target.get("operating_cost")
            statuses = [item for item in statuses if item["field_name"] != "gross_profit"]
            statuses.append(
                _status_record(
                    security_id=security_id,
                    security_code=security_code,
                    report_date=report_date,
                    field_name="gross_profit",
                    status="DERIVED",
                    selected={**(source or {}), "canonical_value_num": values["gross_profit"]},
                    derivation="revenue - operating_cost",
                    source_fields=["revenue", "operating_cost"],
                )
            )

    if template not in FINANCIAL_TEMPLATES and values.get("interest_bearing_debt") is None:
        components: list[tuple[str, dict[str, Any]]] = []
        for key in DEBT_COMPONENTS:
            spec = FieldSpec(f"debt_component:{key}", (key,), "point")
            selected, status, _ = _select_direct(
                candidates,
                spec=spec,
                security_code=security_code,
                report_date=report_date,
            )
            if selected and status == "SOURCE_DIRECT" and selected.get("canonical_value_num") is not None:
                components.append((key, selected))
        if components:
            value = sum(float(item[1]["canonical_value_num"]) for item in components)
            values["interest_bearing_debt"] = value
            source = max((item[1] for item in components), key=lambda item: item["available_at"])
            statuses = [item for item in statuses if item["field_name"] != "interest_bearing_debt"]
            statuses.append(
                _status_record(
                    security_id=security_id,
                    security_code=security_code,
                    report_date=report_date,
                    field_name="interest_bearing_debt",
                    status="DERIVED_PROXY",
                    selected={**source, "canonical_value_num": value},
                    derivation="sum available explicit interest-bearing debt components",
                    source_fields=[item[0] for item in components],
                )
            )
    values.pop("operating_cost", None)
    return values, statuses, duplicate_resolution


def _period_dates(candidates: pd.DataFrame, security_code: str) -> list[str]:
    if candidates.empty:
        return []
    values = candidates[candidates["security_code"].astype(str) == security_code]["report_date"]
    return sorted({str(value) for value in values if _iso(value)})


def _quarter_name(report_date: str) -> str:
    return {"03-31": "Q1", "06-30": "Q2", "09-30": "Q3", "12-31": "Q4"}.get(
        report_date[5:], "OTHER"
    )


def _derive_standalone_quarters(
    cumulative: pd.DataFrame,
    status: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    security_code: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if cumulative.empty:
        return cumulative, status
    output: list[dict[str, Any]] = []
    status_records = status.to_dict("records")
    status_index = {
        (item["security_id"], item["report_period"], item["field_name"]): item
        for item in status_records
    }

    def apply_direct_standalone(
        record: dict[str, Any], *, security_id: str, report_date: str
    ) -> None:
        for spec in FIELD_SPECS:
            if spec.semantics != "flow" or spec.target == "operating_cost":
                continue
            selected, selected_status, _ = _select_direct(
                candidates,
                spec=spec,
                security_code=security_code,
                report_date=report_date,
                standalone=True,
            )
            if selected and selected_status == "SOURCE_DIRECT":
                record[spec.target] = selected.get("canonical_value_num")
                status_item = status_index.get((security_id, report_date, spec.target))
                if status_item is not None:
                    status_item.update(
                        _status_record(
                            security_id=security_id,
                            security_code=security_code,
                            report_date=report_date,
                            field_name=spec.target,
                            status="SOURCE_DIRECT",
                            selected=selected,
                            derivation="direct standalone-quarter source",
                        )
                    )

    for security_id, group in cumulative.groupby("security_id", sort=True):
        group = group.sort_values("report_period")
        for _, row in group.iterrows():
            record = row.to_dict()
            report_date = str(record["report_period"])
            quarter = _quarter_name(report_date)
            record["quarter"] = quarter
            year = report_date[:4]
            if quarter == "Q1":
                apply_direct_standalone(record, security_id=security_id, report_date=report_date)
                output.append(record)
                continue
            previous_suffix = {"Q2": "03-31", "Q3": "06-30", "Q4": "09-30"}.get(quarter)
            if not previous_suffix:
                output.append(record)
                continue
            previous_date = f"{year}-{previous_suffix}"
            previous_rows = group[group["report_period"] == previous_date]
            previous = previous_rows.iloc[-1].to_dict() if not previous_rows.empty else None
            for field in FLOW_TARGETS - {"operating_cost"}:
                current_value = record.get(field)
                previous_value = previous.get(field) if previous else None
                key = (security_id, report_date, field)
                status_item = status_index.get(key)
                if current_value is not None and previous_value is not None:
                    record[field] = float(current_value) - float(previous_value)
                    if status_item and status_item.get("status") not in {
                        "NOT_APPLICABLE",
                        "CONFLICTING",
                    }:
                        status_item["status"] = "DERIVED"
                        status_item["derivation_method"] = (
                            f"{report_date} cumulative - {previous_date} cumulative"
                        )
                        status_item["source_fields"] = json.dumps(
                            [f"{field}@{report_date}", f"{field}@{previous_date}"],
                            ensure_ascii=False,
                        )
                        status_item["value_num"] = record[field]
                elif current_value is not None:
                    record[field] = None
                    if status_item and status_item.get("status") not in {
                        "NOT_APPLICABLE",
                        "CONFLICTING",
                    }:
                        status_item["status"] = "SOURCE_MISSING"
                        status_item["derivation_method"] = (
                            f"missing prior cumulative period {previous_date}"
                        )
                        status_item["value_num"] = None
            apply_direct_standalone(record, security_id=security_id, report_date=report_date)
            output.append(record)
    return pd.DataFrame(output), pd.DataFrame(status_records)


def build_financial_tables(
    facts: pd.DataFrame,
    *,
    security_id: str,
    security_code: str,
    industry_template: IndustryTemplate | str,
    as_of_date: str,
    disclosure_dates: pd.DataFrame | None = None,
) -> FinanceExportResult:
    template = IndustryTemplate(str(industry_template))
    disclosures = disclosure_dates.copy() if disclosure_dates is not None else pd.DataFrame()
    candidates, future, missing_availability = _fact_candidates(
        facts.copy(), disclosures, as_of_date=as_of_date
    )
    statuses: list[dict[str, Any]] = []
    duplicate_resolution: list[dict[str, Any]] = []
    cumulative_rows: list[dict[str, Any]] = []
    annual_rows: list[dict[str, Any]] = []
    for report_date in _period_dates(candidates, security_code):
        values, period_status, period_duplicates = _direct_period_values(
            candidates,
            security_id=security_id,
            security_code=security_code,
            report_date=report_date,
            template=template,
            include_annual_only=report_date.endswith("12-31"),
        )
        statuses.extend(period_status)
        duplicate_resolution.extend(period_duplicates)
        available_values = [item["available_at"] for item in period_status if item.get("available_at")]
        row = {
            "security_id": security_id,
            "report_period": report_date,
            "available_at": max(available_values) if available_values else "",
            "industry_template": template.value,
            **values,
        }
        if report_date.endswith("12-31"):
            annual_rows.append(row)
        cumulative_rows.append(row)

    status_frame = pd.DataFrame(statuses)
    quarterly, status_frame = _derive_standalone_quarters(
        pd.DataFrame(cumulative_rows),
        status_frame,
        candidates,
        security_code=security_code,
    )
    if not quarterly.empty:
        quarterly = quarterly[
            quarterly["report_period"].str[5:].isin({"03-31", "06-30", "09-30", "12-31"})
        ]
        quarterly = quarterly.sort_values(["security_id", "report_period"]).reset_index(drop=True)
    annual = pd.DataFrame(annual_rows)
    if not annual.empty:
        annual = annual.sort_values(["security_id", "report_period"]).reset_index(drop=True)

    data_gap_records: list[dict[str, Any]] = []
    for raw in missing_availability.to_dict("records"):
        data_gap_records.append(
            {
                "security_id": security_id,
                "security_code": security_code,
                "report_period": raw.get("report_date"),
                "field_name": str(raw.get("field_key") or ""),
                "status": "SOURCE_MISSING",
                "reason": "required available_at is unavailable",
                "source_url": str(raw.get("source_url") or ""),
            }
        )
    if not future.empty:
        for raw in future.to_dict("records"):
            data_gap_records.append(
                {
                    "security_id": security_id,
                    "security_code": security_code,
                    "report_period": raw.get("report_date"),
                    "field_name": str(raw.get("field_key") or ""),
                    "status": "FUTURE_EXCLUDED",
                    "reason": f"available_at {raw.get('available_at')} exceeds cutoff {as_of_date}",
                    "source_url": str(raw.get("source_url") or ""),
                }
            )
    if not status_frame.empty:
        for raw in status_frame[
            status_frame["status"].isin({"SOURCE_MISSING", "CONFLICTING", "PARSE_SUSPECT"})
        ].to_dict("records"):
            data_gap_records.append(
                {
                    "security_id": security_id,
                    "security_code": security_code,
                    "report_period": raw.get("report_period"),
                    "field_name": raw.get("field_name"),
                    "status": raw.get("status"),
                    "reason": "canonical field is unavailable or quarantined",
                    "source_url": raw.get("source_url"),
                }
            )
    return FinanceExportResult(
        annual=annual,
        quarterly=quarterly,
        field_status=(
            status_frame.sort_values(["security_id", "report_period", "field_name"]).reset_index(
                drop=True
            )
            if not status_frame.empty
            else status_frame
        ),
        future_rows=future.reset_index(drop=True),
        data_gaps=pd.DataFrame(data_gap_records),
        duplicate_resolution=pd.DataFrame(duplicate_resolution),
    )
