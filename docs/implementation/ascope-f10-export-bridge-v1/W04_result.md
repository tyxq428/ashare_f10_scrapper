# W04 Result — PASS

## Implementation

Implemented bounded batch execution and recovery with:

- atomic `checkpoint.json` writes;
- at most two concurrent stocks per batch;
- at most two attempts per stock;
- four existing F10 request-group workers per stock;
- heartbeat events while work remains active;
- soft-deadline deferral before starting another stock;
- interrupted in-flight recovery as `FAILED_RETRYABLE`;
- preservation of terminal successes across reruns;
- separate completed, failed and deferred ledgers;
- deterministic batch fingerprint and request-order validation;
- batch-level reduction foundations and conservation checks.

## Failure handling verified

- `FAILED_RETRYABLE` and `DEFERRED_TIME_BUDGET` can be retried without resetting completed securities.
- `FAILED_TERMINAL` and `BLOCKED` remain terminal and cannot be hidden by another successful stock.
- A checkpoint with a changed request fingerprint, batch identity or security order is rejected.
- Existing single-stock cache is attempted before the resilient F10 fetch path.
- Provider throttling and transient connection failures are classified for bounded retry; unlimited retries and IP rotation are not used.

## Verification

The GitHub-hosted bridge-targeted suite completed with Ruff clean and 28 tests passing in run `30538490813`. Batch and reducer tests cover concurrency bounds, checkpoint restoration, retry/defer handling, completed-stock preservation, ledgers, conservation, PIT output and duplicate-key gates.

## Security and cost

- Codex calls: 0;
- Responses paid probes: 0;
- no automatic trading;
- no secret-bearing model execution;
- full-market official PDF validation remains disabled.

## Acceptance

W04 passed. Continue automatically to W05 GitHub Actions batch workflow.
