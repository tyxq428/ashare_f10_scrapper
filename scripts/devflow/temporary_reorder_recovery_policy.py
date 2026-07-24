from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[2]
path = root / "scripts/devflow/recovery_policy.py"
text = path.read_text(encoding="utf-8")

framework_start = text.index(
    '    if source_workflow in {\n'
    '        "Devflow State Consistency",\n'
    '        "Devflow Product Gate",\n'
    '        "Devflow Post Merge",\n'
    '    }:\n'
)
codex_start = text.index(
    '    if source_workflow == "Codex Task" or _contains_marker(',
    framework_start,
)
framework_block = text[framework_start:codex_start]
text = text[:framework_start] + text[codex_start:]

infra_start = text.index(
    '    if conclusion in TERMINAL_INFRA_CONCLUSIONS or _contains_marker('
)
relay_start = text.index(
    '    if source_workflow == "Devflow Relay Health":',
    infra_start,
)
text = text[:relay_start] + framework_block + text[relay_start:]
path.write_text(text, encoding="utf-8")

print("RECOVERY_CLASSIFICATION_ORDER=CODEX_THEN_INFRA_THEN_FRAMEWORK")
