from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ashare_f10.fetch.manifest import load_field_mapping

DATE_KEYS = (
    "REPORT_DATE",
    "END_DATE",
    "TRADE_DATE",
    "NOTICE_DATE",
    "PUBLISH_DATE",
    "UPDATE_DATE",
    "report_date",
    "notice_date",
    "publish_time",
    "showDateTime",
)

FLOW_FAMILIES = {
    "RPT_F10_FINANCE_GINCOME",
    "RPT_F10_FINANCE_GINCOMEQC",
    "RPT_F10_FINANCE_GCASHFLOW",
    "RPT_F10_FINANCE_GCASHFLOWQC",
    "RPT_F10_FINANCE_MAINFINADATA",
    "RPT_F10_QTR_MAINFINADATA",
    "RPT_F10_FINANCE_GRATIO",
    "RPT_F10_FINANCE_QGRATIO",
}

POINT_FAMILIES = {
    "RPT_F10_FINANCE_GBALANCE",
    "RPT_F10_EH_HOLDERNUM",
    "RPT_F10_EH_HOLDERS",
    "RPT_F10_EH_FREEHOLDERS",
    "RPT_F10_EH_EQUITY",
}


@dataclass
class FieldMapping:
    global_map: dict[str, dict[str, Any]]
    context_map: dict[str, dict[str, Any]]

    @classmethod
    def load(cls) -> FieldMapping:
        data = load_field_mapping()
        return cls(global_map=data.get("global", {}), context_map=data.get("context", {}))

    def resolve(self, key: str, theme: str, family: str, dataset: str) -> tuple[str, str, str]:
        context_key = f"{theme}|{family}|{dataset}|{key}"
        context = self.context_map.get(context_key)
        global_item = self.global_map.get(key, {})
        item = context or global_item
        return (
            str(item.get("label", key)),
            str(item.get("unit", "")),
            str(item.get("category", "PAGE_DISPLAY_FIELD")),
        )


def normalize_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        # Millisecond or second Unix timestamp.
        try:
            ts = float(value)
            if ts > 10_000_000_000:
                ts /= 1000
            return pd.to_datetime(ts, unit="s", utc=True).strftime("%Y-%m-%d")
        except Exception:
            return str(value)
    text = str(value).strip()
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text[:10] if len(text) >= 10 else text
    return parsed.strftime("%Y-%m-%d")


def derive_period_type(record: dict[str, Any], report_date: str | None, family: str) -> str:
    explicit = str(record.get("REPORT_TYPE") or record.get("REPORT_DATE_NAME") or "").strip()
    if explicit:
        return explicit
    if not report_date:
        return "EVENT"
    month = report_date[5:7]
    return {"03": "Q1", "06": "Q2", "09": "Q3", "12": "FY"}.get(month, "OTHER")


