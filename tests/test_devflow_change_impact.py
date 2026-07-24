from __future__ import annotations

import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from change_impact import classify_paths  # noqa: E402


def test_devflow_fixtures_do_not_trigger_product_or_real_e2e() -> None:
    result = classify_paths(
        [
            "tests/fixtures/devflow/descriptor-v2-xhigh.json",
            "scripts/devflow/task_descriptor.py",
            ".github/workflows/codex-task.yml",
        ]
    )
    assert result.impact == "devflow_only"
    assert result.run_devflow_gate is True
    assert result.run_full_test is False
    assert result.run_e2e is False


def test_unknown_product_path_still_fails_conservatively() -> None:
    result = classify_paths(["src/ashare_f10/new_feature.py"])
    assert result.impact == "product"
    assert result.run_full_test is True
    assert result.run_e2e is True
