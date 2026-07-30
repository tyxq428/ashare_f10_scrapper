# W04 Plan — Resumable Batch Runner

## Goal

Execute a selected A-SCOPE batch with bounded stock concurrency, existing F10 fetch recovery, per-stock checkpoints and no loss or replay of already completed securities.

## Tasks

1. Define stock and batch status machines.
2. Persist `checkpoint.json` atomically after each state transition.
3. Load a previous checkpoint or artifact and verify the input fingerprint.
4. For each requested security:
   - reuse a compatible completed export;
   - otherwise reuse a valid current F10 run;
   - otherwise call the existing resilient single-stock fetch;
   - export and validate the result.
5. Process at most two stocks concurrently.
6. Give each stock at most two total attempts.
7. Stop claiming new work at the soft deadline and mark remaining rows `DEFERRED_TIME_BUDGET`.
8. Apply host-level throttling circuit breakers to new fetches after repeated 429/provider throttling.
9. Stream heartbeat and progress output at least every 30 seconds.
10. Write completed, failed and deferred security ledgers.

## Statuses

Stock:

- `PENDING`
- `CACHE_HIT`
- `FETCHING`
- `FETCH_COMPLETED`
- `EXPORTING`
- `COMPLETED`
- `COMPLETED_WITH_GAPS`
- `FAILED_RETRYABLE`
- `FAILED_TERMINAL`
- `DEFERRED_TIME_BUDGET`

Batch:

- `RUNNING`
- `PASS`
- `PASS_WITH_GAPS`
- `FAILED_RECOVERABLE`
- `BLOCKED`
- `FAILED_TERMINAL`

## Gates

- Simulated interruption resumes from checkpoint.
- Completed securities are not fetched or exported again.
- Only retryable/deferred rows enter a recovery run.
- Maximum active stock workers is two.
- Maximum attempts is two.
- Mismatched checkpoint fingerprints fail closed.
- Batch manifest reconciles every input row to exactly one terminal or resumable status.

## Exit

W04 passes when a mixed success/retry/defer fixture resumes correctly and preserves all successful checkpoints.