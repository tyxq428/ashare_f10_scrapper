# W03 Plan — Single-Stock Cache Reuse and Export

## Goal

Export a compatible completed single-stock F10 run into A-SCOPE files without repeating network collection, while rejecting incomplete, stale or fingerprint-incompatible runs.

## Tasks

1. Locate `data/<code>/latest.json` and require `COMPLETED` with zero failed groups.
2. Resolve the run directory and normalized facts source.
3. Support `facts.parquet`, `f10.duckdb` and a CSV fixture fallback.
4. Infer or accept a financial industry template.
5. Build a decision fingerprint from request row, cutoff, source facts, mapping version and export schema.
6. Reuse a completed export only when all fingerprints and required files match.
7. Run the W02 mapper and requested-period filters.
8. Write annual, quarterly, field-status, gap, future and conflict outputs.
9. Write a per-stock manifest with source job lineage.
10. Prove an identical second export does not issue a fetch and returns `CACHE_HIT`.

## Gates

- Incomplete or partial current runs are rejected.
- Request and current-run stock codes must match.
- First export produces readable A-SCOPE CSVs.
- Second identical export is a cache hit.
- A changed request, source facts hash, mapping version or cutoff invalidates the cache.
- Financial template inference recognizes the B001 bank smoke case.

## Exit

W03 passes when a synthetic completed run exports successfully, a second run reuses it, and incomplete or mismatched runs fail closed.