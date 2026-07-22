from __future__ import annotations

from collections.abc import Iterable
from importlib.resources import files

from ashare_f10.raw_sources.models import PackPolicy, RawSource, RawSourceManifest, SecurityEntity


def load_raw_source_manifest() -> RawSourceManifest:
    resource = files("ashare_f10.resources").joinpath("raw_source_manifest.json")
    return RawSourceManifest.model_validate_json(resource.read_text(encoding="utf-8"))


def resolve_pack_policy(pack_id: str, security_context: SecurityEntity) -> PackPolicy:
    manifest = load_raw_source_manifest()
    item = manifest.packs.get(pack_id)
    if item is None:
        raise KeyError(f"Unknown Raw Pack pack_id: {pack_id}")
    policy = str(item.get("default_policy", "CONDITIONAL_FETCH"))
    if pack_id == "P2_BOND_OVERSEAS_MACRO" and not security_context.company_full_name_en:
        policy = "INDEX_ONLY"
    return PackPolicy(pack_id=pack_id, default_policy=policy, description=str(item.get("description", "")))


def _normalize_packs(packs: str | Iterable[str] | None, manifest: RawSourceManifest) -> list[str]:
    if packs is None or packs == "default":
        return list(manifest.default_packs)
    if packs == "all":
        return list(manifest.packs)
    if isinstance(packs, str):
        values = [value.strip() for value in packs.split(",") if value.strip()]
    else:
        values = [str(value).strip() for value in packs if str(value).strip()]
    unknown = sorted(set(values) - set(manifest.packs))
    if unknown:
        raise ValueError(f"Unknown Raw Pack packs: {', '.join(unknown)}")
    return list(dict.fromkeys(values))


def select_sources(
    security: SecurityEntity,
    include_raw_pack: bool,
    packs: str | Iterable[str] | None = None,
    *,
    include_unimplemented: bool = False,
) -> list[RawSource]:
    if not include_raw_pack:
        return []
    manifest = load_raw_source_manifest()
    selected_packs = set(_normalize_packs(packs, manifest))
    selected: list[RawSource] = []
    for source in manifest.sources:
        if source.pack_id not in selected_packs:
            continue
        if not source.implemented and not include_unimplemented:
            continue
        if packs in (None, "default") and not source.default_enabled:
            continue
        if security.listed_market != "SSE" and source.collector in {"sse_disclosure", "roadshow_seed"}:
            continue
        selected.append(source)
    return sorted(selected, key=lambda item: (item.pack_id, item.priority, item.source_id))


def manifest_summary() -> dict[str, object]:
    manifest = load_raw_source_manifest()
    return {
        "schema_version": manifest.schema_version,
        "source_count": len(manifest.sources),
        "implemented_source_count": sum(source.implemented for source in manifest.sources),
        "pack_count": len(manifest.packs),
        "packs": list(manifest.packs),
        "status_labels": manifest.status_labels,
    }
