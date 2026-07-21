from __future__ import annotations

import base64
from pathlib import Path

from ashare_f10.raw_sources.parsers.html_parser import extract_links, parse_html_document
from ashare_f10.raw_sources.parsers.pdf_parser import parse_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "raw_pack"


def test_sse_html_parser_extracts_entity_and_attachment(tmp_path):
    parsed = parse_html_document(
        FIXTURES / "SS001_listing_announcement.html",
        "https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/test.shtml",
        document_id="doc1",
        output_dir=tmp_path,
    )
    assert "688521" in parsed.text
    assert "芯原微电子" in parsed.text
    assert parsed.attachments == ["https://static.sse.com.cn/sample.pdf"]
    assert Path(parsed.text_path).exists()


def test_company_page_and_roadshow_parser(tmp_path):
    company = parse_html_document(
        FIXTURES / "verisilicon_about.html",
        "https://www.verisilicon.com/cn/AboutVeriSilicon",
        document_id="company",
        output_dir=tmp_path,
    )
    assert "半导体IP" in company.text
    roadshow = parse_html_document(
        FIXTURES / "roadshow_17760.html",
        "https://roadshow.sseinfo.com/roadshowIndex.do?id=17760",
        document_id="roadshow",
        output_dir=tmp_path,
    )
    assert "2024-04-01" in roadshow.text


def test_extract_links_resolves_relative_urls():
    html = '<a href="/cn/InvestorRelations">IR</a>'
    assert extract_links(html, "https://www.verisilicon.com/cn/") == [
        "https://www.verisilicon.com/cn/InvestorRelations"
    ]


def test_pdf_parser_preserves_page_map(tmp_path):
    fixture = tmp_path / "sse_quarter_report_fixture.pdf"
    fixture.write_bytes(
        base64.b64decode(
            "JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDcgMCBSIC9NZWRpYUJveCBbIDAgMCA1OTUuMjc1NiA4NDEuODg5OCBdIC9QYXJlbnQgNiAwIFIgL1Jlc291cmNlcyA8PAovRm9udCAxIDAgUiAvUHJvY1NldCBbIC9QREYgL1RleHQgL0ltYWdlQiAvSW1hZ2VDIC9JbWFnZUkgXQo+PiAvUm90YXRlIDAgL1RyYW5zIDw8Cgo+PiAKICAvVHlwZSAvUGFnZQo+PgplbmRvYmoKNCAwIG9iago8PAovUGFnZU1vZGUgL1VzZU5vbmUgL1BhZ2VzIDYgMCBSIC9UeXBlIC9DYXRhbG9nCj4+CmVuZG9iago1IDAgb2JqCjw8Ci9BdXRob3IgKGFub255bW91cykgL0NyZWF0aW9uRGF0ZSAoRDoyMDI2MDcyMTIyNTY1MyswMCcwMCcpIC9DcmVhdG9yIChhbm9ueW1vdXMpIC9LZXl3b3JkcyAoKSAvTW9kRGF0ZSAoRDoyMDI2MDcyMTIyNTY1MyswMCcwMCcpIC9Qcm9kdWNlciAoUmVwb3J0TGFiIFBERiBMaWJyYXJ5IC0gXChvcGVuc291cmNlXCkpIAogIC9TdWJqZWN0ICh1bnNwZWNpZmllZCkgL1RpdGxlICh1bnRpdGxlZCkgL1RyYXBwZWQgL0ZhbHNlCj4+CmVuZG9iago2IDAgb2JqCjw8Ci9Db3VudCAxIC9LaWRzIFsgMyAwIFIgXSAvVHlwZSAvUGFnZXMKPj4KZW5kb2JqCjcgMCBvYmoKPDwKL0ZpbHRlciBbIC9BU0NJSTg1RGVjb2RlIC9GbGF0ZURlY29kZSBdIC9MZW5ndGggMTU3Cj4+CnN0cmVhbQpHYXJXMVltUz8lKGtoV0lgQWFmTGsiakk1Wl8zTT9xVnRtU0tMamlnZ1w4YV0lTSFNdV9mPkZBQCdca1xoI01lNUc4LnVpR0puPj1ISyhTZGNLLzk0L1tbUCRecmVUMUFWRj9VaVxnRzc5LWAiaWNXUmMyQjo+LERxRVF1aCNqJGk3QmtfcUpHbi8jZj9WPUpyVCsvYUk7PF1Ca34+ZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgOAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwNjEgMDAwMDAgbiAKMDAwMDAwMDA5MiAwMDAwMCBuIAowMDAwMDAwMTk5IDAwMDAwIG4gCjAwMDAwMDA0MDIgMDAwMDAgbiAKMDAwMDAwMDQ3MCAwMDAwMCBuIAowMDAwMDAwNzMxIDAwMDAwIG4gCjAwMDAwMDA3OTAgMDAwMDAgbiAKdHJhaWxlcgo8PAovSUQgCls8ZWY5MGFjYTZmZDJjZjVmNmYwYzI1YTczMjc0MDViZDk+PGVmOTBhY2E2ZmQyY2Y1ZjZmMGMyNWE3MzI3NDA1YmQ5Pl0KJSBSZXBvcnRMYWIgZ2VuZXJhdGVkIFBERiBkb2N1bWVudCAtLSBkaWdlc3QgKG9wZW5zb3VyY2UpCgovSW5mbyA1IDAgUgovUm9vdCA0IDAgUgovU2l6ZSA4Cj4+CnN0YXJ0eHJlZgoxMDM3CiUlRU9GCg=="
        )
    )
    parsed = parse_pdf(fixture, "pdf1", tmp_path)
    assert parsed.page_map and parsed.page_map[0]["page"] == 1
    assert "688521" in parsed.text
    assert Path(parsed.text_path).exists()
