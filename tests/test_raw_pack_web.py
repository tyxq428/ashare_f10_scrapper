from pathlib import Path


def test_raw_pack_static_page_contract():
    root = Path(__file__).parents[1] / "src" / "ashare_f10" / "web"
    html = (root / "raw-pack.html").read_text(encoding="utf-8")
    script = (root / "raw-pack.js").read_text(encoding="utf-8")
    for value in ("Raw Pack任务", "证据浏览器", "文档详情", "权限阻塞"):
        assert value in html
    for endpoint in (
        "/api/raw-pack/jobs",
        "/api/raw-pack/evidence/search",
        "/api/raw-pack/documents/",
        "/api/raw-pack/blocked",
    ):
        assert endpoint in script
