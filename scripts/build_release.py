from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    release = root / "artifacts" / "release"
    if release.exists():
        shutil.rmtree(release)
    release.mkdir(parents=True)
    for name in ("README.md", "pyproject.toml", "Dockerfile", "docker-compose.yml", ".env.example"):
        shutil.copy2(root / name, release / name)
    shutil.copytree(root / "src", release / "src")
    shutil.copytree(root / "scripts", release / "scripts")
    archive = shutil.make_archive(str(root / "artifacts" / "ashare-f10-platform"), "zip", release)
    manifest = {"archive": Path(archive).name, "sha256": sha256(Path(archive))}
    (root / "artifacts" / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
