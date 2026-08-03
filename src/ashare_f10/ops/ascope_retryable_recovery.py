from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SUCCESS_STATES = {"COMPLETED", "COMPLETED_WITH_GAPS"}
RETRYABLE_STATES = {"FAILED_RETRYABLE"}
TERMINAL_STATES = {"FAILED_TERMINAL", "BLOCKED"}
EXPECTED_GROUP_ID = "ef08aa02d7e84c00"
EXPECTED_FAMILY = "/api/qt/stock/get"
EXPECTED_STRATEGY = "union_quote_fields"
HTTP_CODE_RE = re.compile(r"HTTP(?:Error:)?\s*HTTP\s+(\d{3})|HTTP\s+(\d{3})", re.I)


class RecoveryContractError(RuntimeError):
    """Raised when a checkpoint is outside the audited recovery boundary."""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RecoveryContractError(f"required file is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryContractError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RecoveryContractError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _http_codes(errors: list[Any]) -> set[str]:
    codes: set[str] = set()
    for error in errors:
        for first, second in HTTP_CODE_RE.findall(str(error)):
            codes.add(first or second)
    return codes


def _inspect_quote_502(batch_dir: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    security_id = str(state.get("security_id") or "")
    if not security_id:
        raise RecoveryContractError("retryable state is missing security_id")
    group_dir = batch_dir / "_f10_runs" / security_id / "groups"
    if not group_dir.is_dir():
        raise RecoveryContractError(f"failed group directory is missing for {security_id}")

    failed_groups = []
    for path in sorted(group_dir.glob("*.json")):
        value = _read_json(path)
        if not bool(value.get("success")):
            failed_groups.append(value)
    if not failed_groups:
        raise RecoveryContractError(f"no failed request group evidence for {security_id}")

    evidence = []
    for group in failed_groups:
        group_id = str(group.get("group_id") or "")
        family = str(group.get("family") or "")
        strategy = str(group.get("strategy") or "")
        errors = list(group.get("errors") or [])
        codes = _http_codes(errors)
        if (
            group_id != EXPECTED_GROUP_ID
            or family != EXPECTED_FAMILY
            or strategy != EXPECTED_STRATEGY
            or codes != {"502"}
        ):
            raise RecoveryContractError(
                "retryable failure is outside the verified quote HTTP-502 boundary: "
                f"security_id={security_id}, group_id={group_id!r}, family={family!r}, "
                f"strategy={strategy!r}, http_codes={sorted(codes)}, errors={errors}"
            )
        evidence.append(
            {
                "group_id": group_id,
                "family": family,
                "strategy": strategy,
                "http_codes": sorted(codes),
                "errors": errors,
            }
        )
    return evidence


def inspect_batch(batch_dir: Path) -> dict[str, Any]:
    validation = _read_json(batch_dir / "validation_report.json")
    checkpoint = _read_json(batch_dir / "checkpoint.json")
    batch_id = str(validation.get("batch_id") or checkpoint.get("batch_id") or batch_dir.name)
    stocks = list(checkpoint.get("stocks") or [])
    if not stocks:
        raise RecoveryContractError(f"{batch_id}: checkpoint contains no stock states")
    if not bool(validation.get("conservation_pass")):
        raise RecoveryContractError(f"{batch_id}: security conservation failed")
    if int(validation.get("formal_future_rows") or 0) != 0:
        raise RecoveryContractError(f"{batch_id}: formal future rows are present")

    non_success = [item for item in stocks if str(item.get("status")) not in SUCCESS_STATES]
    if not non_success:
        if str(validation.get("status")) not in {"PASS", "PASS_WITH_GAPS"}:
            raise RecoveryContractError(
                f"{batch_id}: all stocks succeeded but validation status is "
                f"{validation.get('status')!r}"
            )
        return {
            "batch_id": batch_id,
            "classification": "SUCCESS",
            "input_count": len(stocks),
            "retryable_count": 0,
            "retryable_securities": [],
        }

    terminal = [item for item in non_success if str(item.get("status")) in TERMINAL_STATES]
    if terminal:
        raise RecoveryContractError(
            f"{batch_id}: terminal failures cannot be automatically retried: "
            f"{sorted(str(item.get('security_id')) for item in terminal)}"
        )
    unexpected = [
        item for item in non_success if str(item.get("status")) not in RETRYABLE_STATES
    ]
    if unexpected:
        raise RecoveryContractError(
            f"{batch_id}: unsupported non-success states: "
            f"{[(item.get('security_id'), item.get('status')) for item in unexpected]}"
        )
    if str(validation.get("status")) != "FAILED_RECOVERABLE":
        raise RecoveryContractError(
            f"{batch_id}: retryable stocks require FAILED_RECOVERABLE validation status"
        )

    retryable = []
    for state in non_success:
        security_id = str(state.get("security_id") or "")
        if not bool(state.get("retryable")):
            raise RecoveryContractError(f"{batch_id}/{security_id}: retryable flag is false")
        if str(state.get("error_code") or "") != "F10_FETCH_FAILED":
            raise RecoveryContractError(
                f"{batch_id}/{security_id}: unexpected error_code="
                f"{state.get('error_code')!r}"
            )
        retryable.append(
            {
                "security_id": security_id,
                "prior_attempt_count": int(state.get("attempt_count") or 0),
                "error_code": str(state.get("error_code") or ""),
                "evidence": _inspect_quote_502(batch_dir, state),
            }
        )

    failed_count = int(validation.get("failed_count") or 0)
    if failed_count != len(retryable):
        raise RecoveryContractError(
            f"{batch_id}: validation failed_count={failed_count}, "
            f"checkpoint retryable={len(retryable)}"
        )
    return {
        "batch_id": batch_id,
        "classification": "RETRYABLE_QUOTE_HTTP_502",
        "input_count": len(stocks),
        "retryable_count": len(retryable),
        "retryable_securities": retryable,
    }


def plan_rollout_recovery(batch_root: Path, *, expected_batches: int = 27) -> dict[str, Any]:
    expected = [f"B{index:03d}" for index in range(1, expected_batches + 1)]
    success_batches: list[str] = []
    retry_batches: list[str] = []
    batch_results: list[dict[str, Any]] = []
    for batch_id in expected:
        result = inspect_batch(batch_root / batch_id)
        if result["batch_id"] != batch_id:
            raise RecoveryContractError(
                f"batch directory mismatch: expected={batch_id}, "
                f"observed={result['batch_id']}"
            )
        batch_results.append(result)
        if result["classification"] == "SUCCESS":
            success_batches.append(batch_id)
        else:
            retry_batches.append(batch_id)

    return {
        "schema_version": 1,
        "status": "READY_FOR_TARGETED_RETRY" if retry_batches else "READY_FOR_REDUCTION",
        "observed_at_utc": utc_now(),
        "expected_batch_count": expected_batches,
        "success_batch_count": len(success_batches),
        "retry_batch_count": len(retry_batches),
        "success_batches": success_batches,
        "retry_batches": retry_batches,
        "retry_matrix": {"include": [{"batch_id": value} for value in retry_batches]},
        "batches": batch_results,
    }


def reset_retryable_batch(batch_dir: Path) -> dict[str, Any]:
    inspection = inspect_batch(batch_dir)
    if inspection["classification"] != "RETRYABLE_QUOTE_HTTP_502":
        raise RecoveryContractError(
            f"{inspection['batch_id']}: batch does not require retryable recovery"
        )

    checkpoint_path = batch_dir / "checkpoint.json"
    checkpoint = _read_json(checkpoint_path)
    allowed = {
        str(item["security_id"]): item for item in inspection["retryable_securities"]
    }
    reset_at = utc_now()
    changed = []
    for state in checkpoint.get("stocks", []):
        security_id = str(state.get("security_id") or "")
        if security_id not in allowed:
            continue
        history = list(state.get("recovery_history") or [])
        history.append(
            {
                "recovered_at_utc": reset_at,
                "recovery_type": "AUDITED_RETRYABLE_RESET",
                "prior_status": state.get("status"),
                "prior_attempt_count": state.get("attempt_count"),
                "prior_error_code": state.get("error_code"),
                "prior_message": state.get("message"),
                "prior_details": state.get("details") or {},
                "reason": "verified transient /api/qt/stock/get union_quote_fields HTTP 502",
                "evidence": allowed[security_id]["evidence"],
            }
        )
        changed.append(
            {
                "security_id": security_id,
                "prior_attempt_count": int(state.get("attempt_count") or 0),
            }
        )
        state.update(
            status="PENDING",
            attempt_count=0,
            started_at_utc=None,
            completed_at_utc=None,
            updated_at_utc=reset_at,
            retryable=False,
            error_code="",
            message="",
            details={},
            recovery_history=history,
        )

    if {item["security_id"] for item in changed} != set(allowed):
        raise RecoveryContractError(
            f"{inspection['batch_id']}: reset set changed during checkpoint mutation"
        )
    checkpoint["status"] = "RUNNING"
    checkpoint["updated_at_utc"] = reset_at
    checkpoint["retry_recovery_generation"] = int(
        checkpoint.get("retry_recovery_generation") or 0
    ) + 1
    _write_json(checkpoint_path, checkpoint)
    return {
        "schema_version": 1,
        "status": "PASS",
        "batch_id": inspection["batch_id"],
        "reset_at_utc": reset_at,
        "reset_count": len(changed),
        "reset_securities": changed,
        "checkpoint_path": str(checkpoint_path),
    }


def _append_github_output(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _plan_command(args: argparse.Namespace) -> int:
    try:
        report = plan_rollout_recovery(
            args.batch_root,
            expected_batches=args.expected_batches,
        )
    except Exception as exc:  # noqa: BLE001
        blocked = {
            "schema_version": 1,
            "status": "BLOCKED",
            "observed_at_utc": utc_now(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        if args.report:
            _write_json(args.report, blocked)
        print(json.dumps(blocked, ensure_ascii=False, indent=2))
        return 1
    if args.report:
        _write_json(args.report, report)
    if args.github_output:
        _append_github_output(
            args.github_output,
            {
                "retry_matrix": json.dumps(
                    report["retry_matrix"], separators=(",", ":")
                ),
                "retry_count": str(report["retry_batch_count"]),
                "plan_status": str(report["status"]),
            },
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _reset_command(args: argparse.Namespace) -> int:
    try:
        report = reset_retryable_batch(args.batch_dir)
    except Exception as exc:  # noqa: BLE001
        blocked = {
            "schema_version": 1,
            "status": "BLOCKED",
            "observed_at_utc": utc_now(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        if args.report:
            _write_json(args.report, blocked)
        print(json.dumps(blocked, ensure_ascii=False, indent=2))
        return 1
    if args.report:
        _write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan and execute audited A-SCOPE retryable batch recovery."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan")
    plan.add_argument("batch_root", type=Path)
    plan.add_argument("--expected-batches", type=int, default=27)
    plan.add_argument("--report", type=Path)
    plan.add_argument("--github-output", type=Path)
    plan.set_defaults(handler=_plan_command)

    reset = subparsers.add_parser("reset")
    reset.add_argument("batch_dir", type=Path)
    reset.add_argument("--report", type=Path)
    reset.set_defaults(handler=_reset_command)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
