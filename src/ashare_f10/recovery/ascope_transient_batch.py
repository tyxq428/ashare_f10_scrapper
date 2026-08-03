from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


QUOTE_GROUP_ID = "ef08aa02d7e84c00"
QUOTE_FAMILY = "/api/qt/stock/get"
QUOTE_STRATEGY = "union_quote_fields"
HTTP_502_ATTEMPT = re.compile(
    r"attempt\s+\d+:\s+HTTPError:\s+HTTP\s+502",
    re.IGNORECASE,
)
TIME_BUDGET_ERROR_CODE = "TIME_BUDGET_REACHED"
TIME_BUDGET_MESSAGES = {
    "Soft deadline reached before another stock attempt",
    "Soft deadline reached before the stock started",
}
SUCCESS_STATUSES = {"COMPLETED", "COMPLETED_WITH_GAPS"}
AUTHORIZED_RECOVERABLE_STATUSES = {
    *SUCCESS_STATUSES,
    "FAILED_RETRYABLE",
    "DEFERRED_TIME_BUDGET",
}


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
            f"{security_id} quote error is not exclusively HTTP 502 attempts: "
            f"{errors[0]!r}"
        )
    return {
        **observed,
        "http_502_attempt_count": len(matches),
        "error": errors[0],
    }


def _verify_deferred_state(state: dict[str, Any], security_id: str) -> dict[str, Any]:
    error_code = str(state.get("error_code") or "")
    if error_code != TIME_BUDGET_ERROR_CODE:
        raise TransientBatchVerificationError(
            f"{security_id} deferred state has unexpected error_code={error_code!r}"
        )
    if not bool(state.get("retryable")):
        raise TransientBatchVerificationError(
            f"{security_id} deferred state is not marked retryable"
        )
    attempt_count = int(state.get("attempt_count") or 0)
    if attempt_count not in {0, 1}:
        raise TransientBatchVerificationError(
            f"{security_id} deferred state has unexpected attempt_count={attempt_count}"
        )
    message = str(state.get("message") or "")
    if message not in TIME_BUDGET_MESSAGES:
        raise TransientBatchVerificationError(
            f"{security_id} deferred state has unexpected message={message!r}"
        )
    return {
        "status": "DEFERRED_TIME_BUDGET",
        "error_code": error_code,
        "attempt_count": attempt_count,
        "message": message,
    }


