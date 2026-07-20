#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${1:-target}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
EXPECTED_BASE_SHA="0d03e7c23e1d1a2c8d264b1b29a9f805dad8442d98bdefc8c4521722c9465bab"
EXPECTED_PATCH_SHA="474ef40dcba1ea4ec41494ed17425ddfa5e375a8ff0b22b071107bd5aeed2199"
CURRENT_STEP="initialization"

on_error() {
  local exit_code=$?
  echo "::error::Bootstrap failed in step: ${CURRENT_STEP} (exit ${exit_code})"
  echo "Repository bootstrap files:"
  find "${TARGET_DIR}/.bootstrap" -maxdepth 1 -type f -printf '%f %s bytes\n' | sort || true
  exit "${exit_code}"
}
trap on_error ERR

cd "${TARGET_DIR}"

if [[ -f pyproject.toml && ! -d .bootstrap ]]; then
  echo "Project is already expanded; nothing to do."
  exit 0
fi

CURRENT_STEP="verify bootstrap input set"
required=(
  .bootstrap/part_001.txt
  .bootstrap/part_002b_00.txt
  .bootstrap/part_002b_01.txt
  .bootstrap/part_002b_02.txt
  .bootstrap/part_002c_00.txt
  .bootstrap/part_002c_01.txt
  .bootstrap/part_002c_02.txt
  .bootstrap/part_003.txt
  .bootstrap/part_004.txt
  .bootstrap/part_005b_00.txt
  .bootstrap/part_005b_01.txt
  .bootstrap/part_005b_02.txt
  .bootstrap/part_006.txt
)
for path in "${required[@]}"; do
  test -s "$path"
done
for path in .bootstrap/patch_{00..07}.txt; do
  test -s "$path"
done

echo "Bootstrap input sizes:"
wc -c "${required[@]}" .bootstrap/patch_{00..07}.txt

CURRENT_STEP="solve and verify base archive reconstruction"
export TARGET_DIR EXPECTED_BASE_SHA
python3 - <<'PY'
from __future__ import annotations

import base64
import binascii
import hashlib
import itertools
import os
from pathlib import Path

root = Path(os.environ["TARGET_DIR"])
expected = os.environ["EXPECTED_BASE_SHA"]
boot = root / ".bootstrap"


def read(name: str) -> bytes:
    return (boot / name).read_bytes().strip()


def b64decode(data: bytes, *, validate: bool = False) -> bytes | None:
    compact = b"".join(data.split())
    try:
        return base64.b64decode(compact, validate=validate)
    except (binascii.Error, ValueError):
        return None


def unique(name_values: list[tuple[str, bytes | None]]) -> list[tuple[str, bytes]]:
    seen: set[bytes] = set()
    result: list[tuple[str, bytes]] = []
    for name, value in name_values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append((name, value))
    return result

p1 = read("part_001.txt")
p2c = b"".join(read(f"part_002c_{index:02d}.txt") for index in range(3))
p2b0 = read("part_002b_00.txt")
p2b1 = read("part_002b_01.txt")
p2b2 = read("part_002b_02.txt")
p3 = read("part_003.txt")
p4 = read("part_004.txt")
p5 = b"".join(read(f"part_005b_{index:02d}.txt") for index in range(3))
p6 = read("part_006.txt")

part2_candidates = unique([
    ("decode(c0+c1+c2+b1+b2)", b64decode(p2c + p2b1 + p2b2)),
    ("decode(c0+c1+c2)+decode(b1)+decode(b2)",
     (b64decode(p2c) or b"") + (b64decode(p2b1) or b"") + (b64decode(p2b2) or b"")),
    ("decode(c0+c1+c2)+b1+b2", (b64decode(p2c) or b"") + p2b1 + p2b2),
    ("raw(c0+c1+c2+b1+b2)", p2c + p2b1 + p2b2),
    ("raw(b0+b1+b2)", p2b0 + p2b1 + p2b2),
    ("decode(b0+b1+b2)", b64decode(p2b0 + p2b1 + p2b2)),
    ("decode(b0)+decode(b1)+decode(b2)",
     (b64decode(p2b0) or b"") + (b64decode(p2b1) or b"") + (b64decode(p2b2) or b"")),
])
part5_candidates = unique([
    ("decode(b0+b1+b2)", b64decode(p5)),
    ("decode(b0)+decode(b1)+decode(b2)",
     b"".join((b64decode(read(f"part_005b_{index:02d}.txt")) or b"") for index in range(3))),
    ("raw(b0+b1+b2)", p5),
])

print("part2 candidates:", [(name, len(value)) for name, value in part2_candidates])
print("part5 candidates:", [(name, len(value)) for name, value in part5_candidates])

attempts = 0
for (part2_name, part2), (part5_name, part5) in itertools.product(part2_candidates, part5_candidates):
    attempts += 1
    assembled_b64 = p1 + part2 + p3 + p4 + part5 + p6
    archive = b64decode(assembled_b64)
    if archive is None:
        continue
    digest = hashlib.sha256(archive).hexdigest()
    print(
        f"attempt {attempts}: part2={part2_name}; part5={part5_name}; "
        f"b64_bytes={len(assembled_b64)}; archive_bytes={len(archive)}; sha={digest}"
    )
    if digest == expected:
        Path("/tmp/project.b64").write_bytes(assembled_b64)
        Path("/tmp/project.tar.xz").write_bytes(archive)
        print(f"MATCHED base archive using part2={part2_name}; part5={part5_name}")
        break
else:
    raise SystemExit(f"No reconstruction candidate matched expected SHA-256 {expected}")
PY

echo "${EXPECTED_BASE_SHA}  /tmp/project.tar.xz" | sha256sum --check --strict
xz -t /tmp/project.tar.xz
tar -tJf /tmp/project.tar.xz >/tmp/project-file-list.txt
echo "Base archive verified: $(wc -l </tmp/project-file-list.txt) entries"

CURRENT_STEP="reconstruct and verify patch archive"
cat .bootstrap/patch_{00..07}.txt > /tmp/f10_patch.b64
base64 --decode /tmp/f10_patch.b64 > /tmp/f10_patch.tar.xz
echo "${EXPECTED_PATCH_SHA}  /tmp/f10_patch.tar.xz" | sha256sum --check --strict
xz -t /tmp/f10_patch.tar.xz
tar -tJf /tmp/f10_patch.tar.xz >/tmp/patch-file-list.txt
echo "Patch archive verified: $(wc -l </tmp/patch-file-list.txt) entries"

CURRENT_STEP="extract archives"
tar -xJf /tmp/project.tar.xz -C .
tar -xJf /tmp/f10_patch.tar.xz -C .

CURRENT_STEP="verify expanded project"
required_outputs=(
  pyproject.toml
  src/ashare_f10/api/app.py
  .github/workflows/fetch-stock.yml
  .github/workflows/e2e-688521.yml
  src/ashare_f10/web/index.html
  Dockerfile
  scripts/start.sh
  scripts/start.ps1
  scripts/start.bat
)
for path in "${required_outputs[@]}"; do
  test -f "$path"
done

python3 -m compileall -q src
node --check src/ashare_f10/web/app.js

echo "Expanded project files: $(find . -type f -not -path './.git/*' -not -path './.bootstrap/*' | wc -l)"

CURRENT_STEP="remove bootstrap transport files"
rm -rf .bootstrap
rm -f .github/workflows/bootstrap-project.yml

echo "Bootstrap reconstruction completed successfully."
