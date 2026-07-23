from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
                raise CodexPolicyError(f"limits.{field} must be a non-negative integer")
            return raw

        terminals = value.get("terminal_results")
        if not isinstance(terminals, list) or not terminals or not all(
            isinstance(item, str) and item for item in terminals
        ):
            raise CodexPolicyError("terminal_results must be a non-empty string array")

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
        if policy.auto_recovery_dispatch:
            raise CodexPolicyError("auto_recovery_dispatch must remain false")
        if policy.allow_github_actions_bot:
            raise CodexPolicyError("allow_github_actions_bot must remain false")
        if policy.retry_failed_codex_job:
            raise CodexPolicyError("retry_failed_codex_job must remain false")
        if policy.automatic_second_session != 0:
            raise CodexPolicyError("automatic_second_session must remain zero")
        return policy


@dataclass(frozen=True)
class CodexApproval:
    approval_id: str
    task_id: str
    approved_by: str
    approval_source: str
    descriptor_sha256: str
    failure_fingerprint: str
    max_calls: int
    issued_at_utc: datetime
    expires_at_utc: datetime

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> CodexApproval:
        if value.get("schema_version") != 1:
            raise CodexPolicyError("approval schema_version must be 1")
        required = (
            "approval_id",
            "task_id",
            "approved_by",
            "approval_source",
            "descriptor_sha256",
            "failure_fingerprint",
        )
        fields: dict[str, str] = {}
        for field in required:
            raw = value.get(field)
            if not isinstance(raw, str) or not raw.strip():
                raise CodexPolicyError(f"approval.{field} must be a non-empty string")
            fields[field] = raw.strip()
        if fields["approval_source"] != "chatgpt_web":
            raise CodexPolicyError("approval_source must be chatgpt_web")
        if not fields["descriptor_sha256"].startswith("sha256:"):
            raise CodexPolicyError("descriptor_sha256 must use sha256 prefix")
        max_calls = value.get("max_calls")
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls != 1:
            raise CodexPolicyError("approval.max_calls must equal 1")
        issued = parse_utc(value.get("issued_at_utc"), "approval.issued_at_utc")
        expires = parse_utc(value.get("expires_at_utc"), "approval.expires_at_utc")
        if expires <= issued:
            raise CodexPolicyError("approval expiration must follow issue time")
        return cls(
            approval_id=fields["approval_id"],
            task_id=fields["task_id"],
            approved_by=fields["approved_by"],
            approval_source=fields["approval_source"],
            descriptor_sha256=fields["descriptor_sha256"],
            failure_fingerprint=fields["failure_fingerprint"],
            max_calls=max_calls,
            issued_at_utc=issued,
            expires_at_utc=expires,
        )

    def is_active(self, now: datetime) -> bool:
        return self.issued_at_utc <= now.astimezone(UTC) < self.expires_at_utc


def ledger_entries(path: Path) -> list[dict[str, Any]]:
    value = load_object(path)
    if value.get("schema_version") != 1:
        raise CodexPolicyError("usage ledger schema_version must be 1")
    entries = value.get("entries")
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise CodexPolicyError("usage ledger entries must be an object array")
    return entries
