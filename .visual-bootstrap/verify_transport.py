from __future__ import annotations

import base64
import hashlib
from pathlib import Path

EXPECTED = {
    "part_00.txt": "d44d7070d6dfe0c676ca9cb8aa78b276b6f02f37",
    "part_01.txt": "0f6fa59e5e9b25b3d4a90618c71571da897a4f87",
    "part_02.txt": "98630605727846895ae13dc2e296deb63caf4043",
    "part_03.txt": "bc8d6723b83bd5cc6c1876ad310410cc9ae4cdda",
    "part_04.txt": "3733b9b9b901b77b1354b750101c0f37503d5930",
    "part_05.txt": "b111891d18481ffa6f21542f7d4f7c8e4807c544",
    "part_06.txt": "236f75f65fe5f43d7f99ededce6f8a552676955e",
    "part_07.txt": "1cca770e42c701c2b8dd5ae6dffc5e633f38af23",
    "part_08.txt": "c958dad57a1d88cffb4dd1ca5f08146cfc274e77",
    "part_09.txt": "3571cc5b99199a5bf66b7c3657b9c55e1a39afc9",
    "part_10.txt": "4962e5ff6cbd3ab4d4960fecf94b9a3d850b751c",
    "part_11.txt": "8008a33b84e115ea92c86a42a2ab0fdeddb11a1c",
    "part_12.txt": "a1f628820e93f554ecf50909193dd57c5dc97b66",
    "part_13.txt": "2cf75679b5d1e2ef77b8dd773a1da85dc3f1f730",
    "part_14.txt": "a76c45b943baae88227136ac424d8942192749e0",
}
EXPECTED_ARCHIVE_SHA256 = "72a4cb48b8569dc789c441c4ae26301942216d546a1ebb01a6f70d6d5749b4eb"

root = Path(".visual-bootstrap")
chunks: list[bytes] = []
for name, expected in EXPECTED.items():
    raw = (root / name).read_bytes()
    actual = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    print(f"{name} bytes={len(raw)} blob={actual} expected={expected}", flush=True)
    if actual != expected:
        raise SystemExit(f"blob mismatch: {name}")
    chunks.append(raw)
encoded = b"".join(chunks).replace(b"\r", b"").replace(b"\n", b"")
decoded = base64.b64decode(encoded, validate=True)
actual_archive = hashlib.sha256(decoded).hexdigest()
print(f"base64_size={len(encoded)} archive_size={len(decoded)} archive_sha256={actual_archive}", flush=True)
if actual_archive != EXPECTED_ARCHIVE_SHA256:
    raise SystemExit("archive sha256 mismatch")
Path("/tmp/visual-patch.tar.xz").write_bytes(decoded)