def _scalar(value: Any) -> tuple[str | None, float | None]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return str(value), float(value)
    if isinstance(value, (int, float)):
        return str(value), float(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")), None
    text = str(value)
    try:
        numeric = float(text.replace(",", ""))
    except (ValueError, TypeError):
        numeric = None
    return text, numeric


def _record_date(record: dict[str, Any]) -> str | None:
    for key in DATE_KEYS:
        if record.get(key) not in (None, ""):
            return normalize_date(record[key])
    return None


def _source_url(group: dict[str, Any], record: dict[str, Any]) -> str:
    if record.get("_SOURCE_URL"):
        return str(record["_SOURCE_URL"])
    for request in group.get("requests", []):
        request_data = request.get("request") if isinstance(request, dict) else None
        if isinstance(request_data, dict) and request_data.get("url"):
            return str(request_data["url"])
    return ""


def _dataset_name(group: dict[str, Any]) -> str:
    return f"{group.get('theme', '')} / {group.get('family', '')}"


def iter_facts(combined: dict[str, Any]) -> Iterable[dict[str, Any]]:
    mapping = FieldMapping.load()
    security = combined["metadata"]["security"]
    security_code = security["code"]

    for group in combined.get("groups", []):
        theme = str(group.get("theme", ""))
        family = str(group.get("family", ""))
        dataset = _dataset_name(group)
        records = list(group.get("records", []))

        # PageAjax is a dictionary of named page sections. Expose each section as a dataset.
        if family == "PageAjax" and group.get("payloads"):
            for payload in group["payloads"]:
                if not isinstance(payload, dict):
                    continue
                for section, value in payload.items():
                    section_records: list[dict[str, Any]] = []
                    if isinstance(value, list):
                        section_records = [item for item in value if isinstance(item, dict)]
                    elif isinstance(value, dict):
                        if isinstance(value.get("data"), list):
                            section_records = [item for item in value["data"] if isinstance(item, dict)]
                        else:
                            section_records = [value]
                    for record in section_records:
                        yield from _record_facts(
                            record,
                            security_code,
                            theme=f"页面汇总/{section}",
                            family=family,
                            dataset=f"PageAjax/{section}",
                            mapping=mapping,
                            source_url=_source_url(group, record),
                        )
            continue

        for record in records:
            if not isinstance(record, dict):
                continue
            yield from _record_facts(
                record,
                security_code,
                theme=theme,
                family=family,
                dataset=dataset,
                mapping=mapping,
                source_url=_source_url(group, record),
            )


def _record_facts(
    record: dict[str, Any],
    security_code: str,
    theme: str,
    family: str,
    dataset: str,
    mapping: FieldMapping,
    source_url: str,
) -> Iterable[dict[str, Any]]:
    report_date = normalize_date(record.get("REPORT_DATE"))
    event_date = _record_date(record)
    period_type = derive_period_type(record, report_date, family)
    semantics = (
        "flow" if family in FLOW_FAMILIES else "point_in_time" if family in POINT_FAMILIES else "event"
    )

    record_key_parts = [security_code, family, report_date or event_date or ""]
    for candidate in ("art_code", "INFO_CODE", "MXID", "HOLDER_RANK", "RANK", "PERSON_CODE"):
        if record.get(candidate) not in (None, ""):
            record_key_parts.append(str(record[candidate]))
    record_key = "|".join(record_key_parts)

    for key, value in record.items():
        if key.startswith("_") and key not in {"_SOURCE_URL", "_FETCHED_AT_UTC"}:
            continue
        value_text, value_num = _scalar(value)
        label, unit, category = mapping.resolve(key, theme, family, dataset)
        yield {
            "security_code": security_code,
            "theme": theme,
            "family": family,
            "dataset": dataset,
            "record_key": record_key,
            "report_date": report_date,
            "event_date": event_date,
            "period_type": period_type,
            "data_semantics": semantics,
            "field_key": key,
            "field_name_cn": label,
            "field_category": category,
            "value_text": value_text,
            "value_num": value_num,
            "unit": unit,
            "source_url": source_url,
            "source_status": "FACT_DIRECT",
        }


def build_data_store(combined: dict[str, Any], output_dir: Path) -> dict[str, str]:
    normalized_dir = output_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    facts_path = normalized_dir / "facts.parquet"
    db_path = normalized_dir / "f10.duckdb"

    rows = list(iter_facts(combined))
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(
            columns=[
                "security_code",
                "theme",
                "family",
                "dataset",
                "record_key",
                "report_date",
                "event_date",
                "period_type",
                "data_semantics",
                "field_key",
                "field_name_cn",
                "field_category",
                "value_text",
                "value_num",
                "unit",
                "source_url",
                "source_status",
            ]
        )
    frame.to_parquet(facts_path, index=False)

    connection = duckdb.connect(str(db_path))
    connection.execute("DROP TABLE IF EXISTS facts")
    connection.execute("CREATE TABLE facts AS SELECT * FROM read_parquet(?)", [str(facts_path)])
    connection.execute("CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(field_key)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_facts_date ON facts(report_date)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_facts_family ON facts(family)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_facts_name ON facts(field_name_cn)")
    connection.execute(
        """
        CREATE OR REPLACE VIEW latest_numeric AS
        SELECT * EXCLUDE (rn) FROM (
            SELECT *, row_number() OVER (
                PARTITION BY security_code, family, field_key
                ORDER BY report_date DESC NULLS LAST, event_date DESC NULLS LAST
            ) AS rn
            FROM facts WHERE value_num IS NOT NULL
        ) WHERE rn = 1
        """
    )
    connection.close()

    return {"parquet": str(facts_path), "duckdb": str(db_path), "fact_count": str(len(frame))}
