from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from endpoint_utils import normalize_responses_endpoint

UPSTREAM_ENDPOINT = normalize_responses_endpoint(os.environ["AGENT_RESPONSES_ENDPOINT"])


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": {"type": "not_found"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/v1/responses":
            self._send_json(404, {"error": {"type": "not_found"}})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": {"type": "invalid_request"}})
            return
        if content_length <= 0 or content_length > 16 * 1024 * 1024:
            self._send_json(400, {"error": {"type": "invalid_request"}})
            return

        body = self.rfile.read(content_length)
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            self._send_json(401, {"error": {"type": "authentication_error"}})
            return

        request = urllib.request.Request(
            UPSTREAM_ENDPOINT,
            data=body,
            headers={
                "Authorization": authorization,
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "Accept": self.headers.get("Accept", "text/event-stream"),
                "User-Agent": "ashare-devflow-private-forwarder/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as upstream:
                self.send_response(int(upstream.status))
                self.send_header(
                    "Content-Type", upstream.headers.get("Content-Type", "text/event-stream")
                )
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = upstream.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                self.close_connection = True
        except urllib.error.HTTPError as exc:
            self._send_json(
                int(exc.code),
                {"error": {"type": "upstream_http_error", "message": "upstream request failed"}},
            )
        except Exception:
            self._send_json(
                502,
                {"error": {"type": "upstream_transport_error", "message": "upstream request failed"}},
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.serve_forever(poll_interval=0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
