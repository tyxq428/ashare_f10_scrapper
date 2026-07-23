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


def _codex_policy_mode() -> str:
    path = Path(".devflow/codex-policy.yaml")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot load .devflow/codex-policy.yaml") from exc
    mode = value.get("mode")
    if mode not in {"disabled", "enabled"}:
        raise ValueError("codex policy mode must be disabled or enabled")
    return mode


def _check_action_pins(path: Path, text: str, errors: list[str]) -> None:
    for reference in ACTION_REF.findall(text):
        if reference.startswith("./"):
            continue
        if "@" not in reference:
            errors.append(f"{path}: action reference lacks @: {reference}")
            continue
        _name, revision = reference.rsplit("@", 1)
        if not FULL_SHA.fullmatch(revision):
            errors.append(f"{path}: action must be pinned to a full SHA: {reference}")


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")

    if "pull_request_target" in text:
        errors.append(f"{path}: pull_request_target is forbidden")
    if "danger-full-access" in text or "safety-strategy: unsafe" in text:
        errors.append(f"{path}: unsafe execution mode is forbidden")
    if "eval " in text or 'bash -c "${{' in text:
        errors.append(f"{path}: arbitrary evaluated workflow input is forbidden")
    _check_action_pins(path, text, errors)

    if path.name == "codex-task.yml":
        _require_fragments(
            path,
            text,
            (
                "workflow_dispatch:",
                "github.actor == 'tyxq428'",
                "codex_eligibility",
                "approval_file",
                "reproduction_file",
                "CODEX_MODEL_INVOCATION=DISABLED",
                "No Environment Secret, localhost forwarder or model session was started",
            ),
            errors,
        )
        for forbidden in (
            "github-actions[bot]",
            "environment: agent-runtime",
            "secrets.",
            "openai/codex-action@",
            "./.github/actions/codex-thin-worker",
            "secret-bearing-read-only-codex",
        ):
            if forbidden in text:
                errors.append(f"{path}: hard-disabled manual entry contains forbidden model path: {forbidden}")
        if re.search(r"^\s{2}push:\s*$", text, re.MULTILINE):
            errors.append(f"{path}: Codex Task must use explicit dispatch, not push")

    if path.as_posix().endswith(".github/actions/codex-thin-worker/action.yml"):
        try:
            mode = _codex_policy_mode()
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            mode = "invalid"
        if mode == "disabled":
            _require_fragments(
                path,
                text,
                (
                    "using: composite",
                    "CODEX_POLICY_DISABLED",
                    "CODEX_MODEL_INVOCATION=DISABLED",
                    "value: ${{ steps.policy.outputs.final-message }}",
                ),
                errors,
            )
            if "openai/codex-action@" in text:
                errors.append(f"{path}: disabled policy must stop before the official Codex action")
        else:
            errors.append(f"{path}: repository production policy must remain disabled")
        if "secrets." in text:
            errors.append(f"{path}: composite action must not read secrets directly")
        if "output-file:" in text:
            errors.append(f"{path}: output-file is forbidden; use structured final-message")
        if "effort: low" in text:
            errors.append(f"{path}: Low reasoning is forbidden")

    if path.name == "devflow-auto-recovery.yml":
        _require_fragments(
            path,
            text,
            (
                "workflow_run:",
                "rerun-failed-jobs",
                "recovery_policy.py",
                "devflow_notify",
                "No Codex task was created or retried",
            ),
            errors,
        )
        for forbidden in (
            "actions/workflows/codex-task.yml/dispatches",
            "steps.decision.outputs.action == 'RETRY_CODEX'",
            "python scripts/devflow/recovery_task.py",
            "environment: agent-runtime",
            "secrets.AGENT_",
        ):
            if forbidden in text:
                errors.append(f"{path}: automatic Codex path is forbidden: {forbidden}")
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
                "git merge-base --is-ancestor",
                "git merge-base origin/main HEAD",
                "product-scope-result.json",
                "Fail closed on changed-path scope violation",
                'git config user.name "github-actions[bot]"',
                'git config user.email "41898282+github-actions[bot]@users.noreply.github.com"',
                "Fail closed when automatic merge boundary is blocked",
                "auto_merge",
                "devflow_post_merge",
            ),
            errors,
        )
        if "environment: agent-runtime" in text or "secrets.AGENT_" in text:
            errors.append(f"{path}: product gate must not access relay secrets")
        if "--base origin/main" in text.split("Reconcile latest main", 1)[0]:
            errors.append(f"{path}: initial scope must use merge base, not moving main")

    if path.name == "devflow-state-consistency.yml":
        _require_fragments(
            path,
            text,
            ("validate_state.py", "validate_workflows.py", "pytest -q", "tests/test_devflow"),
            errors,
        )
        if "environment: agent-runtime" in text or "secrets.AGENT_" in text:
            errors.append(f"{path}: State Consistency must be zero-model and secret-free")

    if path.name == "devflow-relay-health.yml":
        _require_fragments(path, text, ("agent-runtime", "relay_health.py"), errors)

    if path.name == "devflow-secret-audit.yml":
        _require_fragments(path, text, ("secret_audit.py",), errors)

    if path.name == "devflow-incident.yml":
        _require_fragments(
            path,
            text,
            ("repository_dispatch", "devflow_notify", "does **not** trigger repair", "control_issue_number"),
            errors,
        )
        if "workflow_run:" in text:
            errors.append(f"{path}: Incident must not notify directly from raw failures")

    if path.name == "devflow-post-merge.yml":
        _require_fragments(
            path,
            text,
            ("devflow_post_merge", "run_gate_profile.py", "POST_MERGE_WEB_REPAIR_REQUIRED", "devflow_notify"),
            errors,
        )
        for forbidden in (
            "environment: agent-runtime",
            "secrets.AGENT_",
            "actions/workflows/codex-task.yml/dispatches",
            "python scripts/devflow/recovery_task.py",
            "RETRY_CODEX",
        ):
            if forbidden in text:
                errors.append(f"{path}: post-merge automatic model path is forbidden: {forbidden}")

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
