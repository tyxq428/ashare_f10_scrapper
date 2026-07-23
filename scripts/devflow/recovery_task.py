from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from task_descriptor import TaskDescriptorError, load_task_descriptor

SAFE_TEXT = re.compile(r"[^A-Za-z0-9 _./:+\-(),\[\]]+")


def safe_summary(text: str, *, limit: int = 500) -> str:
    normalized = " ".join(text.split())
    normalized = SAFE_TEXT.sub("?", normalized)
    return normalized[:limit]


def build_recovery_descriptor(
    original: dict[str, Any],
    *,
    source_run_id: int,
    reason_code: str,
    reason: str,
    expected_base_sha: str,
) -> dict[str, Any]:
    _descriptor = load_task_descriptor_from_mapping(original)
    generation = _descriptor.recovery_generation + 1
    if generation > _descriptor.max_recovery_generations:
        raise TaskDescriptorError("recovery generation budget exhausted")

    value = deepcopy(original)
    parent_task_id = _descriptor.parent_task_id or _descriptor.task_id
    base_task_id = parent_task_id
    value["task_id"] = f"{base_task_id}-recovery-g{generation}"
    value["parent_task_id"] = base_task_id
    value["parent_run_id"] = source_run_id
    value["recovery_generation"] = generation
    value["expected_base_sha"] = expected_base_sha
    value["publish_branch"] = f"codex/{base_task_id}-recovery-g{generation}"
    value["objective"] = (
        f"Recover the approved low-risk task after {reason_code}. "
        f"Preserve the original scope and repair only the failing deterministic gate."
    )
    changes = list(value.get("required_changes", []))
    changes.append(f"Repair failure {reason_code}: {safe_summary(reason)}")
    changes.append("Do not widen the allowed file set or change business semantics.")
    value["required_changes"] = changes
    notes = list(value.get("acceptance_notes", []))
    notes.append(f"Parent workflow run: {source_run_id}")
    notes.append("This is the only automatic Codex recovery generation.")
    value["acceptance_notes"] = notes
    value["automatic_second_session"] = 0
    value["session_limit"] = 1

    load_task_descriptor_from_mapping(value)
    return value


def load_task_descriptor_from_mapping(value: dict[str, Any]):
    from task_descriptor import TaskDescriptor

    return TaskDescriptor.from_mapping(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-task", type=Path, required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--reason-code", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--expected-base-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    original, _descriptor = load_task_descriptor(args.original_task)
    result = build_recovery_descriptor(
        original,
        source_run_id=args.source_run_id,
        reason_code=args.reason_code,
        reason=args.reason,
        expected_base_sha=args.expected_base_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"RECOVERY_TASK_ID={result['task_id']}")
    print(f"RECOVERY_PUBLISH_BRANCH={result['publish_branch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
