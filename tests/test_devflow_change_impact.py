from __future__ import annotations

import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from change_impact import classify_paths  # noqa: E402


def test_plain_project_documentation_is_docs_only() -> None:
    result = classify_paths(["README.md", "docs/user-guide.md"])
    assert result.impact == "docs_only"
    assert result.run_devflow_gate is False
    assert result.run_full_test is False
    assert result.run_e2e is False


def test_process_and_state_changes_are_devflow_only() -> None:
    result = classify_paths(
        [
            "AGENTS.md",
            "docs/process/policies/security-and-codex.md",
            "docs/implementation/task/W01_plan.md",
            "scripts/devflow/state_model.py",
            "tests/test_devflow.py",
        ]
    )
    assert result.impact == "devflow_only"
    assert result.run_devflow_gate is True
    assert result.run_full_test is False
    assert result.run_e2e is False


def test_product_source_or_business_test_requires_full_gate_and_e2e() -> None:
    result = classify_paths(["src/ashare_f10/api/app.py", "tests/test_search_filters.py"])
    assert result.impact == "product"
    assert result.run_full_test is True
    assert result.run_e2e is True


def test_unknown_path_fails_safe_to_product() -> None:
    result = classify_paths(["tools/unknown-generator.sh"])
    assert result.impact == "product"
    assert "product_or_unknown:tools/unknown-generator.sh" in result.reasons


def test_mixed_docs_and_product_is_product() -> None:
    result = classify_paths(["docs/user-guide.md", "scripts/run_resilient_fetch.py"])
    assert result.impact == "product"


def test_e2e_workflow_change_is_devflow_only_but_still_runs_contract_gate() -> None:
    result = classify_paths([".github/workflows/e2e-688521.yml"])
    assert result.impact == "devflow_only"
    assert result.run_devflow_gate is True
    assert result.run_e2e is False


def test_empty_diff_runs_safe_devflow_gate() -> None:
    result = classify_paths([])
    assert result.impact == "devflow_only"
    assert result.run_devflow_gate is True
