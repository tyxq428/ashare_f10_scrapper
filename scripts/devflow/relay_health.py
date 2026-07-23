from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from endpoint_utils import normalize_responses_endpoint

EXPECTED = "RELAY_HEALTH_OK"


def extract_text(value: Any) -> str:
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type in {"output_text", "response.output_text.done"}:
                text = node.get("text")
                if isinstance(text, str):
                    parts.append(text)
            if node_type == "response.output_text.delta" and isinstance(node.get("delta"), str):
                parts.append(node["delta"])
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return "".join(parts)


def write_summary(value: dict[str, object]) -> None:
    path = Path("relay-health-summary.json")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    endpoint = normalize_responses_endpoint(os.environ["AGENT_RESPONSES_ENDPOINT"])
    api_key = os.environ["AGENT_API_KEY"]
    model = os.environ["AGENT_MODEL"]
    payload = {
        "model": model,
        "input": f"Reply with exactly {EXPECTED} and nothing else.",
        "reasoning": {"effort": "none"},
        "max_output_tokens": 32,
        "stream": True,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "ashare-devflow-relay-health/1.0",
        },
        method="POST",
    )

    event_count = 0
    text_parts: list[str] = []
    completed = False
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                event_count += 1
                event_type = event.get("type")
                if event_type == "response.output_text.delta" and isinstance(event.get("delta"), str):
                    text_parts.append(event["delta"])
                elif event_type == "response.output_text.done" and not text_parts:
                    text_parts.append(str(event.get("text", "")))
                elif event_type == "response.completed":
                    completed = True
                    if not text_parts:
                        text_parts.append(extract_text(event))
                elif event_type == "response.failed":
                    completed = False
        matched = "".join(text_parts).strip() == EXPECTED
        passed = status == 200 and completed and matched
        write_summary(
            {
                "status": "PASS" if passed else "FAIL",
                "http_status_class": f"{status // 100}xx",
                "content_type_is_event_stream": content_type == "text/event-stream",
                "event_count": event_count,
                "response_completed": completed,
                "expected_output_matched": matched,
                "failure_class": None if passed else "PROTOCOL_OR_OUTPUT_MISMATCH",
            }
        )
        print(f"RELAY_HEALTH_STATUS={'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        if status in {401, 403}:
            failure = "AUTH_FAILED"
        elif status == 404:
            failure = "RESPONSES_ENDPOINT_NOT_FOUND"
        elif status == 429:
            failure = "RATE_LIMITED"
        elif 500 <= status <= 599:
            failure = "UPSTREAM_SERVER_ERROR"
        else:
            failure = "HTTP_ERROR"
        write_summary({"status": "FAIL", "http_status_class": f"{status // 100}xx", "failure_class": failure})
        print(f"RELAY_HEALTH_FAILURE_CLASS={failure}")
        return 1
    except Exception:
        write_summary({"status": "FAIL", "failure_class": "TRANSPORT_OR_UNCLASSIFIED_ERROR"})
        print("RELAY_HEALTH_FAILURE_CLASS=TRANSPORT_OR_UNCLASSIFIED_ERROR")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
