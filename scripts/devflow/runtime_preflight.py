from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from endpoint_utils import normalize_responses_endpoint


def inspect_runtime(endpoint: str, api_key: str, model: str) -> dict[str, Any]:
    endpoint = endpoint.strip()
    api_key = api_key.strip()
    model = model.strip()

    checks: dict[str, bool] = {
        "endpoint_present": bool(endpoint),
        "api_key_present": bool(api_key),
        "model_present": bool(model),
        "endpoint_valid_https": False,
    }
    failure_codes: list[str] = []

    if not endpoint:
        failure_codes.append("MISSING_ENDPOINT")
    else:
        try:
            normalize_responses_endpoint(endpoint)
        except ValueError:
            failure_codes.append("INVALID_ENDPOINT")
        else:
            checks["endpoint_valid_https"] = True

    if not api_key:
        failure_codes.append("MISSING_API_KEY")
    if not model:
        failure_codes.append("MISSING_MODEL")

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "failure_codes": failure_codes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Codex runtime configuration without printing values")
    parser.add_argument("--output", type=Path, default=Path("/tmp/devflow-runtime-preflight.json"))
    args = parser.parse_args()

    result = inspect_runtime(
        os.environ.get("AGENT_RESPONSES_ENDPOINT", ""),
        os.environ.get("AGENT_API_KEY", ""),
        os.environ.get("AGENT_MODEL", ""),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for name, passed in result["checks"].items():
        print(f"RUNTIME_PREFLIGHT_{name.upper()}={'PASS' if passed else 'FAIL'}")
    for code in result["failure_codes"]:
        print(f"RUNTIME_PREFLIGHT_FAILURE_CODE={code}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
