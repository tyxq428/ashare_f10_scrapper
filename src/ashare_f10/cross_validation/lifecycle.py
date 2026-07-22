from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import pandas as pd

_LISTING_DATE_KEY_HINTS = {
    "LISTING_DATE",
    "LIST_DATE",
    "LISTED_DATE",
    "A_LIST_DATE",
    "A_SHARE_LISTING_DATE",
    "LISTINGDATE",
    "LISTDATE",
}
_LISTING_FAMILY_PRIORITY = {
    "RPT_F10_ORG_BASICINFO": 0,
    "RPT_F10_BASIC_ORGINFO": 0,
    "RPT_PCF10_ORG_ISSUEINFO": 1,
}


def normalize_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = (
        str(value)
        .strip()
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )
    match = re.search(
        r"(?P<year>(?:19|20)\d{2})-(?P<month>1[0-2]|0?[1-9])-(?P<day>3[01]|[12]\d|0?[1-9])",
        text,
    )
    if match:
        candidate = (
            f"{int(match.group('year')):04d}-"
            f"{int(match.group('month')):02d}-"
            f"{int(match.group('day')):02d}"
        )
        try:
            date.fromisoformat(candidate)
        except ValueError:
            return None
        return candidate
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8 and digits[:4].isdigit():
        candidate = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
        try:
            date.fromisoformat(candidate)
        except ValueError:
            return None
        return candidate
    return None


def _is_listing_date_key(value: Any) -> bool:
    key = re.sub(r"[^A-Z0-9]", "_", str(value or "").upper()).strip("_")
    if key in _LISTING_DATE_KEY_HINTS:
        return True
    return "LIST" in key and "DATE" in key and "DELIST" not in key


def infer_listing_date_from_eastmoney(frame: pd.DataFrame) -> tuple[str | None, str]:
    """Find a listing date only from explicit listing-date fields, never from report dates."""

    if frame.empty or "field_key" not in frame.columns:
        return None, ""
    candidates = frame[frame["field_key"].map(_is_listing_date_key)].copy()
    if candidates.empty:
        return None, ""
    parsed: list[tuple[int, str, str]] = []
    for row in candidates.to_dict("records"):
        family = str(row.get("family") or "")
        for column in ("value_text", "value_num"):
            value = normalize_date(row.get(column))
            if value:
                priority = _LISTING_FAMILY_PRIORITY.get(family, 100)
                parsed.append((priority, value, f"EASTMONEY:{family}:{row.get('field_key', '')}"))
                break
    if not parsed:
        return None, ""
    parsed.sort(key=lambda item: (item[0], item[1]))
    return parsed[0][1], parsed[0][2]


@dataclass(slots=True)
class SecurityLifecycle:
    security_code: str
    exchange: str
    listing_date: str | None
    listing_date_source: str
    requested_report_dates: list[str]
    pre_listing_report_dates: list[str]
    periodic_expected_report_dates: list[str]
    listing_transition_report_dates: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def listing_date_known(self) -> bool:
        return bool(self.listing_date)

    def period_class(self, report_date: str | None) -> str:
        value = normalize_date(report_date)
        if not value:
            return "NO_REPORT_DATE"
        if not self.listing_date:
            return "LISTING_DATE_UNKNOWN"
        if value < self.listing_date:
            return "PRE_LISTING_PERIOD"
        if value in self.listing_transition_report_dates:
            return "LISTING_TRANSITION_PERIOD"
        return "POST_LISTING_PERIODIC_EXPECTED"


def build_security_lifecycle(
    security_code: str,
    exchange: str,
    requested_report_dates: list[str],
    listing_date: str | None,
    listing_date_source: str,
) -> SecurityLifecycle:
    requested = sorted({value for value in (normalize_date(item) for item in requested_report_dates) if value})
    listing = normalize_date(listing_date)
    if listing:
        pre_listing = [item for item in requested if item < listing]
        expected = [item for item in requested if item >= listing]
        listing_year = listing[:4]
        transition = [
            item
            for item in expected
            if item.startswith(listing_year) and item == min(expected, default="")
        ]
    else:
        pre_listing = []
        expected = requested
        transition = []
    return SecurityLifecycle(
        security_code=security_code,
        exchange=exchange,
        listing_date=listing,
        listing_date_source=listing_date_source,
        requested_report_dates=requested,
        pre_listing_report_dates=pre_listing,
        periodic_expected_report_dates=expected,
        listing_transition_report_dates=transition,
    )
