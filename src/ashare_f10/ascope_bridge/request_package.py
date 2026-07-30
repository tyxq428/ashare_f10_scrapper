from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_NAME = "financial_request_manifest.json"
BATCH_DIR = "financial_batches"
REQUIRED_MANIFEST_FIELDS = {
    "status",
    "through",
    "batch_size",
    "batch_count",
    "standard_request_count",
}
REQUIRED_BATCH_FIELDS = {
    "batch_id",
    "security_id",
    "code",
    "name",
    "exchange",
    "request_annual_from",
    "request_quarterly_from",
    "request_through",
    "required_available_at",
    "request_status",
}
ALLOWED_EXCHANGES = {"SSE", "SZSE", "BSE"}
BATCH_ID = re.compile(r"^B\d{3}$")
CODE = re.compile(r"^\d{6}$")
STANDARD_ST_NAME = re.compile(r"^\s*\*?ST", re.IGNORECASE)


class RequestPackageError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class RequestManifest:
    status: str
    through: str
    batch_size: int
    batch_count: int
    standard_request_count: int
    identity_count: int | None = None
    high_risk_st_count: int | None = None
    archive_or_review_count: int | None = None
    generated_at_utc: str | None = None
    selection_rule: str | None = None


@dataclass(frozen=True, slots=True)
class RequestRow:
    batch_id: str
    security_id: str
    code: str
    name: str
    exchange: str
    request_annual_from: str
    request_quarterly_from: str
    request_through: str
    required_available_at: bool
    request_status: str


@dataclass(frozen=True, slots=True)
class ResolvedRequest:
    manifest: RequestManifest
    batch_id: str
    rows: tuple[RequestRow, ...]
    source_row_count: int
    smoke_count: int
    package_sha256: str
    manifest_sha256: str
    selected_batch_sha256: str
    all_batch_sha256: dict[str, str]
    source_kind: str
    source_name: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["rows"] = [asdict(row) for row in self.rows]
        return value


@dataclass(frozen=True, slots=True)
class _PackageFiles:
    source_kind: str
    source_name: str
    package_sha256: str
    manifest_path: str
    manifest_bytes: bytes
    batches: dict[str, tuple[str, bytes]]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_iso_date(value: Any, *, field: str, error_code: str) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise RequestPackageError(error_code, f"{field} is not ISO date: {text!r}") from exc


