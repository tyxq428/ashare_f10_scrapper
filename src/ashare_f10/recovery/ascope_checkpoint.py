from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def reset_terminal_failures(
    checkpoint_path: Path,
    *,
    security_ids: set[str],
    expected_error_code: str = "F10_FETCH_FAILED",
    require_exact_failed_set: bool = True,
) -> dict[str, Any]:
    if not checkpoint_path.exists():
        raise FileNotFoundError(checkpoint_path)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    stocks = list(checkpoint.get("stocks") or [])
    if not stocks:
        raise ValueError("checkpoint contains no stock states")
    if not security_ids:
        raise ValueError("at least one security_id is required")

    terminal = {
        str(item.get("security_id")): item
        for item in stocks
        if item.get("status") in {"FAILED_TERMINAL", "BLOCKED"}
    }
    terminal_ids = set(terminal)
    if require_exact_failed_set and terminal_ids != security_ids:
        raise ValueError(
            "requested recovery set does not match checkpoint terminal failures: "
            f"requested={sorted(security_ids)}, terminal={sorted(terminal_ids)}"
        )
    missing = security_ids - terminal_ids
    if missing:
        raise ValueError(f"requested securities are not terminal failures: {sorted(missing)}")

    recovered_at = utc_now()
    changed: list[dict[str, Any]] = []
    for security_id in sorted(security_ids):
        state = terminal[security_id]
        error_code = str(state.get("error_code") or "")
        if error_code != expected_error_code:
            raise ValueError(
                f"{security_id} error_code={error_code!r}, expected {expected_error_code!r}"
            )
        history = list(state.get("recovery_history") or [])
        history.append(
            {
                "recovered_at_utc": recovered_at,
                "prior_status": state.get("status"),
                "prior_attempt_count": state.get("attempt_count"),
                "prior_error_code": error_code,
                "prior_message": state.get("message"),
                "prior_details": state.get("details") or {},
                "reason": "deterministic exporter root cause fixed; retry explicitly authorized",
            }
        )
        changed.append(
            {
                "security_id": security_id,
                "prior_status": state.get("status"),
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
        "unchanged_terminal_count": len(terminal_ids - security_ids),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset an explicitly authorized set of terminal A-SCOPE stock states."
    )
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument(
        "--security-id",
        action="append",
        required=True,
        dest="security_ids",
        help="Exact security_id to reset; repeat for each authorized terminal failure.",
    )
    parser.add_argument("--expected-error-code", default="F10_FETCH_FAILED")
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--allow-other-terminal-failures",
        action="store_true",
        help="Do not require the requested set to equal all terminal failures.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = reset_terminal_failures(
        args.checkpoint,
        security_ids=set(args.security_ids),
        expected_error_code=args.expected_error_code,
        require_exact_failed_set=not args.allow_other_terminal_failures,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
