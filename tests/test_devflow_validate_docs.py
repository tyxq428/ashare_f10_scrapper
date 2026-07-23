from __future__ import annotations

import json
import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from validate_docs import validate_docs  # noqa: E402


def scaffold(tmp_path: Path) -> None:
    (tmp_path / "docs/process/templates").mkdir(parents=True)
    (tmp_path / "docs/implementation/task").mkdir(parents=True)
    (tmp_path / "docs/process/README.md").write_text("[policy](policies/a.md)\n", encoding="utf-8")
    (tmp_path / "docs/process/policies").mkdir()
    (tmp_path / "docs/process/policies/a.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "docs/process/templates/task_state.template.yaml").write_text("{}\n", encoding="utf-8")
    (tmp_path / "docs/implementation/task/task_state.yaml").write_text("{}\n", encoding="utf-8")
    (tmp_path / "docs/implementation/ACTIVE_TASKS.yaml").write_text(
        json.dumps({"schema_version": 1, "tasks": []}), encoding="utf-8"
    )


def test_validate_docs_passes_existing_links_and_json(tmp_path: Path) -> None:
    scaffold(tmp_path)
    assert validate_docs(tmp_path)["status"] == "PASS"


def test_validate_docs_reports_missing_link(tmp_path: Path) -> None:
    scaffold(tmp_path)
    (tmp_path / "docs/process/README.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    result = validate_docs(tmp_path)
    assert result["status"] == "FAIL"
    assert "missing documentation link target" in result["errors"][0]


def test_validate_docs_reports_invalid_json_yaml(tmp_path: Path) -> None:
    scaffold(tmp_path)
    (tmp_path / "docs/implementation/ACTIVE_TASKS.yaml").write_text("not-json", encoding="utf-8")
    result = validate_docs(tmp_path)
    assert result["status"] == "FAIL"
    assert any("invalid JSON-as-YAML" in error for error in result["errors"])
