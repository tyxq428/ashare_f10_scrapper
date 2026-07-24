from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

MAX_GRANT_TTL = timedelta(minutes=60)
GRANT_STATES = {"ISSUED", "RESERVED", "CONSUMED"}
LEDGER_ACTIVE_STATES = {"RESERVED", "CONSUMED"}


class CodexPolicyError(ValueError):
    pass


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexPolicyError(f"cannot load JSON policy document: {path}") from exc
    if not isinstance(value, dict):
        raise CodexPolicyError(f"document root must be an object: {path}")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def text_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def allowed_files_hash(paths: tuple[str, ...] | list[str]) -> str:
    normalized = "\n".join(sorted({item.strip() for item in paths if item.strip()}))
    return text_sha256(normalized)


def parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CodexPolicyError(f"{field} must be an RFC3339 UTC timestamp")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CodexPolicyError(f"{field} must be an RFC3339 UTC timestamp") from exc
    if result.tzinfo is None:
        raise CodexPolicyError(f"{field} must include UTC timezone")
    return result.astimezone(UTC)


def _required_string(value: dict[str, Any], field: str) -> str:
    raw = value.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise CodexPolicyError(f"{field} must be a non-empty string")
    return raw.strip()


def _sha(value: dict[str, Any], field: str) -> str:
    result = _required_string(value, field)
    if len(result) != 40 or any(ch not in "0123456789abcdef" for ch in result):
        raise CodexPolicyError(f"{field} must be a 40-character lowercase SHA")
    return result


def _digest(value: dict[str, Any], field: str) -> str:
    result = _required_string(value, field)
    prefix, separator, digest = result.partition(":")
    if prefix != "sha256" or not separator or len(digest) != 64:
        raise CodexPolicyError(f"{field} must be sha256 plus 64 hex")
    if any(ch not in "0123456789abcdef" for ch in digest):
        raise CodexPolicyError(f"{field} must be sha256 plus 64 hex")
    return result


@dataclass(frozen=True)
class CodexPolicy:
    mode: str
    manual_approval_required: bool
    allowed_actors: tuple[str, ...]
    auto_recovery_dispatch: bool
    allow_github_actions_bot: bool
    retry_failed_codex_job: bool
    calls_per_task: int
    calls_per_fingerprint: int
    recovery_generations: int
    automatic_second_session: int
    terminal_results: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> CodexPolicy:
        if value.get("schema_version") != 1:
            raise CodexPolicyError("codex policy schema_version must be 1")
        mode = value.get("mode")
        if mode not in {"disabled", "enabled"}:
            raise CodexPolicyError("codex policy mode must be disabled or enabled")
        actors = value.get("allowed_actors")
        if not isinstance(actors, list) or not actors or not all(
            isinstance(item, str) and item for item in actors
        ):
            raise CodexPolicyError("allowed_actors must be a non-empty string array")
        limits = value.get("limits")
        if not isinstance(limits, dict):
            raise CodexPolicyError("limits must be an object")

        def boolean(field: str) -> bool:
            raw = value.get(field)
            if not isinstance(raw, bool):
                raise CodexPolicyError(f"{field} must be boolean")
            return raw

        def non_negative(field: str) -> int:
            raw = limits.get(field)
            if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
                raise CodexPolicyError(
                    f"limits.{field} must be a non-negative integer"
                )
            return raw

        terminals = value.get("terminal_results")
        if not isinstance(terminals, list) or not terminals or not all(
            isinstance(item, str) and item for item in terminals
        ):
            raise CodexPolicyError(
                "terminal_results must be a non-empty string array"
            )

        policy = cls(
            mode=mode,
            manual_approval_required=boolean("manual_approval_required"),
            allowed_actors=tuple(actors),
            auto_recovery_dispatch=boolean("auto_recovery_dispatch"),
            allow_github_actions_bot=boolean("allow_github_actions_bot"),
            retry_failed_codex_job=boolean("retry_failed_codex_job"),
            calls_per_task=non_negative("calls_per_task"),
            calls_per_fingerprint=non_negative("calls_per_fingerprint"),
            recovery_generations=non_negative("recovery_generations"),
            automatic_second_session=non_negative("automatic_second_session"),
            terminal_results=tuple(terminals),
        )
        if not policy.manual_approval_required:
            raise CodexPolicyError("manual_approval_required must remain true")
        if policy.auto_recovery_dispatch:
            raise CodexPolicyError("auto_recovery_dispatch must remain false")
        if policy.allow_github_actions_bot:
            raise CodexPolicyError("allow_github_actions_bot must remain false")
        if policy.retry_failed_codex_job:
            raise CodexPolicyError("retry_failed_codex_job must remain false")
        if policy.recovery_generations != 0:
            raise CodexPolicyError("recovery_generations must remain zero")
        if policy.automatic_second_session != 0:
            raise CodexPolicyError("automatic_second_session must remain zero")
        if policy.calls_per_task != 1 or policy.calls_per_fingerprint != 1:
            raise CodexPolicyError("task and fingerprint call limits must equal one")
        return policy


