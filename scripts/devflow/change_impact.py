from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

IMPACT_ORDER = {"docs_only": 0, "devflow_only": 1, "product": 2}

DOCS_ONLY_PATTERNS = (
    "README.md",
    "LICENSE",
    "docs/**/*.md",
)

DEVFLOW_PATTERNS = (
    "AGENTS.md",
    "**/AGENTS.md",
    ".devflow/**",
    "docs/process/**",
    "docs/implementation/**",
    "docs/ENGINEERING_ISSUES_AND_LESSONS.md",
    "scripts/devflow/**",
    "tests/test_devflow*.py",
    ".github/actions/codex-thin-worker/**",
    ".github/workflows/*devflow*.yml",
    ".github/workflows/*codex*.yml",
    ".github/workflows/test.yml",
    ".github/workflows/e2e-688521.yml",
    ".github/dependabot.yml",
)


@dataclass(frozen=True)
class ImpactResult:
    impact: str
    changed_files: tuple[str, ...]
    reasons: tuple[str, ...]
    run_devflow_gate: bool
    run_full_test: bool
    run_e2e: bool


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def classify_paths(paths: list[str]) -> ImpactResult:
    normalized = sorted({path.strip().lstrip("./") for path in paths if path.strip()})
    impact = "docs_only"
    reasons: list[str] = []

    for path in normalized:
        if _matches(path, DEVFLOW_PATTERNS):
            if IMPACT_ORDER[impact] < IMPACT_ORDER["devflow_only"]:
                impact = "devflow_only"
            reasons.append(f"devflow:{path}")
            continue
        if _matches(path, DOCS_ONLY_PATTERNS):
            reasons.append(f"docs:{path}")
            continue
        impact = "product"
        reasons.append(f"product_or_unknown:{path}")

    if not normalized:
        impact = "devflow_only"
        reasons.append("empty_diff_requires_safe_devflow_gate")

    return ImpactResult(
        impact=impact,
        changed_files=tuple(normalized),
        reasons=tuple(reasons),
        run_devflow_gate=impact in {"devflow_only", "product"},
        run_full_test=impact == "product",
        run_e2e=impact == "product",
    )


def changed_files(base: str, head: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head],
        text=True,
    )
    return [line for line in output.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--paths-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    if args.paths_file:
        paths = args.paths_file.read_text(encoding="utf-8").splitlines()
    elif args.base:
        paths = changed_files(args.base, args.head)
    else:
        raise SystemExit("provide --base or --paths-file")

    result = classify_paths(paths)
    payload = asdict(result)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"impact={result.impact}\n")
            handle.write(f"run_devflow_gate={str(result.run_devflow_gate).lower()}\n")
            handle.write(f"run_full_test={str(result.run_full_test).lower()}\n")
            handle.write(f"run_e2e={str(result.run_e2e).lower()}\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
