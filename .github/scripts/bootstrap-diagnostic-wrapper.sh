#!/usr/bin/env bash
set -uo pipefail

TARGET_DIR="${1:-target}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
LOG_FILE="${TARGET_DIR}/bootstrap-diagnostic.log"
JSON_FILE="${TARGET_DIR}/bootstrap-diagnostic.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

set +e
bash "${SCRIPT_DIR}/bootstrap-patch-first.sh" "${TARGET_DIR}" >"${LOG_FILE}" 2>&1
status=$?
set -e

cat "${LOG_FILE}"

export TARGET_DIR LOG_FILE JSON_FILE status
python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

root = Path(os.environ["TARGET_DIR"])
log_path = Path(os.environ["LOG_FILE"])
status = int(os.environ["status"])
lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
bootstrap = root / ".bootstrap"
files = []
if bootstrap.exists():
    files = [
        {"name": path.name, "size_bytes": path.stat().st_size}
        for path in sorted(bootstrap.iterdir())
        if path.is_file()
    ]
step = None
for line in reversed(lines):
    marker = "Bootstrap failed in step: "
    if marker in line:
        step = line.split(marker, 1)[1]
        break
payload = {
    "exit_code": status,
    "failed_step": step,
    "log_line_count": len(lines),
    "log_tail": lines[-120:],
    "bootstrap_files": files,
    "pyproject_exists": (root / "pyproject.toml").exists(),
    "app_exists": (root / "src/ashare_f10/api/app.py").exists(),
}
Path(os.environ["JSON_FILE"]).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
PY

exit "${status}"
