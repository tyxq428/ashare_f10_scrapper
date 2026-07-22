from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Iterable

from ashare_f10.validation.models import OfficialDocument

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_VERSION_PRIORITY = {"corrected": 30, "revised": 30, "original": 20, "withdrawn": 0}


def normalize_date(value: str | date | datetime | None, *, default_today: bool = False) -> str:
    if value is None or value == "":
        return date.today().isoformat() if default_today else ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    match = _DATE_PATTERN.search(str(value))
    if match is None:
        raise ValueError(f"日期必须包含YYYY-MM-DD：{value}")
    parsed = datetime.strptime(match.group(0), "%Y-%m-%d").date()
    return parsed.isoformat()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def document_available(document: OfficialDocument, as_of_date: str) -> bool:
    available = normalize_date(document.available_at or document.publish_date)
    return bool(available and available <= as_of_date)


def version_sort_key(document: OfficialDocument) -> tuple[int, str, str]:
    return (
        _VERSION_PRIORITY.get(document.version_label, 10),
        normalize_date(document.available_at or document.publish_date),
        document.document_id,
    )


@dataclass(slots=True)
class DocumentSelection:
    selected: list[OfficialDocument]
    boundary: list[OfficialDocument]
    missing_report_dates: list[str]
    decisions: list[dict[str, str]]


def select_report_versions(
    documents: Iterable[OfficialDocument],
    report_dates: Iterable[str],
    *,
    as_of_date: str | None = None,
) -> DocumentSelection:
    """Select the best document version that was knowable at the research cutoff."""

    cutoff = normalize_date(as_of_date, default_today=True)
    requested = sorted({normalize_date(value) for value in report_dates if value})
    available_documents = list(documents)
    selected: list[OfficialDocument] = []
    boundary: list[OfficialDocument] = []
    missing: list[str] = []
    decisions: list[dict[str, str]] = []

    for report_date in requested:
        candidates = [
            item
            for item in available_documents
            if normalize_date(item.report_date) == report_date and item.version_label != "withdrawn"
        ]
        eligible = [item for item in candidates if document_available(item, cutoff)]
        future = [item for item in candidates if not document_available(item, cutoff)]
        for item in future:
            copy_item = copy.copy(item)
            copy_item.is_boundary = True
            boundary.append(copy_item)
        if not eligible:
            missing.append(report_date)
            decisions.append(
                {
                    "report_date": report_date,
                    "decision": "MISSING_AT_AS_OF_DATE",
                    "as_of_date": cutoff,
                    "candidate_count": str(len(candidates)),
                    "future_candidate_count": str(len(future)),
                }
            )
            continue
        chosen = max(eligible, key=version_sort_key)
        predecessors = sorted(
            [item for item in eligible if item.document_id != chosen.document_id],
            key=lambda item: (normalize_date(item.available_at or item.publish_date), version_sort_key(item)),
        )
        if predecessors:
            chosen.supersedes_document_id = predecessors[-1].document_id
        selected.append(chosen)
        decisions.append(
            {
                "report_date": report_date,
                "decision": "SELECTED",
                "as_of_date": cutoff,
                "document_id": chosen.document_id,
                "version_label": chosen.version_label,
                "available_at": chosen.available_at or chosen.publish_date,
                "supersedes_document_id": chosen.supersedes_document_id,
                "candidate_count": str(len(candidates)),
                "eligible_candidate_count": str(len(eligible)),
            }
        )

    selected.sort(key=lambda item: (item.report_date, item.available_at or item.publish_date))
    boundary.sort(key=lambda item: (item.report_date, item.available_at or item.publish_date))
    return DocumentSelection(selected, boundary, missing, decisions)
