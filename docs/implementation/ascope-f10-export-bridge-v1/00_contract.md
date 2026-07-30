# A-SCOPE F10 Export Bridge v1 — Task Contract

## Objective

Consume the confirmed A-SCOPE financial request snapshot, reuse existing single-stock F10 results and checkpoints, and export point-in-time annual and quarterly financial tables that A-SCOPE can validate and screen.

## Confirmed production input

- Request package: `ascope-financial-requests-30529291404.zip`
- Request status: `READY`
- Research cutoff: `2026-07-30`
- Standard non-ST universe: `5,331`
- Standard batches: `B001`–`B027`
- First live smoke: first five rows of `B001`

## Execution sequence

1. Implement deterministic request-package parsing and validation.
2. Implement canonical field mapping, industry templates, point-in-time filtering, revision selection and independent-quarter derivation.
3. Reuse valid single-stock run directories and caches before any network fetch.
4. Run B001 five-stock smoke.
5. If smoke passes, run complete B001.
6. If B001 passes, progress B002–B027 with at most two active batches.
7. Reduce all completed batches into a full-market A-SCOPE financial package.

## Fixed execution limits

- Active batches: at most `2`
- Stocks per batch processed concurrently: at most `2`
- Existing F10 request-group workers per stock: `4`
- Maximum attempts per stock: `2`
- Full-market official PDF validation: disabled
- Allowed supplementary lookup: required disclosure-date metadata only
- Codex calls: `0`
- Responses paid probes: `0`
- Automatic trading: disabled

## Required batch outputs

- `financial_annual.csv`
- `financial_quarterly.csv`
- `financial_field_status.csv`
- `batch_manifest.json`
- `completed_securities.csv`
- `failed_securities.csv`
- `deferred_securities.csv`
- `data_gaps.csv`
- `future_available_rows.csv`
- `duplicate_resolution.csv`
- `field_coverage.csv`
- `validation_report.json`
- `checkpoint.json`

## Data semantics

- `available_at` is the actual public availability date; it must never be copied from `report_period` merely to satisfy a schema.
- Values unavailable at the cutoff are excluded from the formal output and recorded separately.
- Numeric zero, `NOT_APPLICABLE`, `NOT_DISCLOSED`, `SOURCE_MISSING`, `CONFLICTING` and `PARSE_SUSPECT` remain distinct states.
- Flow values may be converted from cumulative reports to standalone quarters only through explicit, auditable derivations.
- Point-in-time balance-sheet values are never differenced between quarters.
- Financial institutions use a dedicated template; inapplicable industrial fields remain null with `NOT_APPLICABLE`.

## Cache and recovery contract

- Reuse a completed per-stock output only when its request fingerprint, cutoff, export schema and mapping version match.
- Preserve all successfully completed stocks when another stock or batch fails.
- Retry only `FAILED_RETRYABLE` or `DEFERRED_TIME_BUDGET` records.
- A repeated run with identical valid inputs must avoid new network fetches for cache hits.
- 429 or provider throttling causes bounded backoff followed by host-level circuit breaking; it never causes unbounded retries or IP rotation.

## Path scope

### Allowed

- `src/ashare_f10/ascope_bridge/**`
- `src/ashare_f10/cli.py`
- `src/ashare_f10/api/ascope_batches.py`
- `schemas/ascope_bridge/**`
- `scripts/run_ascope_f10_*.py`
- `scripts/windows/run_ascope_f10_bridge.ps1`
- `.github/workflows/ascope-f10-*.yml`
- `tests/test_ascope_f10_*.py`
- `tests/fixtures/ascope_bridge/**`
- `docs/implementation/ascope-f10-export-bridge-v1/**`
- `docs/implementation/ACTIVE_TASKS.yaml`

### Forbidden without a new reviewed decision

- Existing 113-group F10 request manifest or endpoint definitions
- Codex entrypoints or policy
- Bark transport and notification mechanics
- Existing official-validation semantics
- A-SCOPE scoring, portfolio or position rules

## Completion standard

The task is not complete until exact-main post-merge validation passes and the canonical state, final report and Issue #71 are atomically closed.