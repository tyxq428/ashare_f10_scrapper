from __future__ import annotations

import argparse
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
            delta = node.get("delta")
            if node_type == "response.output_text.delta" and isinstance(delta, str):
                parts.append(delta)
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return "".join(parts)


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("devflow-artifacts/relay-health.json"))
    args = parser.parse_args()

    endpoint = normalize_responses_endpoint(os.environ["AGENT_RESPONSES_ENDPOINT"])
    payload = {
        "model": os.environ["AGENT_MODEL"],
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Reply with exactly {EXPECTED} and nothing else.",
                    }
                ],
            }
        ],
        "reasoning": {"effort": "none"},
        "max_output_tokens": 32,
        "stream": True,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['AGENT_API_KEY']}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "ashare-f10-relay-health/1.0",
        },
        method="POST",
    )

    event_count = 0
    completed = False
    failed = False
    text_parts: list[str] = []
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0]
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
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
                if event_type == "response.output_text.delta":
                    text_parts.append(str(event.get("delta") or ""))
                elif event_type == "response.output_text.done" and not text_parts:
                    text_parts.append(str(event.get("text") or ""))
                elif event_type == "response.completed":
                    completed = True
                    if not text_parts:
                        text_parts.append(extract_text(event))
                elif event_type == "response.failed":
                    failed = True
        output = "".join(text_parts).strip()
        passed = status == 200 and completed and not failed and output == EXPECTED
        summary = {
            "status": "PASS" if passed else "FAIL",
            "http_status_class": f"{status // 100}xx",
            "content_type_is_event_stream": content_type.strip() == "text/event-stream",
            "event_count": event_count,
            "response_completed": completed,
            "response_failed": failed,
            "expected_output_matched": output == EXPECTED,
            "failure_class": None if passed else "PROTOCOL_OR_OUTPUT_MISMATCH",
        }
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        if status in {401, 403}:
            failure_class = "AUTH_FAILED"
        elif status == 404:
            failure_class = "RESPONSES_ENDPOINT_NOT_FOUND"
        elif status == 429:
            failure_class = "RATE_LIMITED"
        elif 500 <= status <= 599:
            failure_class = "UPSTREAM_SERVER_ERROR"
        else:
            failure_class = "HTTP_ERROR"
        summary = {
            "status": "FAIL",
            "http_status_class": f"{status // 100}xx",
            "failure_class": failure_class,
        }
    except urllib.error.URLError:
        summary = {"status": "FAIL", "failure_class": "TRANSPORT_ERROR"}
    except Exception:
        summary = {"status": "FAIL", "failure_class": "UNCLASSIFIED_SAFE_ERROR"}

    write_summary(args.output, summary)
    print(f"RELAY_HEALTH={summary['status']}")
    if summary.get("failure_class"):
        print(f"RELAY_FAILURE_CLASS={summary['failure_class']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
