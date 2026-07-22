from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComparisonPolicy:
    method: str
    canonical_unit: str = ""
    absolute_tolerance: float | None = None
    relative_tolerance: float | None = None
    display_decimals: int | None = None


def infer_comparison_policy(
    field_key: str,
    field_name: str,
    unit: str,
    data_semantics: str = "",
) -> ComparisonPolicy:
    """Infer a conservative comparison policy from field semantics.

    Explicit registry configuration can override these defaults. The policy separates
    monetary amounts, percentages, per-share metrics, integer counts, dates and text so
    that one global one-yuan threshold is never used for every field type.
    """

    key = str(field_key or "").upper()
    name = str(field_name or "")
    clean_unit = str(unit or "").strip()
    semantics = str(data_semantics or "").lower()

    if "DATE" in key or any(token in name for token in ("日期", "时间")):
        return ComparisonPolicy("date")
    if any(token in name for token in ("名单", "列表", "成员")):
        return ComparisonPolicy("set")
    if any(token in key for token in ("EPS", "PER_SHARE", "BPS")) or "每股" in name:
        return ComparisonPolicy(
            "per_share",
            canonical_unit=clean_unit,
            absolute_tolerance=0.0001,
            relative_tolerance=1e-6,
            display_decimals=4,
        )
    if clean_unit in {"%", "百分点", "百分比"} or any(
        token in name for token in ("率", "比例", "占比", "收益率")
    ):
        return ComparisonPolicy(
            "percentage",
            canonical_unit=clean_unit or "%",
            absolute_tolerance=0.01,
            relative_tolerance=1e-6,
            display_decimals=2,
        )
    if clean_unit in {"人", "户", "家", "股", "次", "个"} or any(
        token in key for token in ("COUNT", "SHARES", "EMPLOYEE", "HOLDER_NUM")
    ):
        return ComparisonPolicy(
            "integer",
            canonical_unit=clean_unit,
            absolute_tolerance=0.5,
            relative_tolerance=0.0,
            display_decimals=0,
        )
    if clean_unit in {"元", "千元", "万元", "亿元"}:
        return ComparisonPolicy(
            "numeric",
            canonical_unit="元",
            absolute_tolerance=1.0,
            relative_tolerance=1e-10,
            display_decimals=2,
        )
    if semantics in {"point_in_time", "flow"}:
        return ComparisonPolicy(
            "numeric",
            canonical_unit=clean_unit,
            absolute_tolerance=1e-9,
            relative_tolerance=1e-9,
        )
    return ComparisonPolicy("text", canonical_unit=clean_unit)