def verify_recoverable_batch(batch_dir: Path) -> dict[str, Any]:
    """Verify only two fail-closed recovery classes for a completed batch.

    Authorized states are exact quote-group HTTP 502 failures and deterministic
    soft-deadline deferrals. Terminal failures, unknown retryable failures,
    conservation errors, and future rows remain hard blockers.
    """

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
            "terminal failures are outside the recoverable boundary: "
            f"{sorted(str(item.get('security_id')) for item in terminal)}"
        )
    unexpected = [
        item
        for item in stocks
        if str(item.get("status") or "") not in AUTHORIZED_RECOVERABLE_STATUSES
    ]
    if unexpected:
        raise TransientBatchVerificationError(
            "unexpected checkpoint statuses: "
            f"{sorted({str(item.get('status')) for item in unexpected})}"
        )

    successful = [
        item for item in stocks if str(item.get("status") or "") in SUCCESS_STATUSES
    ]
    retryable = [
        item for item in stocks if str(item.get("status") or "") == "FAILED_RETRYABLE"
    ]
    deferred = [
        item
        for item in stocks
        if str(item.get("status") or "") == "DEFERRED_TIME_BUDGET"
    ]
    if not retryable and not deferred:
        raise TransientBatchVerificationError(
            "no authorized retryable or deferred securities were found"
        )

    expected_counts = {
        "input_count": len(stocks),
        "successful_count": len(successful),
        "failed_count": len(retryable),
        "deferred_count": len(deferred),
    }
    for key, observed in expected_counts.items():
        if int(validation.get(key) or 0) != observed:
            raise TransientBatchVerificationError(
                f"checkpoint/validation {key} mismatch: "
                f"checkpoint={observed}, validation={validation.get(key)!r}"
            )

    quote_evidence: dict[str, Any] = {}
    for state in retryable:
        security_id = str(state.get("security_id") or "")
        if not security_id:
            raise TransientBatchVerificationError(
                "retryable state has no security_id"
            )
        if str(state.get("error_code") or "") != "F10_FETCH_FAILED":
            raise TransientBatchVerificationError(
                f"{security_id} has unexpected error_code={state.get('error_code')!r}"
            )
        if int(state.get("attempt_count") or 0) < 1:
            raise TransientBatchVerificationError(
                f"{security_id} has no consumed attempt budget"
            )
        combined = _read_json(
            batch_dir / "_f10_runs" / security_id / "combined.json"
        )
        quote_evidence[security_id] = _verify_failed_group(combined, security_id)

    deadline_evidence: dict[str, Any] = {}
    for state in deferred:
        security_id = str(state.get("security_id") or "")
        if not security_id:
            raise TransientBatchVerificationError(
                "deferred state has no security_id"
            )
        deadline_evidence[security_id] = _verify_deferred_state(state, security_id)

    retryable_ids = sorted(quote_evidence)
    deferred_ids = sorted(deadline_evidence)
    root_causes: list[dict[str, Any]] = []
    if retryable_ids:
        root_causes.append(
            {
                "status": "FAILED_RETRYABLE",
                "group_id": QUOTE_GROUP_ID,
                "family": QUOTE_FAMILY,
                "strategy": QUOTE_STRATEGY,
                "error_class": "HTTP_502_ONLY",
                "security_count": len(retryable_ids),
            }
        )
    if deferred_ids:
        root_causes.append(
            {
                "status": "DEFERRED_TIME_BUDGET",
                "error_code": TIME_BUDGET_ERROR_CODE,
                "error_class": "SOFT_DEADLINE_ONLY",
                "security_count": len(deferred_ids),
            }
        )

    return {
        "status": "PASS",
        "batch_id": str(
            validation.get("batch_id") or checkpoint.get("batch_id") or ""
        ),
        "batch_dir": str(batch_dir),
        "input_count": len(stocks),
        "successful_count": len(successful),
        "retryable_count": len(retryable_ids),
        "deferred_count": len(deferred_ids),
        "retryable_security_ids": retryable_ids,
        "deferred_security_ids": deferred_ids,
        "security_ids": sorted({*retryable_ids, *deferred_ids}),
        "authorized_root_causes": root_causes,
        "evidence": {
            "quote_http_502": quote_evidence,
            "soft_deadline": deadline_evidence,
        },
    }


def verify_transient_quote_502_batch(batch_dir: Path) -> dict[str, Any]:
    """Preserve the original strict HTTP-502-only verifier contract."""

    report = verify_recoverable_batch(batch_dir)
    if int(report["deferred_count"]) != 0:
        raise TransientBatchVerificationError("deferred securities are present")
    if int(report["retryable_count"]) == 0:
        raise TransientBatchVerificationError(
            "no FAILED_RETRYABLE securities were found"
        )
    root_cause = next(
        item
        for item in report["authorized_root_causes"]
        if item.get("status") == "FAILED_RETRYABLE"
    )
    return {
        "status": report["status"],
        "batch_id": report["batch_id"],
        "batch_dir": report["batch_dir"],
        "input_count": report["input_count"],
        "successful_count": report["successful_count"],
        "retryable_count": report["retryable_count"],
        "security_ids": report["retryable_security_ids"],
        "authorized_root_cause": {
            key: value
            for key, value in root_cause.items()
            if key not in {"status", "security_count"}
        },
        "evidence": report["evidence"]["quote_http_502"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an A-SCOPE batch is recoverable only through quote HTTP 502 "
            "retries."
        )
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
