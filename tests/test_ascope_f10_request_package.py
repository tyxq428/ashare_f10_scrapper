from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pytest

from ashare_f10.ascope_bridge.request_package import RequestPackageError, resolve_request_package

FIXTURE = Path(__file__).parent / "fixtures" / "ascope_bridge"


def make_package(
    tmp_path: Path,
    *,
    manifest_patch: dict | None = None,
    row_patch: dict | None = None,
    duplicate: bool = False,
) -> Path:
    root = tmp_path / "source"
    batch_dir = root / "financial_batches"
    batch_dir.mkdir(parents=True)
    manifest = json.loads((FIXTURE / "financial_request_manifest.json").read_text(encoding="utf-8"))
    if manifest_patch:
        manifest.update(manifest_patch)
    (root / "financial_request_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    with (FIXTURE / "B001_smoke_5.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if row_patch:
        rows[0].update(row_patch)
    if duplicate:
        rows[-1] = rows[0].copy()
    with (batch_dir / "B001.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    archive = tmp_path / "request.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in root.rglob("*"):
            if path.is_file():
                output.write(path, path.relative_to(root).as_posix())
    return archive


def test_resolve_valid_smoke_preserves_source_order_and_writes_outputs(tmp_path: Path) -> None:
    source = make_package(tmp_path)
    output = tmp_path / "out"
    result = resolve_request_package(
        source,
        batch_id="B001",
        as_of_date="2026-07-30",
        smoke_count=3,
        output_dir=output,
    )
    assert [row.security_id for row in result.rows] == [
        "SZSE.000001",
        "SZSE.000002",
        "SZSE.000006",
    ]
    assert result.source_row_count == 5
    assert len(result.package_sha256) == 64
    assert json.loads((output / "request_validation.json").read_text())["status"] == "PASS"
    with (output / "request_snapshot.csv").open(encoding="utf-8-sig") as handle:
        assert len(list(csv.DictReader(handle))) == 3


def test_directory_and_zip_produce_same_rows(tmp_path: Path) -> None:
    source = make_package(tmp_path)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(source) as archive:
        archive.extractall(extracted)
    left = resolve_request_package(source, batch_id="B001", as_of_date="2026-07-30")
    right = resolve_request_package(extracted, batch_id="B001", as_of_date="2026-07-30")
    assert left.rows == right.rows
    assert left.selected_batch_sha256 == right.selected_batch_sha256


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"manifest_patch": {"status": "PENDING"}}, "REQUEST_STATUS_NOT_READY"),
        ({"manifest_patch": {"through": "2026-07-29"}}, "REQUEST_CUTOFF_MISMATCH"),
        ({"row_patch": {"security_id": "SSE.000001"}}, "REQUEST_EXCHANGE_MISMATCH"),
        ({"row_patch": {"name": "*ST测试"}}, "REQUEST_ST_STANDARD_PATH"),
        ({"duplicate": True}, "REQUEST_DUPLICATE_SECURITY"),
        ({"manifest_patch": {"standard_request_count": 6}}, "REQUEST_COUNT_MISMATCH"),
    ],
)
def test_invalid_packages_fail_closed(tmp_path: Path, kwargs: dict, code: str) -> None:
    source = make_package(tmp_path, **kwargs)
    with pytest.raises(RequestPackageError) as error:
        resolve_request_package(source, batch_id="B001", as_of_date="2026-07-30")
    assert error.value.code == code
