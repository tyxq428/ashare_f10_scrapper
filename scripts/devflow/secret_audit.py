from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit


def secret_variants(endpoint: str, api_key: str, model: str = "") -> set[bytes]:
    parsed = urlsplit(endpoint)
    text_values = {
        endpoint,
        endpoint.rstrip("/"),
        parsed.netloc,
        parsed.hostname or "",
        api_key,
        model,
        quote(endpoint, safe=""),
        quote(api_key, safe=""),
        base64.b64encode(endpoint.encode()).decode(),
        base64.urlsafe_b64encode(endpoint.encode()).decode(),
        base64.b64encode(api_key.encode()).decode(),
        base64.urlsafe_b64encode(api_key.encode()).decode(),
    }
    return {value.encode("utf-8") for value in text_values if len(value) >= 8}


def scan(paths: list[Path], variants: set[bytes]) -> tuple[int, list[str], list[str]]:
    scanned = 0
    leaked: list[str] = []
    missing: list[str] = []
    for path in paths:
        if not path.is_file():
            missing.append(path.as_posix())
            continue
        scanned += 1
        data = path.read_bytes()
        if any(variant in data for variant in variants):
            leaked.append(path.as_posix())
    return scanned, leaked, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--output", type=Path, default=Path("secret-audit.json"))
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    endpoint = os.environ["AGENT_RESPONSES_ENDPOINT"]
    api_key = os.environ["AGENT_API_KEY"]
    model = os.environ.get("AGENT_MODEL", "")
    scanned, leaked, missing = scan(
        [Path(item) for item in args.paths], secret_variants(endpoint, api_key, model)
    )
    failed = bool(leaked) or (bool(missing) and not args.allow_missing)
    summary = {
        "status": "FAIL" if failed else "PASS",
        "files_scanned": scanned,
        "leak_file_count": len(leaked),
        "missing_path_count": len(missing),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"SECRET_AUDIT_STATUS={summary['status']}")
    print(f"SECRET_AUDIT_FILES_SCANNED={scanned}")
    print(f"SECRET_AUDIT_LEAK_FILE_COUNT={len(leaked)}")
    print(f"SECRET_AUDIT_MISSING_PATH_COUNT={len(missing)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
