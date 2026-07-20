# Architecture

## Layers

1. **Fixed endpoint manifest**: versioned request templates generated from the verified HAR workflow.
2. **Fetcher**: code substitution, concurrent groups, pagination, retries, cache and precise fallback.
3. **Raw cache**: gzip JSON for every request fingerprint.
4. **Group results**: one JSON per logical request group, enabling checkpoint resume.
5. **Fact normalizer**: converts heterogeneous records to a long-table research schema.
6. **Storage**: Parquet plus DuckDB indexes for fast search and calculation.
7. **Export**: human-readable Excel and full audit JSON.
8. **Calculation**: TTM, YoY, QoQ, average, CAGR and safe custom formulas.
9. **Delivery adapters**: CLI, FastAPI web, GitHub Actions and GitHub Pages static viewer.

## Why the manifest is fixed

The first production version intentionally does not discover new endpoints at runtime. This makes runs reproducible, testable and resistant to accidental scope expansion. Updating the endpoint set is a versioned maintenance operation.

## Request lifecycle

```text
request template
  -> replace stock identities
  -> request fingerprint
  -> cache lookup
  -> retrying HTTP request
  -> JSON/JSONP parser
  -> pagination
  -> record-path extraction
  -> validation
  -> optional precise fallback
  -> group checkpoint
```

## Data semantics

- `flow`: income statement, cash flow and flow indicators; eligible for TTM when additive.
- `point_in_time`: balance sheet, share structure and holdings; not eligible for TTM.
- `event`: announcements, research, governance and market events.
