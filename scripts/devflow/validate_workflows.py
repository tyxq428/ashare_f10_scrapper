from __future__ import annotations

import json
import re
from pathlib import Path

ACTION_REF = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
TARGETS = (
    "_reusable-codex-thin-worker.yml",
    "codex-task.yml",
    "devflow-auto-recovery.yml",
    "devflow-product-gate.yml",
    "devflow-state-consistency.yml",
    "devflow-relay-health.yml",
    "devflow-secret-audit.yml",
    "devflow-incident.yml",
    "devflow-post-merge.yml",
)


def _require_fragments(path: Path, text: str, fragments: tuple[str, ...], errors: list[str]) -> None:
    lowered = text.lower()
    for fragment in fragments:
        if fragment.lower() not in lowered:
            errors.append(f"{path}: missing policy fragment: {fragment}")


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    if "pull_request_target" in text:
        errors.append(f"{path}: pull_request_target is forbidden")
    if "danger-full-access" in text or "safety-strategy: unsafe" in text:
        errors.append(f"{path}: unsafe Codex execution mode is forbidden")
    if "eval " in text or "bash -c \"${{" in text:
        errors.append(f"{path}: arbitrary evaluated workflow input is forbidden")
    for reference in ACTION_REF.findall(text):
        if reference.startswith("./"):
            continue
        if "@" not in reference:
            errors.append(f"{path}: action reference lacks @: {reference}")
            continue
        _name, revision = reference.rsplit("@", 1)
        if not FULL_SHA.fullmatch(revision):
            errors.append(f"{path}: action must be pinned to a full SHA: {reference}")

    if path.name == "_reusable-codex-thin-worker.yml":
        _require_fragments(
            path,
            text,
            (
                "environment: agent-runtime",
                "contents: read",
                "http://127.0.0.1:8787/v1/responses",
                "effort: low",
                "safety-strategy: drop-sudo",
                "recovery generation",
                "devflow_product_gate",
            ),
            errors,
        )
        publish_index = text.find("publish:")
        if publish_index != -1 and "environment: agent-runtime" in text[publish_index:]:
            errors.append(f"{path}: publish job must not use agent-runtime environment")

    if path.name == "devflow-auto-recovery.yml":
        _require_fragments(
            path,
            text,
            (
                "rerun-failed-jobs",
                "recovery_policy.py",
                "recovery_task.py",
                "devflow_notify",
                "No task-control notification was emitted",
            ),
            errors,
        )
        if "issues: write" in text:
            errors.append(f"{path}: auto recovery must not write Issues directly")

    if path.name == "devflow-product-gate.yml":
        _require_fragments(
            path,
            text,
            (
                "devflow_product_gate",
                "verify_changed_paths.py",
                "run_gate_profile.py",
                "auto_merge",
                "devflow_post_merge",
            ),
            errors,
        )
        if "environment: agent-runtime" in text:
            errors.append(f"{path}: product gate must not access relay Environment Secrets")

    if path.name == "devflow-incident.yml":
        _require_fragments(
            path,
            text,
            (
                "repository_dispatch",
                "devflow_notify",
                "does **not** trigger repair",
                "control_issue_number",
            ),
            errors,
        )
        if "workflow_run:" in text:
            errors.append(f"{path}: Incident must not notify directly from raw workflow failures")

    if path.name == "devflow-post-merge.yml":
        _require_fragments(
            path,
            text,
            (
                "devflow_post_merge",
                "run_gate_profile.py",
                "recovery_task.py",
                "finalize_task.py",
                "devflow_notify",
            ),
            errors,
        )
        if "environment: agent-runtime" in text:
            errors.append(f"{path}: post-merge must not access relay Environment Secrets")

    return errors


def main() -> int:
    root = Path(".github/workflows")
    errors: list[str] = []
    found: list[str] = []
    for name in TARGETS:
        path = root / name
        if not path.is_file():
            errors.append(f"missing workflow: {path}")
            continue
        found.append(path.as_posix())
        errors.extend(validate_file(path))
    summary = {"status": "PASS" if not errors else "FAIL", "files": found, "errors": errors}
    Path("devflow-workflow-validation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
