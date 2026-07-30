# W03 Result — PASS

## Implementation

Implemented completed single-stock run reuse and deterministic A-SCOPE export with:

- `data/<code>/latest.json` lookup;
- completed-run and failed-group validation;
- normalized facts discovery for Parquet, CSV and DuckDB;
- request/cutoff/mapping/schema/source fingerprints;
- cache-hit reuse without a new F10 fetch;
- point-in-time annual and standalone-quarter exports;
- field status, future-row, conflict and data-gap sidecars;
- formal output gates for duplicate keys, missing `available_at` and future rows.

## Semantics verified

- A compatible second export returns `CACHE_HIT` and does not invoke a provider.
- An incomplete source run is not accepted as a cache source.
- Unknown or future `available_at` values do not enter formal annual/quarterly output.
- Financial-template inapplicable values remain null with explicit field status.
- Export identity changes when a decision-relevant request, cutoff, mapping, schema or source-facts hash changes.

## Verification

The bridge-targeted GitHub-hosted suite completed with Ruff clean and 28 tests passing in autofix run `30538490813`. The single-stock tests cover completed-run location, source validation, cache fingerprints, cache hits, PIT filtering and required output files.

## Security and cost

- Codex calls: 0;
- Responses paid probes: 0;
- full-market official PDF validation: disabled;
- no new network request is made for a valid cache hit.

## Acceptance

W03 passed. Continue automatically to W04 batch execution and recovery.
