from __future__ import annotations

import json
import re
from pathlib import Path

ACTION_REF = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
TARGETS = (
    "_reusable-codex-thin-worker.yml",
    "codex-task.yml",
    "devflow-state-consistency.yml",
    "devflow-relay-health.yml",
    "devflow-secret-audit.yml",
    "devflow-incident.yml",
    "devflow-post-merge.yml",
)


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    if "pull_request_target" in text:
        errors.append(f"{path}: pull_request_target is forbidden")
    if "danger-full-access" in text or "safety-strategy: unsafe" in text:
        errors.append(f"{path}: unsafe Codex execution mode is forbidden")
    for reference in ACTION_REF.findall(text):
        if reference.startswith("./"):
            continue
        if "@" not in reference:
            errors.append(f"{path}: action reference lacks @: {reference}")
            continue
        _name, revision = reference.rsplit("@", 1)
        if not FULL_SHA.fullmatch(revision):
            errors.append(f"{path}: action must be pinned to a full SHA: {reference}")
    if path.name == "_reusable-codex-thin-worker.yml":
        required_fragments = (
            "environment: agent-runtime",
            "contents: read",
            "http://127.0.0.1:8787/v1/responses",
            "effort: low",
            "safety-strategy: drop-sudo",
            "automatic second session",
        )
        lowered = text.lower()
        for fragment in required_fragments:
            if fragment.lower() not in lowered:
                errors.append(f"{path}: missing security fragment: {fragment}")
        publish_index = text.find("publish:")
        if publish_index != -1 and "environment: agent-runtime" in text[publish_index:]:
            errors.append(f"{path}: publish job must not use agent-runtime environment")
    return errors


def main() -> int:
    root = Path(".github/workflows")
    errors: list[str] = []
    found: list[str] = []
    for name in TARGETS:
        path = root / name
        if not path.is_file():
            errors.append(f"missing workflow: {path}")
            continue
        found.append(path.as_posix())
        errors.extend(validate_file(path))
    summary = {"status": "PASS" if not errors else "FAIL", "files": found, "errors": errors}
    Path("devflow-workflow-validation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
