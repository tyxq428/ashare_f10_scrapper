from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path(".devflow/codex-entrypoints.yaml")
POLICY_PATH = Path(".devflow/codex-policy.yaml")
CODEX_TASK = Path(".github/workflows/codex-task.yml")
AUTO_RECOVERY = Path(".github/workflows/devflow-auto-recovery.yml")
PRODUCT_GATE = Path(".github/workflows/devflow-product-gate.yml")
POST_MERGE = Path(".github/workflows/devflow-post-merge.yml")
RELAY_HEALTH = Path(".github/workflows/devflow-relay-health.yml")
SECRET_AUDIT = Path(".github/workflows/devflow-secret-audit.yml")
LEGACY_RERUN_AUDIT = Path(
    ".github/workflows/devflow-legacy-codex-rerun-audit.yml"
)
ACTION_PATH = Path(".github/actions/codex-thin-worker/action.yml")
LEGACY_AUDIT_SCRIPT = Path("scripts/devflow/legacy_codex_branch_audit.py")


class EntrypointValidationError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EntrypointValidationError(f"cannot load {path}") from exc
    if not isinstance(value, dict):
        raise EntrypointValidationError(f"{path} root must be an object")
    return value


def _text(path: Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _require(
    text: str,
    fragments: tuple[str, ...],
    path: Path,
    errors: list[str],
) -> None:
    for fragment in fragments:
        if fragment not in text:
            errors.append(f"{path}: missing required fragment: {fragment}")


def _forbid(
    text: str,
    fragments: tuple[str, ...],
    path: Path,
    errors: list[str],
) -> None:
    for fragment in fragments:
        if fragment in text:
            errors.append(f"{path}: forbidden model path: {fragment}")


def _validate_repo_wide_workflow_surface(errors: list[str]) -> None:
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        if "openai/codex-action@" in text:
            errors.append(f"{relative}: permanent workflow contains a model action")
        if "actions/workflows/codex-task.yml/dispatches" in text:
            errors.append(f"{relative}: workflow dispatches Codex Task automatically")
        if "python scripts/devflow/recovery_task.py" in text:
            errors.append(f"{relative}: workflow creates a Codex recovery generation")
        if "steps.decision.outputs.action == 'RETRY_CODEX'" in text:
            errors.append(f"{relative}: workflow can retry a Codex model job")
        if "private_responses_forwarder.py" in text:
            errors.append(f"{relative}: permanent workflow starts a model forwarder")


def validate() -> dict[str, Any]:
    errors: list[str] = []
    manifest = _load_object(MANIFEST_PATH)
    policy = _load_object(POLICY_PATH)

    if manifest.get("schema_version") != 1:
        errors.append("codex entrypoint manifest schema_version must be 1")
    if manifest.get("policy_mode") != "disabled":
        errors.append("entrypoint manifest policy_mode must remain disabled")
    if policy.get("mode") != "disabled":
        errors.append("repository Codex policy must remain disabled")
    for field in (
        "auto_recovery_dispatch",
        "allow_github_actions_bot",
        "retry_failed_codex_job",
    ):
        if policy.get(field) is not False:
            errors.append(f"Codex policy {field} must be false")

    entrypoints = manifest.get("allowed_entrypoints")
    if not isinstance(entrypoints, list) or len(entrypoints) != 1:
        errors.append("exactly one eligibility-only Codex entrypoint is allowed")
    else:
        entrypoint = entrypoints[0]
        expected = {
            "id": "manual_one_time_executor",
            "workflow": CODEX_TASK.as_posix(),
            "current_mode": "eligibility_only",
            "model_invocation": False,
            "allowed_actor": "tyxq428",
        }
        if entrypoint != expected:
            errors.append(
                "manual entrypoint does not match the reviewed manifest"
            )

    activation = manifest.get("activation")
    if not isinstance(activation, dict):
        errors.append("activation policy must be an object")
    else:
        expected_activation = {
            "mode": "one_time_reviewed_pr",
            "persistent_model_job": False,
            "grant_required": True,
            "grant_ttl_minutes_max": 60,
            "calls_per_task": 1,
            "calls_per_fingerprint": 1,
            "automatic_recovery_generations": 0,
            "automatic_second_session": 0,
        }
        if activation != expected_activation:
            errors.append(
                "activation policy must remain one-time and zero-recovery"
            )

    codex_task = _text(CODEX_TASK)
    _require(
        codex_task,
        (
            "workflow_dispatch:",
            "github.actor == 'tyxq428'",
            "path: control",
            "path: workspace",
            "CODEX_MODEL_INVOCATION=DISABLED",
        ),
        CODEX_TASK,
        errors,
    )
    _forbid(
        codex_task,
        (
            "github-actions[bot]",
            "environment: agent-runtime",
            "secrets.",
            "openai/codex-action@",
            "./.github/actions/codex-thin-worker",
            "secret-bearing-read-only-codex",
        ),
        CODEX_TASK,
        errors,
    )

    automatic_forbidden = (
        "actions/workflows/codex-task.yml/dispatches",
        "steps.decision.outputs.action == 'RETRY_CODEX'",
        "python scripts/devflow/recovery_task.py",
        "openai/codex-action@",
    )
    for path in (AUTO_RECOVERY, PRODUCT_GATE, POST_MERGE):
        _forbid(_text(path), automatic_forbidden, path, errors)

    auto_recovery = _text(AUTO_RECOVERY)
    for forbidden_workflow in (
        "      - Codex Task\n",
        "      - Devflow Relay Health\n",
    ):
        if forbidden_workflow in auto_recovery:
            errors.append(
                f"{AUTO_RECOVERY}: paid or model workflow must not be auto-retried"
            )
    _require(
        auto_recovery,
        (
            "No Codex task, Relay paid probe or model session was retried",
            "AUTOMATIC_PAID_RELAY_PROBE_RETRIES=0",
        ),
        AUTO_RECOVERY,
        errors,
    )

    product_gate = _text(PRODUCT_GATE)
    _require(
        product_gate,
        (
            "PRODUCT_GATE_WEB_REPAIR_REQUIRED",
            "Run full product gate",
            "Fail closed on changed-path scope violation",
        ),
        PRODUCT_GATE,
        errors,
    )
    _forbid(
        product_gate,
        ("RECOVERY_GENERATION", "RECOVERY_TASK_ID", "recovery-g"),
        PRODUCT_GATE,
        errors,
    )

    post_merge = _text(POST_MERGE)
    _require(
        post_merge,
        ("POST_MERGE_WEB_REPAIR_REQUIRED",),
        POST_MERGE,
        errors,
    )

    relay_health = _text(RELAY_HEALTH)
    _require(
        relay_health,
        (
            "configuration_only",
            "paid_responses_probe",
            "I_ACCEPT_ONE_PAID_RESPONSES_PROBE",
            "RESPONSES_REQUESTS_SENT=0",
            "This workflow is never automatically retried",
        ),
        RELAY_HEALTH,
        errors,
    )
    if relay_health.count("python scripts/devflow/relay_health.py") != 1:
        errors.append(
            f"{RELAY_HEALTH}: exactly one explicitly paid probe step is allowed"
        )

    secret_audit = _text(SECRET_AUDIT)
    _require(
        secret_audit,
        (
            "validate-source:",
            "AUDIT_CONFIRMED_MODEL_RUN",
            "Codex One-Time Activation",
            "CODEX_MODEL_SESSION_STARTED activation_id=",
            "needs: validate-source",
            "MODEL_RUN_EVIDENCE=VALIDATED_BEFORE_SECRET_ACCESS",
        ),
        SECRET_AUDIT,
        errors,
    )
    validate_index = secret_audit.find("  validate-source:")
    audit_index = secret_audit.find("  audit-public-logs:")
    environment_index = secret_audit.find("    environment:")
    if not (
        0 <= validate_index < audit_index <= environment_index
    ):
        errors.append(
            f"{SECRET_AUDIT}: source evidence must pass before Environment binding"
        )

    legacy_audit = _text(LEGACY_RERUN_AUDIT)
    _require(
        legacy_audit,
        (
            "Devflow Legacy Codex Rerun Audit",
            "task/codex-",
            "legacy_codex_branch_audit.py",
            "persist-credentials: false",
        ),
        LEGACY_RERUN_AUDIT,
        errors,
    )
    _forbid(
        legacy_audit,
        (
            "agent-runtime",
            "secrets.AGENT_",
            "openai/codex-action@",
        ),
        LEGACY_RERUN_AUDIT,
        errors,
    )

    action = _text(ACTION_PATH)
    _require(
        action,
        ("CODEX_POLICY_DISABLED", "CODEX_MODEL_INVOCATION=DISABLED"),
        ACTION_PATH,
        errors,
    )
    _forbid(
        action,
        ("openai/codex-action@", "secrets."),
        ACTION_PATH,
        errors,
    )

    allowed_agent_runtime = set(
        manifest.get("allowed_agent_runtime_workflows", [])
    )
    discovered_agent_runtime: set[str] = set()
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if "agent-runtime" in text:
            discovered_agent_runtime.add(path.relative_to(ROOT).as_posix())
    if discovered_agent_runtime != allowed_agent_runtime:
        errors.append(
            "agent-runtime workflow allowlist mismatch: "
            f"expected={sorted(allowed_agent_runtime)} "
            f"actual={sorted(discovered_agent_runtime)}"
        )
    for required in (RELAY_HEALTH.as_posix(), SECRET_AUDIT.as_posix()):
        if required not in discovered_agent_runtime:
            errors.append(f"required explicit Environment workflow missing: {required}")

    if (ROOT / "scripts/devflow/recovery_task.py").exists():
        errors.append("production recovery_task.py must be removed")
    if not (ROOT / LEGACY_AUDIT_SCRIPT).is_file():
        errors.append("legacy Codex branch audit script is missing")

    task_descriptor = _text(Path("scripts/devflow/task_descriptor.py"))
    _require(
        task_descriptor,
        (
            "max_recovery_generations must equal 0",
            "max_recovery_generations = 0",
        ),
        Path("scripts/devflow/task_descriptor.py"),
        errors,
    )

    _validate_repo_wide_workflow_surface(errors)

    summary = {
        "status": "PASS" if not errors else "FAIL",
        "policy_mode": policy.get("mode"),
        "allowed_entrypoint_count": (
            len(entrypoints) if isinstance(entrypoints, list) else 0
        ),
        "agent_runtime_workflows": sorted(discovered_agent_runtime),
        "legacy_rerun_audit_present": (ROOT / LEGACY_RERUN_AUDIT).is_file(),
        "automatic_model_paths": 0 if not errors else None,
        "automatic_paid_probe_retries": 0 if not errors else None,
        "errors": errors,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = validate()
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
