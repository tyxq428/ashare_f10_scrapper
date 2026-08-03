# W09 retryable rollout recovery plan

## Source checkpoint

The exact production source is rollout Run `30782791016` on `main` SHA
`a47c6ba5eb5a89a8bbdbf2e0ee58cf247b61b4c3`.

At the first recovery checkpoint:

- corrected B001: PASS, 200/200;
- B002: PASS;
- B003: FAILED_RECOVERABLE, with 173 successful and 27 retryable securities;
- B004-B027: allowed to continue under `fail-fast: false` and `max-parallel=2`;
- full-market reduction remains blocked until every batch is successful.

## Verified B003 root cause

Every B003 retryable security failed only the same request group:

```text
group_id: ef08aa02d7e84c00
family: /api/qt/stock/get
strategy: union_quote_fields
HTTP status: 502 on all bounded attempts
```

There are no terminal failures, deferred securities, future formal rows, schema
violations or security-conservation failures in the B003 checkpoint.

A checkpoint restored with `attempt_count=2` cannot perform another attempt when
`max_attempts=2` unless the retryable state is explicitly reset. A broad workflow
rerun is therefore both wasteful and ineffective.

## Recovery design

1. Preserve the active Run `30782791016`; do not cancel or rerun it.
2. After that run completes, download all B001-B027 durable artifacts.
3. Classify every non-success state fail-closed.
4. Automatically authorize only `FAILED_RETRYABLE` states with:
   - `error_code=F10_FETCH_FAILED`;
   - exact group ID, family and strategy shown above;
   - observed HTTP code set exactly `{502}`.
5. Reject terminal failures, unsupported states, missing batches, failed
   conservation, future rows or any different upstream root cause.
6. Reset only verified retryable securities to `PENDING`, set `attempt_count=0`,
   and append the prior state and HTTP evidence to `recovery_history`.
7. Preserve every successful security and retry at most two affected batches in
   parallel.
8. Overlay only corrected batch directories over the immutable source artifacts.
9. Require all 27 batches to be reduction-ready before reducing the full market.
10. Require 27 batches and 5,331 completed securities, with no fixture or
    non-investment markers, before publishing the final financial package.

## Safety boundaries

- no broad batch rerun;
- no rerun of successful securities;
- no cancellation of the active rollout;
- no raw-value mutation;
- no missing-to-zero conversion;
- no ST/*ST standard-path inclusion;
- no Gmail dependency;
- Codex calls remain zero;
- paid probes remain zero;
- automatic trading remains disabled.
