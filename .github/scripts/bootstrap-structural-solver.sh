#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${1:-target}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
PATCH_SHA="474ef40dcba1ea4ec41494ed17425ddfa5e375a8ff0b22b071107bd5aeed2199"

cd "$TARGET_DIR"
export TARGET_DIR

python3 - <<'PY'
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import itertools
import json
import lzma
import os
import tarfile
from pathlib import Path

root = Path(os.environ["TARGET_DIR"])
boot = root / ".bootstrap"


def read(name: str) -> bytes:
    return (boot / name).read_bytes().strip()


def decode(data: bytes) -> bytes | None:
    try:
        return base64.b64decode(b"".join(data.split()), validate=False)
    except (binascii.Error, ValueError):
        return None


def unique(values: list[tuple[str, bytes | None]]) -> list[tuple[str, bytes]]:
    result: list[tuple[str, bytes]] = []
    seen: set[bytes] = set()
    for name, value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append((name, value))
    return result

p1 = read("part_001.txt")
p2c = b"".join(read(f"part_002c_{i:02d}.txt") for i in range(3))
p2b = [read(f"part_002b_{i:02d}.txt") for i in range(3)]
p3 = read("part_003.txt")
p3c_names = ["part_003c_00.txt", "part_003c_01.txt", "part_003c_02.txt", "part_003c_04.txt", "part_003c_05.txt"]
p3c = b"".join(read(name) for name in p3c_names)
p4 = read("part_004.txt")
p5b = [read(f"part_005b_{i:02d}.txt") for i in range(3)]
p5 = b"".join(p5b)
p6 = read("part_006.txt")

part2 = unique([
    ("decode(c+b1+b2)", decode(p2c + p2b[1] + p2b[2])),
    ("decode(c)+b1+b2", (decode(p2c) or b"") + p2b[1] + p2b[2]),
    ("decode(c)+decode(b1)+decode(b2)", (decode(p2c) or b"") + (decode(p2b[1]) or b"") + (decode(p2b[2]) or b"")),
    ("raw(c+b1+b2)", p2c + p2b[1] + p2b[2]),
    ("raw(b0+b1+b2)", b"".join(p2b)),
    ("decode(b0+b1+b2)", decode(b"".join(p2b))),
    ("decode-each(b0,b1,b2)", b"".join(decode(item) or b"" for item in p2b)),
    ("decode(c)", decode(p2c)),
    ("raw(b0)", p2b[0]),
])
part3 = unique([
    ("raw(part3)", p3),
    ("decode(part3)", decode(p3)),
    ("raw(c0+c1+c2+c4+c5)", p3c),
    ("decode(c0+c1+c2+c4+c5)", decode(p3c)),
    ("decode-each(c chunks)", b"".join(decode(read(name)) or b"" for name in p3c_names)),
])
part5 = unique([
    ("decode(b0+b1+b2)", decode(p5)),
    ("decode-each(b0,b1,b2)", b"".join(decode(item) or b"" for item in p5b)),
    ("raw(b0+b1+b2)", p5),
])

required_names = {
    "pyproject.toml",
    "src/ashare_f10/config.py",
    "src/ashare_f10/fetch/pipeline.py",
}
results = []
valid = []
for index, ((n2, v2), (n3, v3), (n5, v5)) in enumerate(itertools.product(part2, part3, part5), 1):
    assembled = p1 + v2 + v3 + p4 + v5 + p6
    archive = decode(assembled)
    if archive is None:
        continue
    digest = hashlib.sha256(archive).hexdigest()
    item = {
        "index": index,
        "part2": n2,
        "part3": n3,
        "part5": n5,
        "assembled_bytes": len(assembled),
        "archive_bytes": len(archive),
        "sha256": digest,
        "xz_valid": False,
        "tar_valid": False,
        "file_count": 0,
        "required_hits": 0,
    }
    try:
        tar_bytes = lzma.decompress(archive)
        item["xz_valid"] = True
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tf:
            names = {member.name.lstrip("./") for member in tf.getmembers() if member.isfile()}
        item["tar_valid"] = True
        item["file_count"] = len(names)
        item["required_hits"] = len(required_names & names)
        item["sample_files"] = sorted(names)[:20]
        valid.append((item, archive, names))
    except Exception as exc:  # noqa: BLE001
        item["error"] = f"{type(exc).__name__}: {exc}"
    results.append(item)

(root / "bootstrap-structural-candidates.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"Evaluated {len(results)} decodable candidates; structurally valid archives: {len(valid)}")
for item, _, _ in valid:
    print(json.dumps(item, ensure_ascii=False))

if not valid:
    raise SystemExit("No candidate is a valid xz-compressed tar archive")

# Prefer candidates containing all known base files, then most required hits/file count.
valid.sort(key=lambda entry: (entry[0]["required_hits"], entry[0]["file_count"], entry[0]["archive_bytes"]), reverse=True)
selected, archive, names = valid[0]
if selected["required_hits"] < 2 or selected["file_count"] < 20:
    raise SystemExit(f"Best structural candidate is implausible: {selected}")
Path("/tmp/project.tar.xz").write_bytes(archive)
(root / "bootstrap-selected-candidate.json").write_text(
    json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Selected structural base archive:", json.dumps(selected, ensure_ascii=False))
PY

xz -t /tmp/project.tar.xz
tar -tJf /tmp/project.tar.xz >/tmp/project-file-list.txt
echo "Selected base archive has $(wc -l </tmp/project-file-list.txt) entries."

cat .bootstrap/patch_{00..07}.txt > /tmp/f10_patch.b64
base64 --decode /tmp/f10_patch.b64 > /tmp/f10_patch.tar.xz
echo "${PATCH_SHA}  /tmp/f10_patch.tar.xz" | sha256sum --check --strict
xz -t /tmp/f10_patch.tar.xz

tar -xJf /tmp/project.tar.xz -C .
tar -xJf /tmp/f10_patch.tar.xz -C .

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
rm -rf .bootstrap
rm -f .github/workflows/bootstrap-project.yml
rm -f bootstrap-diagnostic.log bootstrap-diagnostic.json bootstrap-structural-candidates.json bootstrap-selected-candidate.json

echo "Structural bootstrap completed successfully: $(find . -type f -not -path './.git/*' | wc -l) files."
