from __future__ import annotations

import argparse
from pathlib import Path

from state_model import load_json_yaml, render_handoff, render_status


def _write_or_check(path: Path, expected: str, *, check: bool) -> bool:
    if check:
        return path.is_file() and path.read_text(encoding="utf-8") == expected
    path.write_text(expected, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state_file", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    state = load_json_yaml(args.state_file)
    task_dir = args.state_file.parent
    checks = {
        "STATUS.md": _write_or_check(task_dir / "STATUS.md", render_status(state), check=args.check),
        "HANDOFF.md": _write_or_check(task_dir / "HANDOFF.md", render_handoff(state), check=args.check),
    }
    for name, passed in checks.items():
        print(f"RENDER_{name.replace('.', '_').upper()}={'PASS' if passed else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
