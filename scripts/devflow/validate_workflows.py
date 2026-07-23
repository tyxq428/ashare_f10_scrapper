from __future__ import annotations

import json
import re
from pathlib import Path

ACTION_REF = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
WORKFLOW_TARGETS = (
    "codex-task.yml",
    "devflow-auto-recovery.yml",
    "devflow-product-gate.yml",
    "devflow-state-consistency.yml",
    "devflow-relay-health.yml",
    "devflow-secret-audit.yml",
    "devflow-incident.yml",
    "devflow-post-merge.yml",
)
ACTION_TARGETS = (Path(".github/actions/codex-thin-worker/action.yml"),)


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
    if "eval " in text or 'bash -c "${{' in text:
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

    if path.name == "codex-task.yml":
        _require_fragments(
            path,
            text,
            (
                "workflow_dispatch:",
                "name: agent-runtime",
                "deployment: false",
                "contents: read",
                "./.github/actions/codex-thin-worker",
                "http://127.0.0.1:8787/health",
                "CODEX_FINAL_MESSAGE",
                "/tmp/codex-result.json",
                "steps.result.outcome",
                "secret-free-publish",
                "devflow_product_gate",
            ),
            errors,
        )
        if re.search(r"^\s{2}push:\s*$", text, re.MULTILINE):
            errors.append(f"{path}: Codex Task must use explicit dispatch, not a task-branch push trigger")
        publish_index = text.find("\n  publish:")
        if publish_index == -1:
            errors.append(f"{path}: missing secret-free publish job")
        elif "agent-runtime" in text[publish_index:]:
            errors.append(f"{path}: publish and continuation jobs must not use agent-runtime")

    if path.as_posix().endswith(".github/actions/codex-thin-worker/action.yml"):
        _require_fragments(
            path,
            text,
            (
                "using: composite",
                "openai/codex-action@52fe01ec70a42f454c9d2ebd47598f9fd6893d56",
                "http://127.0.0.1:8787/v1/responses",
                "effort: low",
                "safety-strategy: drop-sudo",
                "allow-bots: \"true\"",
                "allow-bot-users: github-actions[bot]",
                "value: ${{ steps.run-codex.outputs.final-message }}",
                "${{ inputs.api-key }}",
                "${{ inputs.model }}",
            ),
            errors,
        )
        if "secrets." in text:
            errors.append(f"{path}: composite action must receive explicit inputs, not read secrets directly")
        if "output-file:" in text:
            errors.append(f"{path}: official action output must be handed off through final-message, not an absolute output-file")
        if "allow-users:" in text:
            errors.append(f"{path}: arbitrary user allowlists are forbidden")

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
    workflow_root = Path(".github/workflows")
    errors: list[str] = []
    found: list[str] = []
    for name in WORKFLOW_TARGETS:
        path = workflow_root / name
        if not path.is_file():
            errors.append(f"missing workflow: {path}")
            continue
        found.append(path.as_posix())
        errors.extend(validate_file(path))
    for path in ACTION_TARGETS:
        if not path.is_file():
            errors.append(f"missing reusable action: {path}")
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
