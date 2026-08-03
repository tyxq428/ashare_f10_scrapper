from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

# XML 1.0 forbids the C0 control characters below. Tabs, line feeds and
# carriage returns are intentionally preserved because Excel supports them.
EXCEL_ILLEGAL_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True, slots=True)
class ExcelSanitizationReport:
    affected_strings: int
    removed_characters: int
    removed_codepoints: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sanitize_excel_text(value: str) -> tuple[str, Counter[int]]:
    removed: Counter[int] = Counter(ord(match.group(0)) for match in EXCEL_ILLEGAL_CONTROL_CHARACTERS.finditer(value))
    if not removed:
        return value, removed
    return EXCEL_ILLEGAL_CONTROL_CHARACTERS.sub("", value), removed


def sanitize_excel_payload_in_place(value: Any) -> ExcelSanitizationReport:
    """Remove only Excel-forbidden control characters from nested values.

    The caller must invoke this after raw JSON and normalized stores are written.
    This keeps the source payload lossless while making the optional XLSX view safe.
    """

    affected_strings = 0
    removed_codepoints: Counter[int] = Counter()

    def visit(item: Any) -> Any:
        nonlocal affected_strings
        if isinstance(item, dict):
            for key in list(item):
                item[key] = visit(item[key])
            return item
        if isinstance(item, list):
            for index, child in enumerate(item):
                item[index] = visit(child)
            return item
        if isinstance(item, tuple):
            return tuple(visit(child) for child in item)
        if isinstance(item, str):
            sanitized, removed = sanitize_excel_text(item)
            if removed:
                affected_strings += 1
                removed_codepoints.update(removed)
            return sanitized
        return item

    visit(value)
    return ExcelSanitizationReport(
        affected_strings=affected_strings,
        removed_characters=sum(removed_codepoints.values()),
        removed_codepoints={f"U+{codepoint:04X}": count for codepoint, count in sorted(removed_codepoints.items())},
    )