@dataclass(frozen=True)
class CodexGrant:
    grant_id: str
    task_id: str
    approved_by: str
    approval_source: str
    descriptor_sha256: str
    task_commit_sha: str
    source_run_id: int
    source_commit_sha: str
    failure_fingerprint: str
    allowed_files_hash: str
    max_calls: int
    state: str
    issued_at_utc: datetime
    expires_at_utc: datetime

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> CodexGrant:
        if value.get("schema_version") != 1:
            raise CodexPolicyError("grant schema_version must be 1")
        source_run_id = value.get("source_run_id")
        if (
            isinstance(source_run_id, bool)
            or not isinstance(source_run_id, int)
            or source_run_id <= 0
        ):
            raise CodexPolicyError("grant.source_run_id must be positive")
        max_calls = value.get("max_calls")
        if isinstance(max_calls, bool) or max_calls != 1:
            raise CodexPolicyError("grant.max_calls must equal 1")
        state = value.get("state")
        if state not in GRANT_STATES:
            raise CodexPolicyError("grant.state is invalid")
        issued = parse_utc(value.get("issued_at_utc"), "grant.issued_at_utc")
        expires = parse_utc(value.get("expires_at_utc"), "grant.expires_at_utc")
        if expires <= issued:
            raise CodexPolicyError("grant expiration must follow issue time")
        if expires - issued > MAX_GRANT_TTL:
            raise CodexPolicyError("grant TTL must not exceed 60 minutes")
        approval_source = _required_string(value, "approval_source")
        if approval_source != "chatgpt_web":
            raise CodexPolicyError("approval_source must be chatgpt_web")
        return cls(
            grant_id=_required_string(value, "grant_id"),
            task_id=_required_string(value, "task_id"),
            approved_by=_required_string(value, "approved_by"),
            approval_source=approval_source,
            descriptor_sha256=_digest(value, "descriptor_sha256"),
            task_commit_sha=_sha(value, "task_commit_sha"),
            source_run_id=source_run_id,
            source_commit_sha=_sha(value, "source_commit_sha"),
            failure_fingerprint=_required_string(
                value, "failure_fingerprint"
            ),
            allowed_files_hash=_digest(value, "allowed_files_hash"),
            max_calls=max_calls,
            state=state,
            issued_at_utc=issued,
            expires_at_utc=expires,
        )

    def is_active(self, now: datetime) -> bool:
        return (
            self.state == "ISSUED"
            and self.issued_at_utc <= now.astimezone(UTC) < self.expires_at_utc
        )


def ledger_entries(path: Path) -> list[dict[str, Any]]:
    value = load_object(path)
    schema_version = value.get("schema_version")
    entries = value.get("entries")
    if schema_version == 1 and entries == []:
        return []
    if schema_version != 2:
        raise CodexPolicyError("usage ledger schema_version must be 2")
    if not isinstance(entries, list) or not all(
        isinstance(item, dict) for item in entries
    ):
        raise CodexPolicyError("usage ledger entries must be an object array")
    return entries


def reserve_grant(
    grant: CodexGrant,
    entries: list[dict[str, Any]],
    *,
    run_id: int,
    reserved_at_utc: str,
) -> dict[str, Any]:
    if grant.state != "ISSUED":
        raise CodexPolicyError("grant is not in ISSUED state")
    for entry in entries:
        if entry.get("state") not in LEDGER_ACTIVE_STATES:
            continue
        if entry.get("grant_id") == grant.grant_id:
            raise CodexPolicyError("GRANT_ALREADY_CONSUMED")
        if entry.get("task_id") == grant.task_id:
            raise CodexPolicyError("TASK_CALL_BUDGET_EXHAUSTED")
        if entry.get("failure_fingerprint") == grant.failure_fingerprint:
            raise CodexPolicyError("FINGERPRINT_ALREADY_USED")
    return {
        "grant_id": grant.grant_id,
        "task_id": grant.task_id,
        "task_commit_sha": grant.task_commit_sha,
        "failure_fingerprint": grant.failure_fingerprint,
        "state": "RESERVED",
        "run_id": run_id,
        "reserved_at_utc": reserved_at_utc,
        "consumed_at_utc": None,
        "result": None,
    }


def consume_reservation(
    entry: dict[str, Any],
    *,
    consumed_at_utc: str,
    result: str,
) -> dict[str, Any]:
    if entry.get("state") != "RESERVED":
        raise CodexPolicyError("only RESERVED entries can be consumed")
    value = dict(entry)
    value.update(
        {
            "state": "CONSUMED",
            "consumed_at_utc": consumed_at_utc,
            "result": result,
        }
    )
    return value
