from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import duckdb

from ashare_f10.validation.documents.pdf_parser import DEFAULT_TARGETS
from ashare_f10.validation.models import TargetField

DIRECT_FAMILY_TO_STATEMENT = {
    "RPT_F10_FINANCE_GBALANCE": ("balance_sheet", "point_in_time"),
    "RPT_F10_FINANCE_GINCOME": ("income_statement", "flow"),
    "RPT_F10_FINANCE_GCASHFLOW": ("cash_flow", "flow"),
}

EXCLUDED_KEYS = {
    "SECUCODE",
    "SECURITY_CODE",
    "SECURITY_NAME_ABBR",
    "ORG_CODE",
    "ORG_TYPE",
    "REPORT_DATE",
    "REPORT_TYPE",
    "REPORT_DATE_NAME",
    "SECURITY_TYPE_CODE",
    "NOTICE_DATE",
    "UPDATE_DATE",
    "CURRENCY",
    "OPINION_TYPE",
    "OSOPINION_TYPE",
    "LISTING_STATE",
}


def build_dynamic_targets(db_path: Path | str) -> tuple[TargetField, ...]:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT family, field_key, any_value(field_name_cn) AS field_name_cn
            FROM facts
            WHERE family IN ('RPT_F10_FINANCE_GBALANCE','RPT_F10_FINANCE_GINCOME','RPT_F10_FINANCE_GCASHFLOW')
              AND value_num IS NOT NULL
              AND field_key NOT LIKE '\\_%' ESCAPE '\\'
            GROUP BY family, field_key
            ORDER BY family, field_key
            """
        ).fetchall()
    finally:
        connection.close()

    aliases: dict[tuple[str, str], set[str]] = defaultdict(set)
    for family, key, name in rows:
        key = str(key)
        if key in EXCLUDED_KEYS or key.endswith(("_YOY", "_QOQ")):
            continue
        label = str(name or key).strip()
        if not label or label == key or len(label) > 60:
            continue
        aliases[(str(family), key)].add(label)

    targets: dict[tuple[str, str], TargetField] = {}
    for target in DEFAULT_TARGETS:
        for family in target.eastmoney_families:
            targets[(family, target.field_key)] = target

    for (family, key), names in aliases.items():
        statement_type, semantics = DIRECT_FAMILY_TO_STATEMENT[family]
        identity = (family, key)
        existing = targets.get(identity)
        if existing:
            merged_aliases = tuple(dict.fromkeys((*existing.aliases, *sorted(names))))
            targets[identity] = TargetField(
                existing.field_key,
                existing.field_name_cn,
                existing.statement_type,
                merged_aliases,
                existing.eastmoney_keys,
                existing.eastmoney_families,
                existing.semantics,
            )
        else:
            label = sorted(names, key=len)[0]
            targets[identity] = TargetField(
                key,
                label,
                statement_type,
                tuple(sorted(names, key=len, reverse=True)),
                (key,),
                (family,),
                semantics,
            )
    return tuple(targets.values())
