from __future__ import annotations

import base64
import gzip
import json
from importlib.resources import files
from typing import Any


def _load_compressed_json(name: str) -> dict[str, Any]:
    resource = files("ashare_f10.resources").joinpath(f"{name}.json.gz.b64")
    compressed = base64.b64decode(resource.read_bytes())
    return json.loads(gzip.decompress(compressed).decode("utf-8"))


def load_manifest() -> dict[str, Any]:
    return _load_compressed_json("endpoint_manifest_v1")


def load_field_mapping() -> dict[str, Any]:
    mapping = _load_compressed_json("field_mapping_cn")
    # Corrections remain a small, reviewable resource layered over the large
    # generated mapping. This avoids regenerating the full compressed mapping
    # whenever units or technical metadata labels are refined.
    patch_resource = files("ashare_f10.resources").joinpath("field_mapping_patch_v1.json")
    if patch_resource.is_file():
        patch = json.loads(patch_resource.read_text(encoding="utf-8"))
        mapping.setdefault("global", {}).update(patch.get("global", {}))
        mapping.setdefault("context", {}).update(patch.get("context", {}))
    return mapping
