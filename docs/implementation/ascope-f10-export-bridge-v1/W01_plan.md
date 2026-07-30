# W01 Plan — Request Package Resolver and Validation

## Goal

Provide a deterministic, network-free resolver for A-SCOPE financial request snapshots and prove that the confirmed package contract and B001 smoke selection are valid before any F10 fetch can start.

## Inputs

Production contract:

- ZIP name: `ascope-financial-requests-30529291404.zip`
- `status = READY`
- `through = 2026-07-30`
- `standard_request_count = 5331`
- `batch_count = 27`
- first batch `B001`
- first smoke subset: first five valid non-ST rows

CI uses a minimized fixture with the same schema and no live data.

## Tasks

1. Add `ashare_f10.ascope_bridge` package and immutable request models.
2. Support a ZIP or extracted-directory input.
3. Locate exactly one root request manifest and one requested batch file.
4. Validate required manifest fields and the `READY` status.
5. Validate batch IDs, counts, row schema, date ordering and request cutoff.
6. Validate `security_id`, exchange and six-digit code consistency.
7. Reject duplicate securities and ST/*ST rows in the standard path.
8. Compute package, manifest and selected-batch SHA256 fingerprints.
9. Implement deterministic `smoke_count` selection without changing row order.
10. Write a resolved request snapshot and validation report.
11. Add fixture tests for valid input and every fail-closed condition.

## Outputs

- `resolved_request.json`
- `request_snapshot.csv`
- `request_validation.json`
- package API reusable by later batch execution
- W01 fixture and regression tests

## Required validation errors

- `REQUEST_MANIFEST_NOT_FOUND`
- `REQUEST_MANIFEST_AMBIGUOUS`
- `REQUEST_STATUS_NOT_READY`
- `REQUEST_CUTOFF_MISMATCH`
- `REQUEST_BATCH_NOT_FOUND`
- `REQUEST_ROW_SCHEMA_INVALID`
- `REQUEST_SECURITY_ID_INVALID`
- `REQUEST_EXCHANGE_MISMATCH`
- `REQUEST_DUPLICATE_SECURITY`
- `REQUEST_ST_STANDARD_PATH`
- `REQUEST_COUNT_MISMATCH`

## Gates

- Fixture valid package parses identically on repeated runs.
- First five B001 rows remain in source order.
- Every invalid fixture fails before a network/client object is created.
- Input ZIP and selected batch hashes are written to the output.
- Ruff, compile and bridge tests pass.

## Failure and recovery

Deterministic schema or identity errors are terminal for that request package. Filesystem and artifact-download errors may be retried at the infrastructure layer without regenerating an already verified snapshot.

## Exit

W01 passes when the confirmed request contract can be represented by the fixture, B001 five-row selection is deterministic, and all fail-closed tests pass.