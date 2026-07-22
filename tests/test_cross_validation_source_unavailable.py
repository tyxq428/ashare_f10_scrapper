from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.comparator import CrossSourceComparator


def test_official_source_unavailable_is_not_counted_as_comparable() -> None:
    frame = pd.DataFrame(
        [
            {"status": "OFFICIAL_SOURCE_UNAVAILABLE"},
            {"status": "NOT_IN_OFFICIAL_SCOPE"},
            {"status": "SOURCE_SPECIFIC"},
        ]
    )
    summary = CrossSourceComparator.summary(frame)
    assert summary["comparison_count"] == 3
    assert summary["comparable_count"] == 0
    assert summary["matched_count"] == 0
    assert summary["true_conflict_count"] == 0
