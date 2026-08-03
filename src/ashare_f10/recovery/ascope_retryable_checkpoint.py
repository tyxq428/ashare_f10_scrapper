from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RETRYABLE_STATUSES = {"FAILED_RETRYABLE", "DEFERRED_TIME_BUDGET"}
STATUS_ERROR_CODES = {
    "FAILED_RETRYABLE": "F10_FETCH_FAILED",
    "DEFERRED_TIME_BUDGET": "TIME_BUDGET_REACHED",
}
DEFERRED_RECOVERY_REASON = (
    "verified deterministic soft-deadline deferral; "
    "post-rollout bounded continuation authorized"
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _expected_error_code(prior_status: str, requested_code: str) -> str:
    """Preserve the legacy workflow call while validating status-specific codes."""

    if requested_code == "F10_FETCH_FAILED" and prior_status in STATUS_ERROR_CODES:
        return STATUS_ERROR_CODES[prior_status]
    return requested_code


def reset_retryable_failures(
    checkpoint_path: Path,
    *,
    security_ids: set[str],
    expected_error_code: str = "F10_FETCH_FAILED",
    expected_statuses: set[str] | None = None,
    require_exact_failed_set: bool = True,
    reason: str = "transient upstream root cause confirmed; bounded retry explicitly authorized",
) -> dict[str, Any]:
    """Reset an exact, audited retryable set without touching successful securities.

    A normal resume keeps the prior ``attempt_count``. Once that value already
    equals the bounded ``max_attempts``, the next attempt range is empty. This
    helper deliberately resets both status and attempt budget only after an
    external root-cause verifier has authorized the exact security set.

    The default status set includes both explicit upstream failures and
    deterministic soft-deadline deferrals. The existing finalizer still passes
    ``expected_error_code='F10_FETCH_FAILED'``; that legacy call is interpreted
    status-by-status, so deferred states must still carry the exact
    ``TIME_BUDGET_REACHED`` code rather than silently bypassing validation.
    """

    if not checkpoint_path.exists():
        raise FileNotFoundError(checkpoint_path)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    stocks = list(checkpoint.get("stocks") or [])
    if not stocks:
        raise ValueError("checkpoint contains no stock states")
    if not security_ids:
        raise ValueError("at least one security_id is required")

    allowed_statuses = set(expected_statuses or RETRYABLE_STATUSES)
    if not allowed_statuses or not allowed_statuses <= RETRYABLE_STATUSES:
        raise ValueError(f"invalid expected retryable statuses: {sorted(allowed_statuses)}")

    retryable = {
        str(item.get("security_id")): item
        for item in stocks
        if str(item.get("status") or "") in allowed_statuses
    }
    retryable_ids = set(retryable)
    if require_exact_failed_set and retryable_ids != security_ids:
        raise ValueError(
            "requested recovery set does not match checkpoint retryable failures: "
            f"requested={sorted(security_ids)}, retryable={sorted(retryable_ids)}"
        )
    missing = security_ids - retryable_ids
    if missing:
        raise ValueError(
            f"requested securities are not authorized retryable failures: {sorted(missing)}"
        )

    recovered_at = utc_now()
    changed: list[dict[str, Any]] = []
    for security_id in sorted(security_ids):
        state = retryable[security_id]
        prior_status = str(state.get("status") or "")
        error_code = str(state.get("error_code") or "")
        wanted_error_code = _expected_error_code(prior_status, expected_error_code)
        if error_code != wanted_error_code:
            raise ValueError(
                f"{security_id} error_code={error_code!r}, "
                f"expected {wanted_error_code!r} for status {prior_status!r}"
            )
        history_reason = (
            DEFERRED_RECOVERY_REASON
            if prior_status == "DEFERRED_TIME_BUDGET"
            else reason
        )
        history = list(state.get("recovery_history") or [])
        history.append(
            {
                "recovered_at_utc": recovered_at,
                "prior_status": prior_status,
                "prior_attempt_count": state.get("attempt_count"),
                "prior_error_code": error_code,
                "prior_message": state.get("message"),
                "prior_details": state.get("details") or {},
                "reason": history_reason,
            }
        )
        changed.append(
            {
                "security_id": security_id,
                "prior_status": prior_status,
                "prior_attempt_count": state.get("attempt_count"),
                "prior_error_code": error_code,
            }
        )
        state.update(
            status="PENDING",
            attempt_count=0,
            started_at_utc=None,
            completed_at_utc=None,
            updated_at_utc=recovered_at,
            retryable=False,
            error_code="",
            message="",
            details={},
            recovery_history=history,
        )

    checkpoint["status"] = "RUNNING"
    checkpoint["updated_at_utc"] = recovered_at
    _atomic_json(checkpoint_path, checkpoint)
    return {
        "status": "PASS",
        "checkpoint_path": str(checkpoint_path),
        "recovered_at_utc": recovered_at,
        "recovered_count": len(changed),
        "recovered_securities": changed,
        "unchanged_retryable_count": len(retryable_ids - security_ids),
        "unchanged_success_count": sum(
            str(item.get("status") or "") in {"COMPLETED", "COMPLETED_WITH_GAPS"}
            for item in stocks
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset an exact authorized set of retryable A-SCOPE stock states."
    )
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument(
        "--security-id",
        action="append",
        required=True,
        dest="security_ids",
        help="Exact security_id to reset; repeat for each authorized retryable failure.",
    )
    parser.add_argument("--expected-error-code", default="F10_FETCH_FAILED")
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--allow-other-retryable-failures",
        action="store_true",
        help="Do not require the requested set to equal all retryable failures.",
    )
    parser.add_argument(
        "--reason",
        default="transient upstream root cause confirmed; bounded retry explicitly authorized",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = reset_retryable_failures(
        args.checkpoint,
        security_ids=set(args.security_ids),
        expected_error_code=args.expected_error_code,
        require_exact_failed_set=not args.allow_other_retryable_failures,
        reason=args.reason,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
