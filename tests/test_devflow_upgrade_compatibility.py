from __future__ import annotations

import json
import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from upgrade_compatibility import (  # noqa: E402
    preview_state_v2,
    run_matrix,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "devflow"


def test_upgrade_compatibility_matrix_passes() -> None:
    result = run_matrix(FIXTURES)

    assert result["status"] == "PASS"
    assert result["failed_cases"] == []
    assert result["cases"]["descriptor_v1_low_read"][
        "effective_effort"
    ] == "xhigh"
    assert result["cases"]["descriptor_v2_low_rejected"][
        "rejected"
    ] is True


def test_state_migration_preview_is_idempotent_and_non_mutating() -> None:
    path = FIXTURES / "state-v1-done.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    snapshot = json.loads(json.dumps(original))

    first = preview_state_v2(original)
    second = preview_state_v2(first)

    assert original == snapshot
    assert first == second
    assert first["schema_version"] == 2
    assert first["status"] == "DONE"
    assert first["acceptance"]["domain"] == "research"
    assert first["acceptance"]["status"] == "PASS"
    assert first["security_status"] == "PASS"
