from __future__ import annotations

from pathlib import Path

from ashare_f10.config import Settings
from ashare_f10.raw_sources.downloaders.http_downloader import HttpDownloader, RequestContext


class FakeResponse:
    def __init__(self, status_code: int, text: str = "", content_type: str = "text/html") -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = {"content-type": content_type}
        self.url = "https://example.gov.cn/final"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls = 0
        self.headers: dict[str, str] = {}

    def get(self, *args, **kwargs):  # noqa: ANN002, ANN003
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def downloader(session: FakeSession) -> HttpDownloader:
    return HttpDownloader(Settings(timeout=1, retries=1), session=session)  # type: ignore[arg-type]


def test_permission_gate_stops_after_one_403(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(403, "Forbidden")])
    result = downloader(session).download(
        "https://example.gov.cn/query",
        tmp_path / "result.html",
        RequestContext(
            source_id="SRC016",
            expected_domains=("example.gov.cn",),
            max_attempts=3,
            permission_gate=True,
            rate_limit_seconds=0,
        ),
    )
    assert result.access_status == "HTTP_403"
    assert result.attempts == 1
    assert session.calls == 1


def test_javascript_gate_is_classified_without_retry(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, "This site doesn't work properly without JavaScript enabled")])
    result = downloader(session).download(
        "https://example.gov.cn/query",
        tmp_path / "result.html",
        RequestContext(
            source_id="SRC023",
            expected_domains=("example.gov.cn",),
            max_attempts=1,
            permission_gate=True,
            rate_limit_seconds=0,
        ),
    )
    assert result.access_status == "JS_REQUIRED"
    assert result.file_path is None
    assert session.calls == 1


def test_successful_html_is_saved_with_hash(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, "<html><title>Official</title><body>688521</body></html>")])
    target = tmp_path / "result.html"
    result = downloader(session).download(
        "https://example.gov.cn/query",
        target,
        RequestContext(
            source_id="SRC001",
            expected_domains=("example.gov.cn",),
            max_attempts=1,
            rate_limit_seconds=0,
        ),
    )
    assert result.access_status == "DOWNLOAD_OK"
    assert target.exists()
    assert result.sha256 and len(result.sha256) == 64
