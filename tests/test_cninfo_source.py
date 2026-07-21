from __future__ import annotations

import hashlib

from ashare_f10.validation.sources.cninfo import CNInfoOfficialSource


def test_cninfo_report_discovery_prefers_corrected_and_excludes_summary(monkeypatch) -> None:
    source = CNInfoOfficialSource()
    monkeypatch.setattr(source, "resolve_org_id", lambda _code: "9900010448")
    payload = {
        "announcements": [
            {
                "announcementTitle": "顺丰控股：2025年年度报告",
                "announcementTime": 1774886400000,
                "adjunctUrl": "finalpage/2026-03-31/annual-original.PDF",
                "adjunctType": "PDF",
            },
            {
                "announcementTitle": "顺丰控股：2025年年度报告（修订版）",
                "announcementTime": 1774972800000,
                "adjunctUrl": "finalpage/2026-04-01/annual-corrected.PDF",
                "adjunctType": "PDF",
            },
            {
                "announcementTitle": "顺丰控股：2025年年度报告摘要",
                "announcementTime": 1774886400000,
                "adjunctUrl": "finalpage/2026-03-31/annual-summary.PDF",
                "adjunctType": "PDF",
            },
            {
                "announcementTitle": "顺丰控股：2026年一季度报告",
                "announcementTime": 1777392000000,
                "adjunctUrl": "finalpage/2026-04-29/q1.PDF",
                "adjunctType": "PDF",
            },
        ],
        "hasMore": False,
        "totalpages": 1,
    }
    monkeypatch.setattr(source, "_post_json", lambda _url, _data, _referer: payload)
    selected = source.select_reports(
        "002352",
        ["2025-12-31", "2026-03-31"],
        begin_date="2025-01-01",
        end_date="2026-07-21",
    )
    assert len(selected) == 2
    annual = next(item for item in selected if item.report_kind == "annual")
    quarter = next(item for item in selected if item.report_kind == "q1")
    assert annual.version_label == "corrected"
    assert annual.url.endswith("annual-corrected.PDF")
    assert quarter.report_date == "2026-03-31"
    assert all("摘要" not in item.title for item in selected)


def test_cninfo_stock_lookup_uses_exact_code(monkeypatch) -> None:
    source = CNInfoOfficialSource()
    monkeypatch.setattr(source, "_warmup", lambda _code: None)
    monkeypatch.setattr(
        source,
        "_post_json",
        lambda _url, _data, _referer: [
            {"code": "00235", "orgId": "wrong", "category": "A股"},
            {"code": "002352", "orgId": "9900010448", "category": "A股"},
        ],
    )
    assert source.resolve_org_id("002352") == "9900010448"


def test_cninfo_download_validates_pdf_and_hash(tmp_path) -> None:
    content = b"%PDF-1.7\nCNINFO test document"

    class Response:
        headers = {"content-type": "application/pdf"}
        status_code = 200

        def __init__(self) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class Session:
        headers: dict[str, str] = {}

        def get(self, *_args, **_kwargs):
            return Response()

    source = CNInfoOfficialSource(session=Session())
    from ashare_f10.validation.models import OfficialDocument

    document = OfficialDocument(
        "CNINFO",
        "002352",
        "顺丰控股：2025年年度报告",
        "2026-03-31",
        "2025-12-31",
        "annual",
        "original",
        "https://static.cninfo.com.cn/finalpage/2026-03-31/test.PDF",
    )
    downloaded = source.download(document, tmp_path)
    assert downloaded.local_path
    assert downloaded.sha256 == hashlib.sha256(content).hexdigest()
    assert (tmp_path / "002352_2025-12-31_annual.pdf").read_bytes() == content
