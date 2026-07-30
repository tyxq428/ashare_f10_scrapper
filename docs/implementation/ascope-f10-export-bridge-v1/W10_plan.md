# W10 Plan — Full Rollout and Closeout

## Goal

Complete B002–B027 after full B001 acceptance, reduce all 27 immutable batch outputs and close the task on exact `main`.

## Production sequence

1. Exact-main smoke succeeds.
2. Full B001 runs and passes.
3. B002–B027 start automatically with `max-parallel: 2`.
4. Each batch preserves completed securities and exposes retryable/deferred ledgers.
5. Failed/deferred batches resume from their latest compatible checkpoint; successful batches remain immutable.
6. The reducer downloads the 27 full-batch artifacts from the same rollout run.
7. The reducer reconciles exactly 5,331 standard-path securities.
8. The final package contains annual, quarterly, field-status, batch-index, failed/deferred, gap and validation outputs.
9. Fixture, cutoff, request-fingerprint and ST-standard-path contamination are rejected.
10. A closeout change records W09/W10 evidence, transitions canonical state to `DONE / COMPLETED / PASS`, merges and verifies exact-main Post-Merge gates.

## Failure handling

- Transient provider or infrastructure failures: bounded recovery from the affected batch checkpoint only.
- Hosted-runner soft deadline: stop accepting new stocks, upload the checkpoint and mark the remaining stocks `DEFERRED_TIME_BUDGET`.
- Semantic or provenance conflict: `BLOCKED`; do not guess or fill zero.
- Sibling batch failure: do not replay successful batches.

## Acceptance

- Batch count: 27.
- Expected standard-path securities: 5,331.
- Every requested security has one final state.
- Full-market future rows: 0.
- No fixture/non-investment marker.
- No ST/*ST security in the standard path.
- Codex calls: 0.
- Responses paid probes: 0.
- Exact-main product, state, security, E2E and Post-Merge gates pass.

## Exit

W10 passes only after the validated full-market artifact and atomic canonical closeout are recorded on `main`.
