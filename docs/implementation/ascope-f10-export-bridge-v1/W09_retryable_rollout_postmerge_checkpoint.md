# W09 retryable rollout post-merge checkpoint

## Canonical execution

- source workflow: `A-SCOPE F10 Recover B001 and Continue Rollout`;
- canonical source run: `30782791016`;
- source head: `a47c6ba5eb5a89a8bbdbf2e0ee58cf247b61b4c3`;
- source branch/event: `main / push`;
- source run remains active and is not cancelled or broadly rerun.

Current observed progress:

- B001 recovered and accepted: 200/200;
- B002: PASS;
- B003: FAILED_RECOVERABLE with 173 successes and 27 retryable failures;
- B004 and B005: in progress at the checkpoint;
- remaining matrix jobs continue under `fail-fast: false` and `max-parallel: 2`.

## Retryable recovery implementation

PR #74 was squash-merged as:

```text
efce99f80448fe7f4e1521120880a0067d790b2b
```

The merged finalizer:

1. accepts only the exact canonical source Run `30782791016` and source SHA;
2. waits for all source matrix jobs to reach a terminal result;
3. identifies failed batch jobs dynamically;
4. verifies every failed security is `FAILED_RETRYABLE` and every failed request group is the authorized quote-endpoint HTTP-502 boundary;
5. resets only those securities, including consumed attempt budget, with `recovery_history`;
6. preserves all successful securities and successful source batch artifacts;
7. overlays only corrected batch artifacts;
8. performs the 27-batch / 5,331-security full-market reduction.

## Duplicate guard

Merging the recovery implementation matched the earlier B001 recovery workflow's push paths and created duplicate Run `30794078905`.

A one-shot exact-SHA guard cancelled only that duplicate and preserved canonical Run `30782791016`. The duplicate completion also emitted finalizer Run `30794178188`; its exact source gate rejected the event before any data mutation.

The rejected duplicate event does not represent an interruption of the canonical source run.

## User action

No user action is required while Run `30782791016` remains active.

Do not:

- rerun the entire source workflow;
- rerun successful source batches;
- start another B001 or B003 chain;
- treat the rejected duplicate finalizer event as the canonical finalizer.

After the canonical source run completes, observe the new `A-SCOPE F10 Recover Retryable Batches and Finalize` run. A successful chain ends with the artifact:

```text
ascope-f10-full-market-<finalizer-run-id>
```

An interrupted chain writes its bounded recovery instruction to Task Control Issue #71. No Gmail or other external email connection is required.

Codex calls, paid probes and automatic trading remain disabled.
