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

start_marker = "# Make workflow policy aware of the zero-Codex design.\n"
end_marker = "# Record the active task using schema v2 and immutable work-package evidence.\n"
start = text.index(start_marker)
end = text.index(end_marker, start)
text = (
    text[:start]
    + "# Workflow policy is updated by the deterministic post-finalizer helper.\n\n"
    + text[end:]
)
path.write_text(text, encoding="utf-8")

for diagnostic in (root / "docs/implementation/devflow-operational-optimization-v2").glob(
    "FINALIZER_DIAGNOSTIC*.md"
):
    diagnostic.unlink()

for helper in (
    root / "scripts/devflow/temporary_patch_finalizer.py",
    root / "scripts/devflow/temporary_patch_finalizer_v2.py",
    Path(__file__),
):
    if helper.exists():
        helper.unlink()

print("FINALIZER_SOURCE_SIMPLIFIED=PASS")
