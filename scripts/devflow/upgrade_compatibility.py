from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from state_model import StateError, TaskState
from task_descriptor import TaskDescriptor, TaskDescriptorError

FIXTURE_FILES = {
    "state_v1_done": "state-v1-done.json",
    "state_v2_running": "state-v2-running.json",
    "descriptor_v1_low": "descriptor-v1-low.json",
    "descriptor_v2_xhigh": "descriptor-v2-xhigh.json",
    "descriptor_v2_low_invalid": "descriptor-v2-low-invalid.json",
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"fixture root must be object: {path}")
    return value


def preview_state_v2(value: dict[str, Any]) -> dict[str, Any]:
    """Return an idempotent migration preview without mutating input."""

    schema_version = value.get("schema_version")
    if schema_version == 2:
        TaskState.from_mapping(value)
        return deepcopy(value)
    if schema_version != 1:
        raise StateError(f"unsupported schema_version: {schema_version!r}")

    migrated = deepcopy(value)
    legacy_status = migrated.pop("research_acceptance_status", None)
    if not isinstance(legacy_status, str):
        raise StateError("schema v1 migration requires research_acceptance_status")
    migrated["schema_version"] = 2
    migrated["acceptance"] = {
        "domain": "research",
        "status": legacy_status,
        "reason_code": None,
        "details_path": None,
    }
    if "security_status" not in migrated:
        migrated["security_status"] = "PASS" if migrated.get("status") == "DONE" else "PENDING"
    TaskState.from_mapping(migrated)
    return migrated


def run_matrix(fixtures_root: Path) -> dict[str, Any]:
    cases: dict[str, dict[str, object]] = {}
    errors: list[str] = []

    def record(name: str, function) -> None:
        try:
            details = function()
        except Exception as exc:
            cases[name] = {
                "status": "FAIL",
                "error_type": type(exc).__name__,
                "error": str(exc)[:300],
            }
            errors.append(name)
        else:
            cases[name] = {"status": "PASS", **(details or {})}

    state_v1 = load_object(fixtures_root / FIXTURE_FILES["state_v1_done"])
    state_v2 = load_object(fixtures_root / FIXTURE_FILES["state_v2_running"])
    descriptor_v1 = load_object(fixtures_root / FIXTURE_FILES["descriptor_v1_low"])
    descriptor_v2 = load_object(fixtures_root / FIXTURE_FILES["descriptor_v2_xhigh"])
    descriptor_v2_low = load_object(fixtures_root / FIXTURE_FILES["descriptor_v2_low_invalid"])

    def check_state_v1() -> dict[str, object]:
        state = TaskState.from_mapping(state_v1)
        return {"schema_version": state.schema_version, "task_status": state.status}

    record("state_v1_read", check_state_v1)

    def check_state_v2() -> dict[str, object]:
        state = TaskState.from_mapping(state_v2)
        return {"schema_version": state.schema_version, "task_status": state.status}

    record("state_v2_read", check_state_v2)

    def check_descriptor_v1() -> dict[str, object]:
        task = TaskDescriptor.from_mapping(descriptor_v1)
        if task.effective_reasoning_effort != "xhigh":
            raise AssertionError("legacy metadata lowered runtime effort")
        return {
            "schema_version": task.schema_version,
            "metadata_effort": task.reasoning_effort,
            "effective_effort": task.effective_reasoning_effort,
        }

    record("descriptor_v1_low_read", check_descriptor_v1)

    def check_descriptor_v2() -> dict[str, object]:
        task = TaskDescriptor.from_mapping(descriptor_v2)
        return {
            "schema_version": task.schema_version,
            "effective_effort": task.effective_reasoning_effort,
        }

    record("descriptor_v2_xhigh_read", check_descriptor_v2)

    def check_v2_low_rejected() -> dict[str, object]:
        try:
            TaskDescriptor.from_mapping(descriptor_v2_low)
        except TaskDescriptorError:
            return {"rejected": True}
        raise AssertionError("schema v2 low descriptor was accepted")

    record("descriptor_v2_low_rejected", check_v2_low_rejected)

    def check_state_migration() -> dict[str, object]:
        before = deepcopy(state_v1)
        preview = preview_state_v2(state_v1)
        repeated = preview_state_v2(preview)
        if state_v1 != before:
            raise AssertionError("migration preview mutated input")
        if preview != repeated:
            raise AssertionError("migration preview is not idempotent")
        if preview.get("status") != "DONE":
            raise AssertionError("completed state was reopened")
        return {
            "status_preserved": preview["status"],
            "schema_version": preview["schema_version"],
            "idempotent": True,
        }

    record("state_v1_to_v2_preview", check_state_migration)

    def check_unknown_state_rejected() -> dict[str, object]:
        invalid = deepcopy(state_v2)
        invalid["schema_version"] = 99
        try:
            TaskState.from_mapping(invalid)
        except StateError:
            return {"rejected": True}
        raise AssertionError("unknown state schema was accepted")

    record("unknown_state_schema_rejected", check_unknown_state_rejected)

    def check_unknown_descriptor_rejected() -> dict[str, object]:
        invalid = deepcopy(descriptor_v2)
        invalid["schema_version"] = 99
        try:
            TaskDescriptor.from_mapping(invalid)
        except TaskDescriptorError:
            return {"rejected": True}
        raise AssertionError("unknown descriptor schema was accepted")

    record("unknown_descriptor_schema_rejected", check_unknown_descriptor_rejected)

    return {
        "status": "PASS" if not errors else "FAIL",
        "fixture_root": fixtures_root.as_posix(),
        "cases": cases,
        "failed_cases": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures-root", type=Path, default=Path("tests/fixtures/devflow")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("devflow-upgrade-compatibility.json")
    )
    args = parser.parse_args()

    result = run_matrix(args.fixtures_root.resolve())
    text = json.dumps(result, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
