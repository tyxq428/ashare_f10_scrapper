from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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
    "PRODUCT_FULL_GATE_FAILED",
    "POST_MERGE_GATE_FAILED",
    "MERGE_BOUNDARY",
}
ALLOWED_CODEX_REASON_CODES = {
    "LOCAL_IMPLEMENTATION_DEFECT",
    "LOCAL_TEST_GAP",
    "BOUNDED_PURE_REFACTOR",
}
ALLOWED_UNIQUE_BENEFITS = {
    "LOCAL_ITERATIVE_TOOL_LOOP",
    "BACKGROUND_WORKER_EXPLICITLY_REQUESTED",
}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason_code: str
    codex_candidate: bool
    explanation: str


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _valid_web_assessment(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("attempted") is True
        and value.get("can_complete_in_web") is False
        and value.get("reason_code") in ALLOWED_UNIQUE_BENEFITS
        and isinstance(value.get("summary"), str)
        and bool(value["summary"].strip())
    )


def route_failure(
    reason_code: str,
    failure_files: list[str],
    *,
    web_resolution_assessment: dict[str, Any] | None = None,
) -> RouteDecision:
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
            explanation=(
                "The failure touches orchestration, policy, security, "
                "documentation, integration gates or business semantics."
            ),
        )
    if reason_code not in ALLOWED_CODEX_REASON_CODES:
        return RouteDecision(
            route="CHATGPT_WEB",
            reason_code=reason_code,
            codex_candidate=False,
            explanation="Unknown or unapproved reason codes fail closed to ChatGPT Web.",
        )
    if not _valid_web_assessment(web_resolution_assessment):
        return RouteDecision(
            route="CHATGPT_WEB",
            reason_code=reason_code,
            codex_candidate=False,
            explanation=(
                "A task is not a Codex candidate until ChatGPT Web records "
                "why the current session cannot practically complete it."
            ),
        )
    if 2 <= len(normalized) <= 5:
        return RouteDecision(
            route="CODEX_CANDIDATE",
            reason_code=reason_code,
            codex_candidate=True,
            explanation=(
                "A narrow local product-code task has an approved reason and "
                "a documented unique runner-side benefit. Candidate status "
                "still requires user approval and all zero-token gates."
            ),
        )
    return RouteDecision(
        route="CHATGPT_WEB",
        reason_code=reason_code,
        codex_candidate=False,
        explanation=(
            "Codex candidates require exactly two to five safe failure files; "
            "single-file simple work and broader tasks stay in ChatGPT Web."
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason-code", required=True)
    parser.add_argument("--failure-file", action="append", default=[])
    parser.add_argument("--web-assessment", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    assessment = None
    if args.web_assessment:
        value = json.loads(args.web_assessment.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise SystemExit("web assessment root must be an object")
        assessment = value
    decision = route_failure(
        args.reason_code,
        args.failure_file,
        web_resolution_assessment=assessment,
    )
    text = json.dumps(asdict(decision), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
