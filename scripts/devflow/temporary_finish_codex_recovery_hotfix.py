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
