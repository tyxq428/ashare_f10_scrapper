from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


QUOTE_GROUP_ID = "ef08aa02d7e84c00"
QUOTE_FAMILY = "/api/qt/stock/get"
QUOTE_STRATEGY = "union_quote_fields"
HTTP_502_ATTEMPT = re.compile(r"attempt\s+\d+:\s+HTTPError:\s+HTTP\s+502", re.IGNORECASE)


class TransientBatchVerificationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise TransientBatchVerificationError(f"required file is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TransientBatchVerificationError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise TransientBatchVerificationError(f"JSON root is not an object: {path}")
    return value


def _verify_failed_group(combined: dict[str, Any], security_id: str) -> dict[str, Any]:
    groups = list(combined.get("groups") or [])
    failed = [group for group in groups if not bool(group.get("success"))]
    if len(failed) != 1:
        raise TransientBatchVerificationError(
            f"{security_id} has {len(failed)} failed request groups; expected exactly one"
        )
    group = failed[0]
    observed = {
        "group_id": str(group.get("group_id") or ""),
        "family": str(group.get("family") or ""),
        "strategy": str(group.get("strategy") or ""),
        "record_count": int(group.get("record_count") or 0),
    }
    expected = {
        "group_id": QUOTE_GROUP_ID,
        "family": QUOTE_FAMILY,
        "strategy": QUOTE_STRATEGY,
        "record_count": 0,
    }
    if observed != expected:
        raise TransientBatchVerificationError(
            f"{security_id} failed group is outside the authorized quote boundary: "
            f"observed={observed}, expected={expected}"
        )
    errors = [str(item) for item in (group.get("errors") or [])]
    if len(errors) != 1:
        raise TransientBatchVerificationError(
            f"{security_id} quote group has {len(errors)} error records; expected one"
        )
    matches = HTTP_502_ATTEMPT.findall(errors[0])
    residual = HTTP_502_ATTEMPT.sub("", errors[0]).replace("；", "").strip()
    if len(matches) < 1 or residual:
        raise TransientBatchVerificationError(
            f"{security_id} quote error is not exclusively HTTP 502 attempts: {errors[0]!r}"
        )
    return {
        **observed,
        "http_502_attempt_count": len(matches),
        "error": errors[0],
    }


def verify_transient_quote_502_batch(batch_dir: Path) -> dict[str, Any]:
    validation = _read_json(batch_dir / "validation_report.json")
    checkpoint = _read_json(batch_dir / "checkpoint.json")

    if validation.get("status") != "FAILED_RECOVERABLE":
        raise TransientBatchVerificationError(
            f"batch status is not FAILED_RECOVERABLE: {validation.get('status')!r}"
        )
    if not bool(validation.get("conservation_pass")):
        raise TransientBatchVerificationError("security conservation did not pass")
    if int(validation.get("formal_future_rows") or 0) != 0:
        raise TransientBatchVerificationError("formal future rows are present")
    if int(validation.get("deferred_count") or 0) != 0:
        raise TransientBatchVerificationError("deferred securities are present")

    stocks = list(checkpoint.get("stocks") or [])
    if not stocks:
        raise TransientBatchVerificationError("checkpoint contains no stock states")
    terminal = [
        item
        for item in stocks
        if str(item.get("status") or "") in {"FAILED_TERMINAL", "BLOCKED"}
    ]
    if terminal:
        raise TransientBatchVerificationError(
            "terminal failures are outside the transient-recovery boundary: "
            f"{sorted(str(item.get('security_id')) for item in terminal)}"
        )
    retryable = [
        item for item in stocks if str(item.get("status") or "") == "FAILED_RETRYABLE"
    ]
    if not retryable:
        raise TransientBatchVerificationError("no FAILED_RETRYABLE securities were found")
    unexpected = [
        item
        for item in stocks
        if str(item.get("status") or "")
        not in {"COMPLETED", "COMPLETED_WITH_GAPS", "FAILED_RETRYABLE"}
    ]
    if unexpected:
        raise TransientBatchVerificationError(
            "unexpected checkpoint statuses: "
            f"{sorted({str(item.get('status')) for item in unexpected})}"
        )

    successful_count = sum(
        str(item.get("status") or "") in {"COMPLETED", "COMPLETED_WITH_GAPS"}
        for item in stocks
    )
    if successful_count != int(validation.get("successful_count") or 0):
        raise TransientBatchVerificationError(
            "checkpoint/validation successful-count mismatch"
        )
    if len(retryable) != int(validation.get("failed_count") or 0):
        raise TransientBatchVerificationError("checkpoint/validation failure-count mismatch")
    if len(stocks) != int(validation.get("input_count") or 0):
        raise TransientBatchVerificationError("checkpoint/validation input-count mismatch")

    evidence: dict[str, Any] = {}
    for state in retryable:
        security_id = str(state.get("security_id") or "")
        if not security_id:
            raise TransientBatchVerificationError("retryable state has no security_id")
        if str(state.get("error_code") or "") != "F10_FETCH_FAILED":
            raise TransientBatchVerificationError(
                f"{security_id} has unexpected error_code={state.get('error_code')!r}"
            )
        if int(state.get("attempt_count") or 0) < 1:
            raise TransientBatchVerificationError(
                f"{security_id} has no consumed attempt budget"
            )
        combined = _read_json(batch_dir / "_f10_runs" / security_id / "combined.json")
        evidence[security_id] = _verify_failed_group(combined, security_id)

    return {
        "status": "PASS",
        "batch_id": str(validation.get("batch_id") or checkpoint.get("batch_id") or ""),
        "batch_dir": str(batch_dir),
        "input_count": len(stocks),
        "successful_count": successful_count,
        "retryable_count": len(retryable),
        "security_ids": sorted(evidence),
        "authorized_root_cause": {
            "group_id": QUOTE_GROUP_ID,
            "family": QUOTE_FAMILY,
            "strategy": QUOTE_STRATEGY,
            "error_class": "HTTP_502_ONLY",
        },
        "evidence": evidence,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an A-SCOPE batch is recoverable only through quote HTTP 502 retries."
    )
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = verify_transient_quote_502_batch(args.batch_dir)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
