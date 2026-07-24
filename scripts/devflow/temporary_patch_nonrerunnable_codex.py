from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

policy_path = ROOT / "scripts/devflow/recovery_policy.py"
text = policy_path.read_text(encoding="utf-8")
marker = """    if conclusion in TERMINAL_INFRA_CONCLUSIONS or _contains_marker(
        failure_steps, INFRA_STEP_MARKERS
    ):
"""
codex_block = """    if source_workflow == "Codex Task" or _contains_marker(
        failure_steps, CODEX_STEP_MARKERS
    ):
        return _decision(
            action="INTERRUPTED",
            reason_code="CODEX_SESSION_NO_AUTOMATIC_RETRY",
            reason=(
                "A model-bearing Codex job is single-use. Checkout, setup, "
                "timeout, cancellation and artifact failures after dispatch "
                "cannot rerun the model session."
            ),
            minimum_action=(
                "Return to ChatGPT Web and create a new user-approved Grant "
                "only if a fresh task remains justified."
            ),
            notification_type="INTERRUPTED",
            **common,
        )

"""
if marker not in text:
    raise SystemExit("infrastructure marker not found")
text = text.replace(marker, codex_block + marker, 1)
old_late_block = """    if source_workflow == "Codex Task" or _contains_marker(
        failure_steps, CODEX_STEP_MARKERS
    ):
        return _decision(
            action="INTERRUPTED",
            reason_code="CODEX_SESSION_NO_AUTOMATIC_RETRY",
            reason="Codex sessions are single-use and cannot be automatically retried.",
            minimum_action="Return to ChatGPT Web and decide whether a new task-specific authorization is justified.",
            notification_type="INTERRUPTED",
            **common,
        )

"""
if old_late_block not in text:
    raise SystemExit("late Codex block not found")
text = text.replace(old_late_block, "", 1)
policy_path.write_text(text, encoding="utf-8")

test_path = ROOT / "tests/test_devflow.py"
text = test_path.read_text(encoding="utf-8")
text = text.replace(
    "from recovery_task import build_recovery_descriptor  # noqa: E402\n",
    "",
    1,
)
old_infra = """def test_infrastructure_failure_retries_silently() -> None:
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=101,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
    )
    assert decision.action == "RETRY"
    assert decision.notification_type is None
"""
new_infra = """def test_pre_model_infrastructure_failure_retries_silently() -> None:
    decision = classify(
        source_workflow="Devflow State Consistency",
        source_run_id=101,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
    )
    assert decision.action == "RETRY"
    assert decision.notification_type is None


def test_codex_checkout_failure_is_never_automatically_rerun() -> None:
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=101,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "CODEX_SESSION_NO_AUTOMATIC_RETRY"
"""
if old_infra not in text:
    raise SystemExit("infrastructure test anchor not found")
text = text.replace(old_infra, new_infra, 1)
old_recovery_test = """def test_recovery_descriptor_preserves_scope_and_increments_generation() -> None:
    original = valid_task()
    recovered = build_recovery_descriptor(
        original,
        source_run_id=200,
        reason_code="PRODUCT_FULL_GATE_FAILED",
        reason="A deterministic test failed.",
        expected_base_sha="c" * 40,
    )
    assert recovered["recovery_generation"] == 1
    assert recovered["allowed_files"] == original["allowed_files"]
    assert recovered["auto_merge"] is True
    assert recovered["notify_completion"] is True
    assert recovered["parent_run_id"] == 200
"""
new_recovery_test = """def test_recovery_generation_is_effectively_zero_and_generator_removed() -> None:
    task = TaskDescriptor.from_mapping(valid_task())
    assert task.recovery_generation == 0
    assert task.max_recovery_generations == 0
    assert not (DEVFLOW / "recovery_task.py").exists()
"""
if old_recovery_test not in text:
    raise SystemExit("recovery descriptor test anchor not found")
text = text.replace(old_recovery_test, new_recovery_test, 1)
test_path.write_text(text, encoding="utf-8")

print("NONRERUNNABLE_CODEX_PATCH=PASS")
