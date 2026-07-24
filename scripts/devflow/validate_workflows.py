from __future__ import annotations

import json
import re
from pathlib import Path

from validate_codex_entrypoints import validate as validate_codex_entrypoints
from validate_notification_channels import validate as validate_notification_channels

ACTION_REF = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
WORKFLOW_TARGETS = (
    "codex-task.yml",
    "devflow-auto-recovery.yml",
    "devflow-product-gate.yml",
    "devflow-state-consistency.yml",
    "devflow-relay-health.yml",
    "devflow-secret-audit.yml",
    "devflow-legacy-codex-rerun-audit.yml",
    "devflow-incident.yml",
    "devflow-post-merge.yml",
    "devflow-terminal-state-notify.yml",
)
ACTION_TARGETS = (Path(".github/actions/codex-thin-worker/action.yml"),)


def _require_fragments(
    path: Path,
    text: str,
    fragments: tuple[str, ...],
    errors: list[str],
) -> None:
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
            errors.append(
                f"{path}: action must be pinned to a full SHA: {reference}"
            )


def _forbid(
    path: Path,
    text: str,
    fragments: tuple[str, ...],
    errors: list[str],
    *,
    message: str,
) -> None:
    for fragment in fragments:
        if fragment in text:
            errors.append(f"{path}: {message}: {fragment}")


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
                "github.ref_name == 'main'",
                "path: control",
                "path: workspace",
                "codex_candidate_review.py",
                "CODEX_MODEL_INVOCATION=DISABLED",
                "Task branches are data-only",
            ),
            errors,
        )
        _forbid(
            path,
            text,
            (
                "github-actions[bot]",
                "environment: agent-runtime",
                "secrets.",
                "openai/codex-action@",
                "./.github/actions/codex-thin-worker",
                "secret-bearing-read-only-codex",
            ),
            errors,
            message="hard-disabled entry contains a model path",
        )
        if re.search(r"^\s{2}push:\s*$", text, re.MULTILINE):
            errors.append(f"{path}: Codex Task must use explicit dispatch, not push")

    if path.as_posix().endswith(
        ".github/actions/codex-thin-worker/action.yml"
    ):
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
                errors.append(
                    f"{path}: disabled policy must stop before the official action"
                )
        else:
            errors.append(f"{path}: production policy must remain disabled")
        _forbid(
            path,
            text,
            ("secrets.", "output-file:", "effort: low"),
            errors,
            message="disabled composite contains a forbidden field",
        )

    if path.name == "devflow-auto-recovery.yml":
        _require_fragments(
            path,
            text,
            (
                "workflow_run:",
                "rerun-failed-jobs",
                "recovery_policy.py",
                "notification_event.py resolve-task",
                "value['task_id'] = resolved['task_id']",
                "devflow_notify",
                "assert_auto_recovery_boundaries.py",
                "No Codex task, Relay paid probe or model session was retried",
                "AUTOMATIC_PAID_RELAY_PROBE_RETRIES=0",
                "AUTOMATIC_BARK_RETRIES=0",
            ),
            errors,
        )
        _forbid(
            path,
            text,
            (
                "      - Codex Task\n",
                "      - Devflow Relay Health\n",
                "      - Devflow Incident\n",
                "      - Devflow Terminal State Notification\n",
                "actions/workflows/codex-task.yml/dispatches",
                "steps.decision.outputs.action == 'RETRY_CODEX'",
                "python scripts/devflow/recovery_task.py",
                "environment: agent-runtime",
                "secrets.AGENT_",
                "${{ secrets.BARK_PUSH_URL }}",
                "name: notification-runtime",
            ),
            errors,
            message="automatic model, paid-probe or Bark retry path is forbidden",
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
                "git merge-base --is-ancestor",
                "git merge-base origin/main HEAD",
                "product-scope-result.json",
                "Fail closed on changed-path scope violation",
                "PRODUCT_GATE_WEB_REPAIR_REQUIRED",
                "Centralized Auto Recovery will classify the terminal task event",
                "No direct duplicate devflow notification was dispatched",
                "'task_id': '${{ steps.task.outputs.task_id }}'",
                'git config user.name "github-actions[bot]"',
                "Fail closed when automatic merge boundary is blocked",
                "auto_merge",
                "devflow_post_merge",
            ),
            errors,
        )
        _forbid(
            path,
            text,
            (
                "environment: agent-runtime",
                "secrets.AGENT_",
                "actions/workflows/codex-task.yml/dispatches",
                "python scripts/devflow/recovery_task.py",
                "RECOVERY_GENERATION",
                "RECOVERY_TASK_ID",
            ),
            errors,
            message="Product Gate automatic model recovery is forbidden",
        )
        if "--base origin/main" in text.split(
            "Reconcile latest main", 1
        )[0]:
            errors.append(
                f"{path}: initial scope must use merge base, not moving main"
            )
        failure_prefix = text.split(
            "Notify when a task is not approved for automatic merge",
            1,
        )[0]
        if "'event_type': 'devflow_notify'" in failure_prefix:
            errors.append(
                f"{path}: failed product gate must be classified by Auto Recovery"
            )

    if path.name == "devflow-state-consistency.yml":
        _require_fragments(
            path,
            text,
            (
                "validate_state.py",
                "validate_workflows.py",
                "validate_codex_entrypoints.py",
                "pytest -q",
                "tests/test_devflow",
            ),
            errors,
        )
        if "environment: agent-runtime" in text or "secrets.AGENT_" in text:
            errors.append(
                f"{path}: State Consistency must be zero-model and secret-free"
            )

    if path.name == "devflow-relay-health.yml":
        _require_fragments(
            path,
            text,
            (
                "agent-runtime",
                "configuration_only",
                "paid_responses_probe",
                "I_ACCEPT_ONE_PAID_RESPONSES_PROBE",
                "RESPONSES_REQUESTS_SENT=0",
                "relay_health.py",
                "This workflow is never automatically retried",
            ),
            errors,
        )
        if text.count("python scripts/devflow/relay_health.py") != 1:
            errors.append(
                f"{path}: exactly one explicitly paid Responses probe is allowed"
            )
        if "openai/codex-action@" in text:
            errors.append(f"{path}: Relay Health may not call Codex")

    if path.name == "devflow-secret-audit.yml":
        _require_fragments(
            path,
            text,
            (
                "validate-source:",
                "AUDIT_CONFIRMED_MODEL_RUN",
                "Codex One-Time Activation",
                "CODEX_MODEL_SESSION_STARTED activation_id=",
                "needs: validate-source",
                "MODEL_RUN_EVIDENCE=VALIDATED_BEFORE_SECRET_ACCESS",
                "secret_audit.py",
            ),
            errors,
        )
        if "workflow_run:" in text:
            errors.append(f"{path}: Secret Audit must not trigger automatically")
        validate_index = text.find("  validate-source:")
        audit_index = text.find("  audit-public-logs:")
        environment_index = text.find("    environment:")
        if not (0 <= validate_index < audit_index <= environment_index):
            errors.append(
                f"{path}: source evidence must pass before Environment binding"
            )

    if path.name == "devflow-legacy-codex-rerun-audit.yml":
        _require_fragments(
            path,
            text,
            (
                "workflow_dispatch:",
                "schedule:",
                "create:",
                "task/codex-",
                "legacy_codex_branch_audit.py",
                "persist-credentials: false",
            ),
            errors,
        )
        _forbid(
            path,
            text,
            ("agent-runtime", "secrets.AGENT_", "openai/codex-action@"),
            errors,
            message="legacy branch audit must remain zero-model and secret-free",
        )

    if path.name == "devflow-incident.yml":
        _require_fragments(
            path,
            text,
            (
                "repository_dispatch",
                "devflow_notify",
                "notification_event.py prepare",
                "control_issue_number",
                "name: notification-runtime",
                "${{ secrets.BARK_PUSH_URL }}",
                "github.run_attempt == 1",
                "continue-on-error: true",
                "--retry 0",
                "--output /dev/null",
                "BARK_DELIVERY=FAILED_FAIL_OPEN",
                "BARK_AUTOMATIC_RETRIES=0",
                "does **not** trigger repair",
            ),
            errors,
        )
        _forbid(
            path,
            text,
            (
                "workflow_run:",
                "agent-runtime",
                "secrets.AGENT_",
                "openai/codex-action@",
                "private_responses_forwarder.py",
                "relay_health.py",
            ),
            errors,
            message="Incident contains a forbidden raw, model or Relay path",
        )
        if text.count("--request POST") != 1:
            errors.append(f"{path}: exactly one Bark POST location is allowed")

    if path.name == "devflow-post-merge.yml":
        _require_fragments(
            path,
            text,
            (
                "devflow_post_merge",
                "run_gate_profile.py",
                "POST_MERGE_WEB_REPAIR_REQUIRED",
                "Centralized Auto Recovery will classify the terminal task event",
                "No direct duplicate devflow notification was dispatched",
            ),
            errors,
        )
        _forbid(
            path,
            text,
            (
                "environment: agent-runtime",
                "secrets.AGENT_",
                "actions/workflows/codex-task.yml/dispatches",
                "python scripts/devflow/recovery_task.py",
                "RETRY_CODEX",
                "'event_type': 'devflow_notify'",
            ),
            errors,
            message="Post-Merge automatic model or duplicate notification path is forbidden",
        )

    if path.name == "devflow-terminal-state-notify.yml":
        _require_fragments(
            path,
            text,
            (
                "push:",
                "      - main",
                "docs/implementation/*/task_state.yaml",
                "ref: ${{ github.sha }}",
                "fetch-depth: 0",
                "persist-credentials: false",
                "terminal_notification_scan.py",
                "devflow_notify",
                "RAW_WORKFLOW_RUN_NOTIFICATIONS=0",
                "BARK_REQUESTS_IN_THIS_WORKFLOW=0",
            ),
            errors,
        )
        _forbid(
            path,
            text,
            (
                "workflow_run:",
                "notification-runtime",
                "BARK_PUSH_URL",
                "agent-runtime",
                "secrets.AGENT_",
                "openai/codex-action@",
                "--request POST",
            ),
            errors,
            message="terminal state producer must remain secret-free and bus-only",
        )

    return errors


def main() -> int:
    workflow_root = Path(".github/workflows")
    errors: list[str] = []
    found: list[str] = []
    for temporary in sorted(workflow_root.glob("temporary-*.yml")):
        errors.append(f"obsolete temporary workflow must be removed: {temporary}")
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

    entrypoint_summary = validate_codex_entrypoints()
    errors.extend(
        f"codex-entrypoint: {item}"
        for item in entrypoint_summary.get("errors", [])
    )
    notification_summary = validate_notification_channels()
    errors.extend(
        f"notification-channel: {item}"
        for item in notification_summary.get("errors", [])
    )

    summary = {
        "status": "PASS" if not errors else "FAIL",
        "files": found,
        "automatic_model_paths": entrypoint_summary.get(
            "automatic_model_paths"
        ),
        "automatic_paid_probe_retries": entrypoint_summary.get(
            "automatic_paid_probe_retries"
        ),
        "automatic_bark_retries": notification_summary.get(
            "automatic_bark_retries"
        ),
        "bark_post_locations": notification_summary.get(
            "bark_post_locations"
        ),
        "errors": errors,
    }
    Path("devflow-workflow-validation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
