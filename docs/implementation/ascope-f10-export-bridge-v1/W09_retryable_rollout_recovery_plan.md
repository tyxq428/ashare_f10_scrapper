# W09 retryable rollout recovery plan

## Source execution

Exact source rollout:

- workflow: `A-SCOPE F10 Recover B001 and Continue Rollout`;
- run: `30782791016`;
- branch: `main`;
- head SHA: `a47c6ba5eb5a89a8bbdbf2e0ee58cf247b61b4c3`;
- recovered B001: PASS, 200/200;
- B002: PASS;
- B003: FAILED_RECOVERABLE;
- B004-B027: allowed to continue under `fail-fast: false` and `max-parallel: 2`.

The active source run must not be cancelled, broadly rerun or replaced by a parallel rollout. Its successful jobs and immutable batch artifacts remain the canonical source for final reduction.

## B003 diagnosis

Artifact `ascope-f10-B003-s0-30782791016` contains:

- input securities: 200;
- successful: 173;
- retryable failures: 27;
- terminal failures: 0;
- deferred: 0;
- security conservation: PASS;
- formal future rows: 0.

Every failed security has exactly one failed request group:

```text
group_id = ef08aa02d7e84c00
family = /api/qt/stock/get
strategy = union_quote_fields
record_count = 0
attempt 1 = HTTP 502
attempt 2 = HTTP 502
attempt 3 = HTTP 502
```

The failure is an upstream quote-endpoint outage. It does not affect the finance mapping, point-in-time cutoff, source identity, schema, security conservation or XLSX sanitizer.

## Recovery-semantic defect

A restored `FAILED_RETRYABLE` state remains in the resumable set, but its `attempt_count` may already equal the bounded `max_attempts`. In that case a simple job rerun restores the checkpoint but enters an empty attempt range and performs no real network retry.

Therefore an authorized recovery must reset all of the following together:

- status to `PENDING`;
- `attempt_count` to zero;
- start/completion timestamps;
- prior error fields;
- retry flag;

and must append the complete prior state to `recovery_history`.

## Automatic post-rollout chain

The new workflow runs only after the exact source rollout completes:

1. verify source run ID, workflow name, event, branch and head SHA;
2. require recovered B001 to have succeeded;
3. enumerate B002-B027 job outcomes;
4. require a durable artifact for all 27 batches;
5. create a recovery matrix containing only failed batch jobs;
6. for every failed batch, verify that all failures are retryable and exclusively the authorized quote HTTP-502 group;
7. reset only the exact retryable securities with audit history;
8. resume those securities from their per-stock request-group checkpoints;
9. require each corrected batch to reach 200/200, with zero failures, zero deferred securities and zero formal future rows;
10. preserve every successful source batch artifact;
11. overlay only corrected failed-batch directories;
12. reduce all B001-B027 outputs and reconcile all 5,331 standard-path securities;
13. upload the final full-market artifact and persist the result to Task Control Issue #71.

## Rejection boundary

Automatic recovery stops rather than broadening scope when any failed batch contains:

- `FAILED_TERMINAL` or `BLOCKED`;
- deferred securities;
- a request group other than `ef08aa02d7e84c00`;
- an error other than HTTP 502 attempts;
- missing or changed request/package identity;
- formal future rows;
- security-conservation failure.

## User action after interruption

No complete-rollout rerun is allowed.

- Confirmed transient failure in a recovery job: rerun only that failed recovery job.
- Different deterministic root cause: fix only that root cause, reset only the affected securities, and preserve all successful artifacts.
- Final reducer failure after all batches pass: rerun only the reducer after diagnosing its explicit conservation/schema/PIT error.

No Gmail connection, Codex call, paid probe, broad rerun, ST/*ST standard-path inclusion or automatic trading is used.
