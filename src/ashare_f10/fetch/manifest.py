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
    return _load_compressed_json("field_mapping_cn")
