from pathlib import Path

path = Path("tests/test_devflow.py")
text = path.read_text(encoding="utf-8")
start_marker = "def test_state_failure_is_eligible_for_one_bounded_codex_repair(tmp_path: Path) -> None:\n"
end_marker = "\n\ndef test_recovery_descriptor_preserves_scope_and_increments_generation() -> None:\n"
if start_marker in text:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    replacement = '''def test_state_consistency_failure_never_creates_automatic_codex_repair(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(valid_task()), encoding="utf-8")
    decision = classify(
        source_workflow="Devflow State Consistency",
        source_run_id=105,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Validate devflow workflows and tests"),
        task_file=task_path,
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "STATE_CONSISTENCY_WEB_REPAIR_REQUIRED"
    assert decision.notification_type == "INTERRUPTED"
'''
    text = text[:start] + replacement + end_marker + text[end + len(end_marker):]
path.write_text(text, encoding="utf-8")

# Auto Recovery no longer embeds a synthesized descriptor, so the workflow
# should not be required to contain a literal reasoning_effort field.
path = Path("scripts/devflow/validate_workflows.py")
text = path.read_text(encoding="utf-8")
text = text.replace('                \'"reasoning_effort": "xhigh"\',\n', "", 1)
path.write_text(text, encoding="utf-8")

# Recovery generations themselves normalize the policy to XHigh.
path = Path("scripts/devflow/recovery_task.py")
text = path.read_text(encoding="utf-8")
marker = '    value["automatic_second_session"] = 0\n'
if '    value["reasoning_effort"] = "xhigh"\n' not in text:
    if marker not in text:
        raise SystemExit("recovery XHigh marker not found")
    text = text.replace(marker, '    value["reasoning_effort"] = "xhigh"\n' + marker, 1)
path.write_text(text, encoding="utf-8")

# Test the generator rather than a removed inline workflow literal.
path = Path("tests/test_devflow_codex_environment.py")
text = path.read_text(encoding="utf-8")
old = '''def test_auto_recovery_generates_xhigh_tasks() -> None:
    workflow = REPO / ".github/workflows/devflow-auto-recovery.yml"
    text = workflow.read_text(encoding="utf-8")
    assert '"reasoning_effort": "xhigh"' in text
    assert '"reasoning_effort": "low"' not in text
    assert validate_file(workflow) == []
'''
new = '''def test_recovery_generator_forces_xhigh_tasks() -> None:
    script = REPO / "scripts/devflow/recovery_task.py"
    text = script.read_text(encoding="utf-8")
    assert 'value["reasoning_effort"] = "xhigh"' in text

    workflow = REPO / ".github/workflows/devflow-auto-recovery.yml"
    assert validate_file(workflow) == []
'''
if old not in text:
    raise SystemExit("legacy XHigh workflow test marker not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
