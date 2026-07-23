from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[2]

policy_path = root / "scripts/devflow/recovery_policy.py"
text = policy_path.read_text(encoding="utf-8")
old = '''    if codex_result is not None and codex_result.get("status") in {
        "BLOCKED",
        "NO_CHANGES",
        "UNVERIFIED",
        "FAILURE",
        "TIMEOUT",
    }:
        return _decision(
            action="INTERRUPTED",
            reason_code="CODEX_TERMINAL_NO_RETRY",
            reason="The single approved Codex session produced a terminal non-publishable result.",
            minimum_action="Inspect the immutable evidence in ChatGPT Web; never rerun this task fingerprint.",
            notification_type="INTERRUPTED",
            **common,
        )
'''
new = '''    if codex_result is not None and codex_result.get("status") in {
        "BLOCKED",
        "NO_CHANGES",
        "UNVERIFIED",
        "FAILURE",
        "TIMEOUT",
    }:
        blocked = codex_result.get("status") == "BLOCKED"
        return _decision(
            action="INTERRUPTED",
            reason_code=("CODEX_BLOCKED_NO_RETRY" if blocked else "CODEX_TERMINAL_NO_RETRY"),
            reason="The single approved Codex session produced a terminal non-publishable result.",
            minimum_action="Inspect the immutable evidence in ChatGPT Web; never rerun this task fingerprint.",
            notification_type="INTERRUPTED",
            **common,
        )
'''
if old not in text:
    raise SystemExit("Codex terminal policy anchor missing")
text = text.replace(old, new, 1)

framework_anchor = '''    if source_workflow in {
        "Devflow State Consistency",
        "Devflow Product Gate",
        "Devflow Post Merge",
    }:
'''
security_block = '''    if _contains_marker(failure_steps, SECURITY_STEP_MARKERS):
        return _decision(
            action="SECURITY_BLOCKED",
            reason_code="SECURITY_CONTROL_FAILED",
            reason="A security, secret or changed-path scope control failed.",
            minimum_action="Review the bounded safe summary before any further execution.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

'''
if framework_anchor not in text:
    raise SystemExit("Framework routing anchor missing")
text = text.replace(framework_anchor, security_block + framework_anchor, 1)

old = '''        return _decision(
            action="INTERRUPTED",
            reason_code="WEB_REPAIR_REQUIRED",
            reason="Framework, state, gate and post-merge failures are handled by ChatGPT Web, not Codex.",
            minimum_action="Diagnose the actual failing branch and paths in ChatGPT Web, then rerun deterministic gates.",
            notification_type="INTERRUPTED",
            **common,
        )
'''
new = '''        reason_code = {
            "Devflow State Consistency": "STATE_CONSISTENCY_WEB_REPAIR_REQUIRED",
            "Devflow Product Gate": "PRODUCT_GATE_WEB_REPAIR_REQUIRED",
            "Devflow Post Merge": "POST_MERGE_WEB_REPAIR_REQUIRED",
        }[source_workflow]
        return _decision(
            action="INTERRUPTED",
            reason_code=reason_code,
            reason="Framework, state, gate and post-merge failures are handled by ChatGPT Web, not Codex.",
            minimum_action="Diagnose the actual failing branch and paths in ChatGPT Web, then rerun deterministic gates.",
            notification_type="INTERRUPTED",
            **common,
        )
'''
if old not in text:
    raise SystemExit("Framework reason-code anchor missing")
text = text.replace(old, new, 1)
policy_path.write_text(text, encoding="utf-8")

# Replace the obsolete automatic Codex retry regression with the new single-use policy.
test_path = root / "tests/test_devflow.py"
text = test_path.read_text(encoding="utf-8")
start_marker = "def test_codex_failure_gets_one_silent_failed_job_rerun() -> None:\n"
end_marker = "\n\ndef test_missing_agent_runtime_secrets_are_a_real_human_gate"
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = '''def test_codex_failure_never_reruns_automatically() -> None:
    first = classify(
        source_workflow="Codex Task",
        source_run_id=102,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run one Codex Thin Worker session"),
    )
    second = classify(
        source_workflow="Codex Task",
        source_run_id=102,
        conclusion="failure",
        run_attempt=2,
        jobs_payload=failed_jobs("Run one Codex Thin Worker session"),
    )
    assert first.action == "INTERRUPTED"
    assert first.reason_code == "CODEX_SESSION_NO_AUTOMATIC_RETRY"
    assert first.notification_type == "INTERRUPTED"
    assert second.action == "INTERRUPTED"
    assert second.reason_code == "CODEX_SESSION_NO_AUTOMATIC_RETRY"
'''
text = text[:start] + replacement + text[end:]
test_path.write_text(text, encoding="utf-8")

# Schema-v1 Low remains readable metadata; Schema-v2 Low remains invalid.
env_test = root / "tests/test_devflow_codex_environment.py"
text = env_test.read_text(encoding="utf-8")
text = text.replace(
    '    legacy = dict(template)\n    legacy["reasoning_effort"] = "low"',
    '    legacy = dict(template)\n    legacy["schema_version"] = 1\n    legacy["reasoning_effort"] = "low"',
    1,
)
env_test.write_text(text, encoding="utf-8")

# Remove all staging diagnostics and helpers from the eventual reviewed branch.
for diagnostic in (root / "docs/implementation/devflow-operational-optimization-v2").glob(
    "FINALIZER_DIAGNOSTIC*.md"
):
    diagnostic.unlink()
for helper in root.glob("scripts/devflow/temporary_*finalizer*.py"):
    if helper != Path(__file__):
        helper.unlink()
for helper in (
    root / "scripts/devflow/temporary_patch_workflow_validator.py",
    Path(__file__),
):
    if helper.exists():
        helper.unlink()

print("ZERO_MODEL_POLICY_TESTS_FIXED=PASS")
