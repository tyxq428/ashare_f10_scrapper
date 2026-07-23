from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def validate_docs(repo: Path) -> dict[str, object]:
    errors: list[str] = []
    checked_links: list[str] = []
    process_root = repo / "docs/process"

    for markdown in sorted(process_root.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative = target.split("#", 1)[0]
            if not relative:
                continue
            path = (markdown.parent / relative).resolve()
            checked_links.append(path.relative_to(repo.resolve()).as_posix())
            if not path.exists():
                errors.append(
                    f"missing documentation link target: {markdown.relative_to(repo)} -> {target}"
                )

    json_yaml_files = [
        *sorted((repo / "docs/process/templates").glob("*.yaml")),
        *sorted((repo / "docs/implementation").glob("*/task_state.yaml")),
        repo / "docs/implementation/ACTIVE_TASKS.yaml",
    ]
    checked_json: list[str] = []
    for path in json_yaml_files:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON-as-YAML: {path.relative_to(repo)}:{exc.lineno}")
            continue
        if not isinstance(value, dict):
            errors.append(f"JSON-as-YAML root must be object: {path.relative_to(repo)}")
        checked_json.append(path.relative_to(repo).as_posix())

    return {
        "status": "PASS" if not errors else "FAIL",
        "checked_link_targets": sorted(set(checked_links)),
        "checked_json_files": checked_json,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = validate_docs(args.repo.resolve())
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
