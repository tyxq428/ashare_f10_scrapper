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


def normalize_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    match = re.search(r"(?:19|20)\d{2}[-/.年](?:0?[1-9]|1[0-2])[-/.月](?:0?[1-9]|[12]\d|3[01])", text)
    if match:
        digits = re.sub(r"\D", "", match.group(0))
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
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
    for row in candidates.to_dict("records"):
        for column in ("value_text", "value_num"):
            parsed = normalize_date(row.get(column))
            if parsed:
                return parsed, f"EASTMONEY:{row.get('family', '')}:{row.get('field_key', '')}"
    return None, ""


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
