#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${1:-target}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATCH_SHA="474ef40dcba1ea4ec41494ed17425ddfa5e375a8ff0b22b071107bd5aeed2199"

cd "$TARGET_DIR"

if [[ -f pyproject.toml && ! -d .bootstrap ]]; then
  echo "Project is already expanded; nothing to do."
  exit 0
fi

for path in .bootstrap/patch_{00..07}.txt; do
  test -s "$path"
done

rm -rf /tmp/f10-patch-only
mkdir -p /tmp/f10-patch-only
cat .bootstrap/patch_{00..07}.txt > /tmp/f10_patch.b64
base64 --decode /tmp/f10_patch.b64 > /tmp/f10_patch.tar.xz
echo "${PATCH_SHA}  /tmp/f10_patch.tar.xz" | sha256sum --check --strict
xz -t /tmp/f10_patch.tar.xz
tar -xJf /tmp/f10_patch.tar.xz -C /tmp/f10-patch-only

echo "Patch archive contains $(find /tmp/f10-patch-only -type f | wc -l) files."

required=(
  pyproject.toml
  README.md
  Dockerfile
  docker-compose.yml
  src/ashare_f10/api/app.py
  src/ashare_f10/fetch/pipeline.py
  src/ashare_f10/calculate/ttm.py
  src/ashare_f10/calculate/formula.py
  src/ashare_f10/export/bundle.py
  src/ashare_f10/resources/endpoint_manifest.json.gz.b64
  src/ashare_f10/resources/field_dictionary.json.gz.b64
  src/ashare_f10/web/index.html
  src/ashare_f10/web/app.js
  .github/workflows/test.yml
  .github/workflows/fetch-stock.yml
  .github/workflows/e2e-688521.yml
  scripts/start.sh
  scripts/start.ps1
  scripts/start.bat
)
missing=()
for path in "${required[@]}"; do
  if [[ ! -f "/tmp/f10-patch-only/${path}" ]]; then
    missing+=("$path")
  fi
done

if (( ${#missing[@]} == 0 )); then
  echo "Patch archive is a complete self-contained project; bypassing corrupted legacy base archive."
  tar -C /tmp/f10-patch-only -cf - . | tar -C "$TARGET_DIR" -xf -
  python3 -m compileall -q src
  node --check src/ashare_f10/web/app.js
  rm -rf .bootstrap
  rm -f .github/workflows/bootstrap-project.yml
  echo "Patch-only bootstrap completed successfully: $(find . -type f -not -path './.git/*' | wc -l) files."
  exit 0
fi

echo "Patch archive is incremental; missing ${#missing[@]} complete-project files:"
printf '  %s\n' "${missing[@]}"
echo "Falling back to legacy base-archive reconstruction solver."
exec bash "${SCRIPT_DIR}/bootstrap-f10.sh" "$TARGET_DIR"
