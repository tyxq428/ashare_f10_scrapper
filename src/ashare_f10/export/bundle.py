from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ashare_f10.export.excel_exporter import export_excel, validate_group_records
from ashare_f10.export.json_exporter import export_json
from ashare_f10.normalize.facts import build_data_store


def build_exports(combined: dict[str, Any], output_dir: Path) -> dict[str, str]:
    # Fail before any downstream file is produced when a stale or corrupted
    # checkpoint reports records that are not actually present in its payload.
    validate_group_records(combined)
    store = build_data_store(combined, output_dir)
    json_path = export_json(combined, output_dir, store)
    excel_path = export_excel(combined, output_dir)
    artifacts = {
        "json": str(json_path),
        "excel": str(excel_path),
        "parquet": store["parquet"],
        "duckdb": store["duckdb"],
        "fact_count": store["fact_count"],
    }
    (output_dir / "artifacts.json").write_text(
        json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return artifacts
