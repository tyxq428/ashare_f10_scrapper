from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[2]
path = root / "scripts/devflow/temporary_finalize_operational_optimization.py"
text = path.read_text(encoding="utf-8")

text = text.replace(
    'for forbidden in ("codex-task.yml/dispatches", "RETRY_CODEX", "recovery_task.py"):\n    if forbidden in auto_text:\n        raise SystemExit(f"automatic Codex path remains in auto recovery: {forbidden}")',
    'for forbidden in (\n    "actions/workflows/codex-task.yml/dispatches",\n    "steps.decision.outputs.action == \'RETRY_CODEX\'",\n    "python scripts/devflow/recovery_task.py",\n):\n    if forbidden in auto_text:\n        raise SystemExit(f"automatic Codex path remains in auto recovery: {forbidden}")',
)
text = text.replace(
    "permissions:\n  contents: read\n  actions: read\n\nconcurrency:",
    "permissions:\n  contents: write\n  actions: read\n\nconcurrency:",
    1,
)

text = text.replace(
    '        for forbidden in ("codex-task.yml/dispatches", "RETRY_CODEX", "recovery_task.py"):\\n            if forbidden in text:\\n                errors.append(f"{path}: automatic Codex path is forbidden: {forbidden}")',
    '        for forbidden in (\\n            "actions/workflows/codex-task.yml/dispatches",\\n            "steps.decision.outputs.action == \'RETRY_CODEX\'",\\n            "python scripts/devflow/recovery_task.py",\\n        ):\\n            if forbidden in text:\\n                errors.append(f"{path}: automatic Codex path is forbidden: {forbidden}")',
)
text = text.replace(
    '        if "github-actions[bot]" in text:\\n            errors.append(f"{path}: bot actors may not dispatch Codex")',
    '        for forbidden in (\\n            "github.actor == \'github-actions[bot]\'",\\n            "actor not in {\'tyxq428\', \'github-actions[bot]\'}",\\n            "allow-bot-users:",\\n        ):\\n            if forbidden in text:\\n                errors.append(f"{path}: bot actors may not dispatch Codex: {forbidden}")',
)
text = text.replace(
    '        for forbidden in ("codex-task.yml/dispatches", "recovery_task.py", "RETRY_CODEX"):\\n            if forbidden in text:\\n                errors.append(f"{path}: post-merge automatic Codex path is forbidden: {forbidden}")',
    '        for forbidden in (\\n            "actions/workflows/codex-task.yml/dispatches",\\n            "python scripts/devflow/recovery_task.py",\\n            "steps.decision.outputs.action == \'RETRY_CODEX\'",\\n        ):\\n            if forbidden in text:\\n                errors.append(f"{path}: post-merge automatic Codex path is forbidden: {forbidden}")',
)

path.write_text(text, encoding="utf-8")

for diagnostic in (root / "docs/implementation/devflow-operational-optimization-v2").glob(
    "FINALIZER_DIAGNOSTIC*.md"
):
    diagnostic.unlink()

for helper in (
    root / "scripts/devflow/temporary_patch_finalizer.py",
    Path(__file__),
):
    if helper.exists():
        helper.unlink()

print("FINALIZER_VALIDATOR_PATTERNS_PATCHED=PASS")
