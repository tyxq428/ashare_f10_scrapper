from __future__ import annotations

from ashare_f10.validation.models import OfficialDocument
from ashare_f10.validation.point_in_time import normalize_date, select_report_versions


def _document(title: str, publish_date: str, version: str) -> OfficialDocument:
    return OfficialDocument(
        source="SSE",
        security_code="688521",
        title=title,
        publish_date=publish_date,
        report_date="2025-12-31",
        report_kind="annual",
        version_label=version,
        url=f"https://example.invalid/{version}-{publish_date}.pdf",
    )


def test_as_of_date_selects_original_before_later_correction() -> None:
    original = _document("芯原股份2025年年度报告", "2026-03-20", "original")
    corrected = _document("芯原股份2025年年度报告（修订版）", "2026-04-01", "corrected")
    selection = select_report_versions(
        [original, corrected],
        ["2025-12-31"],
        as_of_date="2026-03-31",
    )
    assert selection.selected == [original]
    assert [item.document_id for item in selection.boundary] == [corrected.document_id]
    assert selection.missing_report_dates == []
    assert selection.decisions[0]["version_label"] == "original"


def test_as_of_date_selects_correction_and_records_version_chain() -> None:
    original = _document("芯原股份2025年年度报告", "2026-03-20", "original")
    corrected = _document("芯原股份2025年年度报告（修订版）", "2026-04-01", "corrected")
    selection = select_report_versions(
        [original, corrected],
        ["2025-12-31"],
        as_of_date="2026-04-02",
    )
    assert selection.selected == [corrected]
    assert corrected.supersedes_document_id == original.document_id
    assert selection.boundary == []


def test_unpublished_report_is_missing_at_cutoff() -> None:
    document = _document("芯原股份2025年年度报告", "2026-03-20", "original")
    selection = select_report_versions(
        [document],
        ["2025-12-31"],
        as_of_date="2026-03-01",
    )
    assert selection.selected == []
    assert selection.missing_report_dates == ["2025-12-31"]
    assert selection.boundary[0].is_boundary


def test_document_identity_is_stable_and_dates_are_normalized() -> None:
    first = _document("芯原股份2025年年度报告", "2026-03-20", "original")
    second = _document("芯原股份2025年年度报告", "2026-03-20", "original")
    assert first.document_id == second.document_id
    assert first.available_at == "2026-03-20"
    assert first.effective_at == "2025-12-31"
    assert normalize_date("published 2026-03-20 18:00") == "2026-03-20"
