from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ashare_f10.export.excel_exporter import export_excel
from ashare_f10.export.json_exporter import export_json
from ashare_f10.normalize.facts import build_data_store


def build_exports(combined: dict[str, Any], output_dir: Path) -> dict[str, str]:
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