def _integer(value: Any, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise RequestPackageError("REQUEST_MANIFEST_INVALID", f"{field} must be an integer") from exc
    if result < 0:
        raise RequestPackageError("REQUEST_MANIFEST_INVALID", f"{field} must be non-negative")
    return result


def _boolean(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise RequestPackageError("REQUEST_ROW_SCHEMA_INVALID", f"{field} is not boolean: {value!r}")


def _normalize_member(value: str) -> str:
    return PurePosixPath(value.replace("\\", "/")).as_posix().lstrip("./")


def _read_zip(path: Path) -> _PackageFiles:
    manifest_members: list[str] = []
    batch_members: dict[str, list[str]] = {}
    with zipfile.ZipFile(path) as archive:
        for raw_name in archive.namelist():
            name = _normalize_member(raw_name)
            if name.endswith("/"):
                continue
            pure = PurePosixPath(name)
            if pure.name == MANIFEST_NAME:
                manifest_members.append(name)
            if len(pure.parts) >= 2 and pure.parts[-2] == BATCH_DIR and pure.suffix.lower() == ".csv":
                batch_members.setdefault(pure.stem.upper(), []).append(name)
        if not manifest_members:
            raise RequestPackageError("REQUEST_MANIFEST_NOT_FOUND", MANIFEST_NAME)
        if len(manifest_members) != 1:
            raise RequestPackageError(
                "REQUEST_MANIFEST_AMBIGUOUS", f"found {len(manifest_members)} manifest files"
            )
        duplicates = sorted(batch for batch, members in batch_members.items() if len(members) != 1)
        if duplicates:
            raise RequestPackageError(
                "REQUEST_BATCH_AMBIGUOUS", f"duplicate batch members: {duplicates}"
            )
        manifest_path = manifest_members[0]
        manifest_bytes = archive.read(manifest_path)
        batches = {
            batch_id: (members[0], archive.read(members[0]))
            for batch_id, members in sorted(batch_members.items())
        }
    return _PackageFiles(
        source_kind="zip",
        source_name=path.name,
        package_sha256=_sha256_file(path),
        manifest_path=manifest_path,
        manifest_bytes=manifest_bytes,
        batches=batches,
    )


def _read_directory(path: Path) -> _PackageFiles:
    manifests = sorted(item for item in path.rglob(MANIFEST_NAME) if item.is_file())
    if not manifests:
        raise RequestPackageError("REQUEST_MANIFEST_NOT_FOUND", MANIFEST_NAME)
    if len(manifests) != 1:
        raise RequestPackageError(
            "REQUEST_MANIFEST_AMBIGUOUS", f"found {len(manifests)} manifest files"
        )
    batch_paths: dict[str, list[Path]] = {}
    for item in path.rglob("*.csv"):
        if item.parent.name == BATCH_DIR:
            batch_paths.setdefault(item.stem.upper(), []).append(item)
    duplicates = sorted(batch for batch, members in batch_paths.items() if len(members) != 1)
    if duplicates:
        raise RequestPackageError("REQUEST_BATCH_AMBIGUOUS", f"duplicate batches: {duplicates}")
    batches = {
        batch_id: (str(items[0].relative_to(path)).replace("\\", "/"), items[0].read_bytes())
        for batch_id, items in sorted(batch_paths.items())
    }
    manifest_bytes = manifests[0].read_bytes()
    component_hashes = [
        f"{manifests[0].relative_to(path)}:{_sha256_bytes(manifest_bytes)}",
        *(f"{name}:{_sha256_bytes(content)}" for name, content in batches.values()),
    ]
    package_sha = _sha256_bytes("\n".join(component_hashes).encode("utf-8"))
    return _PackageFiles(
        source_kind="directory",
        source_name=path.name,
        package_sha256=package_sha,
        manifest_path=str(manifests[0].relative_to(path)).replace("\\", "/"),
        manifest_bytes=manifest_bytes,
        batches=batches,
    )


def _read_package(path: Path) -> _PackageFiles:
    if path.is_file() and zipfile.is_zipfile(path):
        return _read_zip(path)
    if path.is_dir():
        return _read_directory(path)
    raise RequestPackageError(
        "REQUEST_SOURCE_INVALID", f"source must be a ZIP archive or directory: {path}"
    )


def _manifest(value: bytes) -> RequestManifest:
    try:
        raw = json.loads(value.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestPackageError("REQUEST_MANIFEST_INVALID", "manifest is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise RequestPackageError("REQUEST_MANIFEST_INVALID", "manifest must be an object")
    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(raw))
    if missing:
        raise RequestPackageError("REQUEST_MANIFEST_INVALID", f"missing fields: {missing}")
    status = str(raw.get("status") or "").strip().upper()
    if status != "READY":
        raise RequestPackageError("REQUEST_STATUS_NOT_READY", f"status={status!r}")
    through = _parse_iso_date(
        raw.get("through"), field="through", error_code="REQUEST_MANIFEST_INVALID"
    )
    return RequestManifest(
        status=status,
        through=through,
        batch_size=_integer(raw.get("batch_size"), field="batch_size"),
        batch_count=_integer(raw.get("batch_count"), field="batch_count"),
        standard_request_count=_integer(
            raw.get("standard_request_count"), field="standard_request_count"
        ),
        identity_count=(
            _integer(raw.get("identity_count"), field="identity_count")
            if raw.get("identity_count") is not None
            else None
        ),
        high_risk_st_count=(
            _integer(raw.get("high_risk_st_count"), field="high_risk_st_count")
            if raw.get("high_risk_st_count") is not None
            else None
        ),
        archive_or_review_count=(
            _integer(raw.get("archive_or_review_count"), field="archive_or_review_count")
            if raw.get("archive_or_review_count") is not None
            else None
        ),
        generated_at_utc=(str(raw.get("generated_at_utc")) if raw.get("generated_at_utc") else None),
        selection_rule=(str(raw.get("selection_rule")) if raw.get("selection_rule") else None),
    )


def _rows(value: bytes, *, batch_id: str, manifest: RequestManifest) -> list[RequestRow]:
    try:
        text = value.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RequestPackageError("REQUEST_ROW_SCHEMA_INVALID", f"{batch_id} is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or ())
    missing = sorted(REQUIRED_BATCH_FIELDS - fields)
    if missing:
        raise RequestPackageError(
            "REQUEST_ROW_SCHEMA_INVALID", f"{batch_id} missing fields: {missing}"
        )
    result: list[RequestRow] = []
    for line_number, raw in enumerate(reader, start=2):
        actual_batch = str(raw.get("batch_id") or "").strip().upper()
        if actual_batch != batch_id:
            raise RequestPackageError(
                "REQUEST_ROW_SCHEMA_INVALID",
                f"{batch_id} line {line_number} has batch_id={actual_batch!r}",
            )
        exchange = str(raw.get("exchange") or "").strip().upper()
        if exchange not in ALLOWED_EXCHANGES:
            raise RequestPackageError(
                "REQUEST_EXCHANGE_MISMATCH",
                f"{batch_id} line {line_number} exchange={exchange!r}",
            )
        code = str(raw.get("code") or "").strip()
        if not CODE.fullmatch(code):
            raise RequestPackageError(
                "REQUEST_SECURITY_ID_INVALID", f"{batch_id} line {line_number} code={code!r}"
            )
        security_id = str(raw.get("security_id") or "").strip().upper()
        expected = f"{exchange}.{code}"
        if security_id != expected:
            raise RequestPackageError(
                "REQUEST_EXCHANGE_MISMATCH",
                f"{batch_id} line {line_number}: {security_id!r} != {expected!r}",
            )
        name = str(raw.get("name") or "").strip()
        if not name:
            raise RequestPackageError(
                "REQUEST_ROW_SCHEMA_INVALID", f"{batch_id} line {line_number} name is blank"
            )
        if STANDARD_ST_NAME.search(name):
            raise RequestPackageError("REQUEST_ST_STANDARD_PATH", f"{security_id} name={name!r}")
        annual_from = _parse_iso_date(
            raw.get("request_annual_from"),
            field="request_annual_from",
            error_code="REQUEST_ROW_SCHEMA_INVALID",
        )
        quarterly_from = _parse_iso_date(
            raw.get("request_quarterly_from"),
            field="request_quarterly_from",
            error_code="REQUEST_ROW_SCHEMA_INVALID",
        )
        through = _parse_iso_date(
            raw.get("request_through"),
            field="request_through",
            error_code="REQUEST_ROW_SCHEMA_INVALID",
        )
        if through != manifest.through:
            raise RequestPackageError(
                "REQUEST_CUTOFF_MISMATCH",
                f"{security_id} request_through={through} manifest={manifest.through}",
            )
        if annual_from > through or quarterly_from > through:
            raise RequestPackageError(
                "REQUEST_ROW_SCHEMA_INVALID", f"{security_id} start date is after cutoff"
            )
        required_available_at = _boolean(
            raw.get("required_available_at"), field="required_available_at"
        )
        if not required_available_at:
            raise RequestPackageError(
                "REQUEST_ROW_SCHEMA_INVALID", f"{security_id} must require available_at"
            )
        request_status = str(raw.get("request_status") or "").strip().upper()
        if request_status not in {"PENDING", "RETRY", "FAILED_RETRYABLE"}:
            raise RequestPackageError(
                "REQUEST_ROW_SCHEMA_INVALID",
                f"{security_id} unsupported request_status={request_status!r}",
            )
        result.append(
            RequestRow(
                batch_id=batch_id,
                security_id=security_id,
                code=code,
                name=name,
                exchange=exchange,
                request_annual_from=annual_from,
                request_quarterly_from=quarterly_from,
                request_through=through,
                required_available_at=required_available_at,
                request_status=request_status,
            )
        )
    if not result:
        raise RequestPackageError("REQUEST_COUNT_MISMATCH", f"{batch_id} contains zero rows")
    if len(result) > manifest.batch_size:
        raise RequestPackageError(
            "REQUEST_COUNT_MISMATCH",
            f"{batch_id} rows={len(result)} exceeds batch_size={manifest.batch_size}",
        )
    return result


def _validate_full_package(
    package: _PackageFiles, manifest: RequestManifest
) -> tuple[dict[str, list[RequestRow]], dict[str, str]]:
    expected_ids = [f"B{index:03d}" for index in range(1, manifest.batch_count + 1)]
    actual_ids = sorted(package.batches)
    if actual_ids != expected_ids:
        missing = sorted(set(expected_ids) - set(actual_ids))
        extra = sorted(set(actual_ids) - set(expected_ids))
        raise RequestPackageError(
            "REQUEST_COUNT_MISMATCH", f"batch IDs mismatch; missing={missing}, extra={extra}"
        )
    parsed: dict[str, list[RequestRow]] = {}
    hashes: dict[str, str] = {}
    all_security_ids: list[str] = []
    for batch_id in expected_ids:
        _name, content = package.batches[batch_id]
        hashes[batch_id] = _sha256_bytes(content)
        rows = _rows(content, batch_id=batch_id, manifest=manifest)
        parsed[batch_id] = rows
        all_security_ids.extend(row.security_id for row in rows)
    if len(all_security_ids) != manifest.standard_request_count:
        raise RequestPackageError(
            "REQUEST_COUNT_MISMATCH",
            f"rows={len(all_security_ids)} manifest={manifest.standard_request_count}",
        )
    seen: set[str] = set()
    duplicates: set[str] = set()
    for security_id in all_security_ids:
        if security_id in seen:
            duplicates.add(security_id)
        seen.add(security_id)
    if duplicates:
        raise RequestPackageError(
            "REQUEST_DUPLICATE_SECURITY", f"duplicate securities: {sorted(duplicates)[:20]}"
        )
    return parsed, hashes


def resolve_request_package(
    source: Path | str,
    *,
    batch_id: str,
    as_of_date: str,
    smoke_count: int = 0,
    output_dir: Path | str | None = None,
) -> ResolvedRequest:
    source_path = Path(source)
    normalized_batch = batch_id.strip().upper()
    if not BATCH_ID.fullmatch(normalized_batch):
        raise RequestPackageError("REQUEST_BATCH_NOT_FOUND", f"invalid batch ID: {batch_id!r}")
    cutoff = _parse_iso_date(
        as_of_date, field="as_of_date", error_code="REQUEST_CUTOFF_MISMATCH"
    )
    if smoke_count < 0:
        raise RequestPackageError("REQUEST_ROW_SCHEMA_INVALID", "smoke_count cannot be negative")
    package = _read_package(source_path)
    manifest = _manifest(package.manifest_bytes)
    if manifest.through != cutoff:
        raise RequestPackageError(
            "REQUEST_CUTOFF_MISMATCH", f"manifest={manifest.through}, requested={cutoff}"
        )
    parsed, hashes = _validate_full_package(package, manifest)
    if normalized_batch not in parsed:
        raise RequestPackageError("REQUEST_BATCH_NOT_FOUND", normalized_batch)
    source_rows = parsed[normalized_batch]
    selected_rows = source_rows[:smoke_count] if smoke_count else source_rows
    resolved = ResolvedRequest(
        manifest=manifest,
        batch_id=normalized_batch,
        rows=tuple(selected_rows),
        source_row_count=len(source_rows),
        smoke_count=min(smoke_count, len(source_rows)) if smoke_count else 0,
        package_sha256=package.package_sha256,
        manifest_sha256=_sha256_bytes(package.manifest_bytes),
        selected_batch_sha256=hashes[normalized_batch],
        all_batch_sha256=hashes,
        source_kind=package.source_kind,
        source_name=package.source_name,
    )
    if output_dir is not None:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        request_csv = target / "request_snapshot.csv"
        with request_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(selected_rows[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(row) for row in selected_rows)
        (target / "resolved_request.json").write_text(
            json.dumps(resolved.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        validation = {
            "status": "PASS",
            "batch_id": normalized_batch,
            "selected_count": len(selected_rows),
            "source_row_count": len(source_rows),
            "standard_request_count": manifest.standard_request_count,
            "batch_count": manifest.batch_count,
            "through": manifest.through,
            "package_sha256": package.package_sha256,
            "manifest_sha256": _sha256_bytes(package.manifest_bytes),
            "selected_batch_sha256": hashes[normalized_batch],
        }
        (target / "request_validation.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return resolved
