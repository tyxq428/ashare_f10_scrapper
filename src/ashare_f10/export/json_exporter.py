from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ashare_f10.fetch.manifest import load_field_mapping


def export_json(combined: dict[str, Any], output_dir: Path, data_store: dict[str, str]) -> Path:
    exports_dir = output_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    path = exports_dir / f"{combined['metadata']['security']['code']}_F10_full.json"
    metadata = dict(combined["metadata"])
    security = dict(metadata.get("security", {}))
    # Keep the compact internal key while also exposing the stable public alias
    # used by the original research JSON and downstream integrations.
    if security.get("code"):
        security.setdefault("security_code", security["code"])
    metadata["security"] = security

    payload = {
        "metadata": {
            **metadata,
            "data_store": data_store,
            "source_policy": "All values are fetched from the fixed live Eastmoney endpoint manifest.",
        },
        "field_mapping": load_field_mapping(),
        "groups": combined.get("groups", []),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    (exports_dir / "checksums.json").write_text(
        json.dumps({path.name: checksum}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
