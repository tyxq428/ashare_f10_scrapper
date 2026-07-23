from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[2]
path = root / "scripts/devflow/validate_workflows.py"
text = path.read_text(encoding="utf-8")

old = '''                "./.github/actions/codex-thin-worker",
                "http://127.0.0.1:8787/health",'''
new = '''                "codex_eligibility.py",
                "approval_file",
                "reproduction_file",
                "needs.read-task.outputs.eligible == 'true'",
                "./.github/actions/codex-thin-worker",
                "http://127.0.0.1:8787/health",'''
if old not in text:
    raise SystemExit("codex-task required-fragment anchor missing")
text = text.replace(old, new, 1)

old = '''        if re.search(r"^\\s{2}push:\\s*$", text, re.MULTILINE):
            errors.append(f"{path}: Codex Task must use explicit dispatch, not a task-branch push trigger")'''
new = '''        for forbidden in (
            "github.actor == 'github-actions[bot]'",
            "actor not in {'tyxq428', 'github-actions[bot]'}",
            "allow-bot-users:",
        ):
            if forbidden in text:
                errors.append(f"{path}: bot actors may not dispatch Codex: {forbidden}")
        if re.search(r"^\\s{2}push:\\s*$", text, re.MULTILINE):
            errors.append(f"{path}: Codex Task must use explicit dispatch, not a task-branch push trigger")'''
if old not in text:
    raise SystemExit("codex bot-policy anchor missing")
text = text.replace(old, new, 1)

old = '''                "rerun-failed-jobs",
                "recovery_policy.py",
                "recovery_task.py",
                "devflow_notify",
                "No task-control notification was emitted",'''
new = '''                "rerun-failed-jobs",
                "recovery_policy.py",
                "devflow_notify",
                "No Codex task was created or retried",'''
if old not in text:
    raise SystemExit("auto-recovery required-fragment anchor missing")
text = text.replace(old, new, 1)

old = '''        if "issues: write" in text:
            errors.append(f"{path}: auto recovery must not write Issues directly")'''
new = '''        if "issues: write" in text:
            errors.append(f"{path}: auto recovery must not write Issues directly")
        for forbidden in (
            "actions/workflows/codex-task.yml/dispatches",
            "steps.decision.outputs.action == 'RETRY_CODEX'",
            "python scripts/devflow/recovery_task.py",
        ):
            if forbidden in text:
                errors.append(f"{path}: automatic Codex path is forbidden: {forbidden}")'''
if old not in text:
    raise SystemExit("auto-recovery forbidden-policy anchor missing")
text = text.replace(old, new, 1)

old = '''                "run_gate_profile.py",
                "recovery_task.py",
                "finalize_task.py",
                "devflow_notify",'''
new = '''                "run_gate_profile.py",
                "POST_MERGE_WEB_REPAIR_REQUIRED",
                "devflow_notify",'''
if old not in text:
    raise SystemExit("post-merge required-fragment anchor missing")
text = text.replace(old, new, 1)

old = '''        if "environment: agent-runtime" in text:
            errors.append(f"{path}: post-merge must not access relay Environment Secrets")'''
new = '''        if "environment: agent-runtime" in text:
            errors.append(f"{path}: post-merge must not access relay Environment Secrets")
        for forbidden in (
            "actions/workflows/codex-task.yml/dispatches",
            "python scripts/devflow/recovery_task.py",
            "steps.decision.outputs.action == 'RETRY_CODEX'",
        ):
            if forbidden in text:
                errors.append(f"{path}: post-merge automatic Codex path is forbidden: {forbidden}")'''
if old not in text:
    raise SystemExit("post-merge forbidden-policy anchor missing")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path(__file__).unlink()
print("WORKFLOW_VALIDATOR_ZERO_CODEX_PATCHED=PASS")
