from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEVFLOW_OR_SECURITY_PATTERNS = (
    ".github/**",
    ".devflow/**",
    "AGENTS.md",
    "**/AGENTS.md",
    "docs/process/**",
    "docs/implementation/**",
    "scripts/devflow/**",
    "tests/test_devflow*",
    ".env",
    "secrets/**",
    "migrations/**",
)
MECHANICAL_REASON_CODES = {
    "RUFF_FORMAT",
    "RUFF_IMPORT_SORT",
    "LINT_ONLY",
    "FIXTURE_SCHEMA_MISMATCH",
    "GENERATED_CACHE",
    "DEPENDENCY_CACHE",
    "ARTIFACT_DOWNLOAD_TRANSIENT",
}
WEB_ONLY_REASON_CODES = {
    "STATE_CONSISTENCY",
    "WORKFLOW_FAILURE",
    "DEVFLOW_CORE",
    "SECURITY_POLICY",
    "SECRET_CONFIGURATION",
    "PERMISSION_BOUNDARY",
    "BUSINESS_DECISION",
    "SOURCE_CONFLICT",
    "ARCHITECTURE_DECISION",
    "DOCUMENTATION_POLICY",
}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason_code: str
    codex_candidate: bool
    explanation: str


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def route_failure(reason_code: str, failure_files: list[str]) -> RouteDecision:
    normalized = sorted({item.strip() for item in failure_files if item.strip()})
    if reason_code in MECHANICAL_REASON_CODES:
        return RouteDecision(
            route="DETERMINISTIC_REPAIR",
            reason_code=reason_code,
            codex_candidate=False,
            explanation="The failure has a trusted mechanical correction path.",
        )
    if reason_code in WEB_ONLY_REASON_CODES or any(
        _matches(path, DEVFLOW_OR_SECURITY_PATTERNS) for path in normalized
    ):
        return RouteDecision(
            route="CHATGPT_WEB",
            reason_code=reason_code,
            codex_candidate=False,
            explanation="The failure touches orchestration, policy, security, documentation or business semantics.",
        )
    if 2 <= len(normalized) <= 5:
        return RouteDecision(
            route="CODEX_CANDIDATE",
            reason_code=reason_code,
            codex_candidate=True,
            explanation=(
                "A narrow local product-code task may be considered, but only after explicit user approval "
                "and all zero-token eligibility gates pass."
            ),
        )
    return RouteDecision(
        route="CHATGPT_WEB",
        reason_code=reason_code,
        codex_candidate=False,
        explanation="The failure is too broad, too small to justify model startup, or lacks a safe bounded scope.",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason-code", required=True)
    parser.add_argument("--failure-file", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    decision = route_failure(args.reason_code, args.failure_file)
    text = json.dumps(asdict(decision), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
