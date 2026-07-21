from __future__ import annotations

import hashlib
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from ashare_f10.config import Settings, settings
from ashare_f10.raw_sources.models import Attachment, DownloadResult, stable_document_id


@dataclass(slots=True)
class RequestContext:
    source_id: str
    referer: str | None = None
    expected_domains: tuple[str, ...] = ()
    max_attempts: int = 3
    rate_limit_seconds: float = 0.5
    permission_gate: bool = False


class HttpDownloader:
    def __init__(self, config: Settings = settings, session: requests.Session | None = None) -> None:
        self.settings = config
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.user_agent,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/pdf,application/json,*/*;q=0.8",
            }
        )
        self._last_request_at: dict[str, float] = {}

    def _wait_for_rate_limit(self, domain: str, seconds: float) -> None:
        if seconds <= 0:
            return
        previous = self._last_request_at.get(domain)
        if previous is not None:
            remaining = seconds - (time.monotonic() - previous)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[domain] = time.monotonic()

    @staticmethod
    def _extension(url: str, content_type: str | None) -> str:
        suffix = Path(urlparse(url).path).suffix
        if suffix and len(suffix) <= 8:
            return suffix
        if content_type:
            guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
            if guessed:
                return guessed
        return ".bin"

    @staticmethod
    def _is_js_gate(text: str) -> bool:
        lower = text.lower()
        return any(
            token in lower
            for token in (
                "doesn't work properly without javascript",
                "enable javascript",
                "javascript is required",
                "请开启javascript",
                "请启用javascript",
            )
        )

    @staticmethod
    def _is_captcha(text: str) -> bool:
        lower = text.lower()
        return any(token in lower for token in ("captcha", "验证码", "滑块验证", "人机验证"))

    @staticmethod
    def _is_login_gate(text: str) -> bool:
        lower = text.lower()
        return any(token in lower for token in ("login required", "请登录", "登录后", "统一身份认证"))

    def download(
        self,
        url: str,
        target_path: Path,
        request_context: RequestContext,
        *,
        allow_html: bool = True,
    ) -> DownloadResult:
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower()
        if request_context.expected_domains and not any(
            domain == item or domain.endswith(f".{item}") for item in request_context.expected_domains
        ):
            return DownloadResult(
                url=url,
                final_url=url,
                access_status="DOWNLOAD_FAILED",
                error=f"domain {domain} is outside expected domains",
            )

        max_attempts = max(1, request_context.max_attempts)
        if request_context.permission_gate:
            max_attempts = 1
        headers = {"Referer": request_context.referer} if request_context.referer else {}
        last_error: str | None = None
        for attempt in range(1, max_attempts + 1):
            self._wait_for_rate_limit(domain, request_context.rate_limit_seconds)
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=max(self.settings.timeout, 45),
                    allow_redirects=True,
                )
                content_type = response.headers.get("content-type")
                final_url = response.url
                if response.status_code == 403:
                    return DownloadResult(
                        url=url,
                        final_url=final_url,
                        status_code=403,
                        access_status="HTTP_403",
                        content_type=content_type,
                        error="HTTP 403 Forbidden",
                        attempts=attempt,
                    )
                if response.status_code == 404:
                    return DownloadResult(
                        url=url,
                        final_url=final_url,
                        status_code=404,
                        access_status="HTTP_404",
                        content_type=content_type,
                        error="HTTP 404 Not Found",
                        attempts=attempt,
                    )
                response.raise_for_status()
                content = response.content
                text: str | None = None
                if content_type and (
                    "text/" in content_type or "html" in content_type or "json" in content_type
                ):
                    text = response.text
                    if self._is_js_gate(text):
                        return DownloadResult(
                            url=url,
                            final_url=final_url,
                            status_code=response.status_code,
                            access_status="JS_REQUIRED",
                            content_type=content_type,
                            html_text=text[:10000],
                            error="JavaScript is required for this source",
                            attempts=attempt,
                        )
                    if self._is_captcha(text):
                        return DownloadResult(
                            url=url,
                            final_url=final_url,
                            status_code=response.status_code,
                            access_status="CAPTCHA_REQUIRED",
                            content_type=content_type,
                            html_text=text[:10000],
                            error="Captcha or human verification detected",
                            attempts=attempt,
                        )
                    if self._is_login_gate(text):
                        return DownloadResult(
                            url=url,
                            final_url=final_url,
                            status_code=response.status_code,
                            access_status="LOGIN_REQUIRED",
                            content_type=content_type,
                            html_text=text[:10000],
                            error="Login gate detected",
                            attempts=attempt,
                        )
                if not allow_html and text is not None:
                    return DownloadResult(
                        url=url,
                        final_url=final_url,
                        status_code=response.status_code,
                        access_status="DOWNLOAD_FAILED",
                        content_type=content_type,
                        html_text=text[:1000],
                        error="Expected binary file but received text/html",
                        attempts=attempt,
                    )
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()
                return DownloadResult(
                    url=url,
                    final_url=final_url,
                    status_code=response.status_code,
                    access_status="DOWNLOAD_OK",
                    content_type=content_type,
                    file_path=str(target_path),
                    size_bytes=len(content),
                    sha256=digest,
                    html_text=text,
                    attempts=attempt,
                )
            except requests.Timeout as exc:
                last_error = f"timeout: {exc}"
                if attempt == max_attempts:
                    return DownloadResult(
                        url=url,
                        final_url=url,
                        access_status="TIMEOUT",
                        error=last_error,
                        attempts=attempt,
                    )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == max_attempts:
                    return DownloadResult(
                        url=url,
                        final_url=url,
                        access_status="DOWNLOAD_FAILED",
                        error=last_error,
                        attempts=attempt,
                    )
            if attempt < max_attempts:
                time.sleep(min(8, 2**attempt))
        return DownloadResult(
            url=url,
            final_url=url,
            access_status="DOWNLOAD_FAILED",
            error=last_error or "unknown download failure",
            attempts=max_attempts,
        )

    def snapshot_html(
        self,
        url: str,
        target_dir: Path,
        request_context: RequestContext,
    ) -> DownloadResult:
        filename = f"{stable_document_id(request_context.source_id, url)}.html"
        return self.download(url, target_dir / filename, request_context, allow_html=True)

    def download_attachment(
        self,
        url: str,
        parent_document_id: str,
        target_dir: Path,
        request_context: RequestContext,
    ) -> Attachment:
        extension = self._extension(url, None)
        attachment_id = stable_document_id(parent_document_id, url)
        result = self.download(url, target_dir / f"{attachment_id}{extension}", request_context)
        status = (
            "DOWNLOAD_OK"
            if result.access_status == "DOWNLOAD_OK"
            else (
                "PERMISSION_BLOCKED"
                if result.access_status in {"HTTP_403", "JS_REQUIRED", "LOGIN_REQUIRED", "CAPTCHA_REQUIRED"}
                else "DOWNLOAD_FAILED"
            )
        )
        return Attachment(
            attachment_id=attachment_id,
            parent_document_id=parent_document_id,
            source_url=result.final_url or url,
            file_name=Path(result.file_path).name if result.file_path else None,
            content_type=result.content_type,
            file_path=result.file_path,
            sha256=result.sha256,
            size_bytes=result.size_bytes,
            status=status,
            notes=result.error or "",
        )
