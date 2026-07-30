# A-SCOPE F10 Export Bridge v1 — Master Plan

## Architecture

```text
A-SCOPE request snapshot
  → package resolver and validation
  → batch selection / smoke subset / resume selection
  → per-stock cache lookup
      → valid cache: export only
      → missing/invalid cache: existing resilient F10 fetch
  → canonical mapping and industry template
  → point-in-time and revision filtering
  → cumulative-to-standalone quarter derivation
  → per-stock checkpoint
  → batch reducer and QA
  → annual/quarterly/status outputs
  → full-market reducer
  → A-SCOPE live-bundle handoff
```

## Work packages

| Stage | Objective | Main deliverables | Exit gate |
|---|---|---|---|
| W00 | Bootstrap task and freeze contract | Issue, branch, Draft PR, canonical state, path scope | repository/task preflight PASS |
| W01 | Resolve and validate request snapshots | resolver, models, fixture, request manifest validation | confirmed package and B001 fixture parse deterministically |
| W02 | Canonical finance semantics | mapping registry, templates, PIT/revision logic, quarter derivation | industrial and financial fixtures PASS |
| W03 | Export a completed single-stock run | cache locator, facts reader, exporter, lineage/status tables | second identical export uses cache and performs no fetch |
| W04 | Run and resume a batch | batch state, heartbeat, bounded concurrency, retry/defer queue | interruption fixture resumes without redoing completed stocks |
| W05 | GitHub Actions batch execution | manually dispatchable and reusable batch workflow | workflow, security and fixture gates PASS |
| W06 | Reduce and validate outputs | batch reducer, field coverage, duplicate and PIT checks | schema, keys, cutoff and conservation PASS |
| W07 | Local/API execution surface | Windows runbook and optional API endpoints | job management regression PASS |
| W08 | A-SCOPE handoff and rollout control | artifact/release resolver, rollout queue, full-market reducer | downstream contract and contamination gates PASS |
| W09 | First real production batch | B001 five-stock smoke, cache rerun, full B001 | smoke and B001 acceptance PASS |
| W10 | Full rollout and closeout | B002–B027, full-market package, final report | exact-main post-merge PASS |

## Failure classification

- `FAILED_RETRYABLE`: transient network/provider condition; eligible for bounded recovery.
- `FAILED_TERMINAL`: deterministic invalid input, unsupported schema or non-recoverable exporter error.
- `DEFERRED_TIME_BUDGET`: job soft deadline reached before a new stock can start.
- `BLOCKED`: security boundary, request-manifest mismatch, unavailable required semantics or irreconcilable source conflict.
- `PASS_WITH_GAPS`: usable output exists and every gap is explicitly classified.

## Output identity and idempotence

Every run records:

- input package SHA256;
- batch row hash;
- cutoff date;
- F10 request manifest hash;
- canonical mapping version;
- export schema version;
- source run fingerprints;
- software commit SHA when available.

A cache hit requires all decision-relevant fingerprints to match.

## Production rollout policy

- B001 first-five smoke is mandatory.
- Smoke must prove point-in-time filtering, financial-template routing, cache reuse and output readability.
- Full B001 starts only after smoke acceptance.
- B002–B027 start only after full B001 acceptance.
- At most two batches run concurrently.
- Completed batches are immutable inputs to the full-market reducer.

## Human actions

Non-blocking platform or optional-runner actions are recorded in `MANUAL_ACTIONS.yaml` and do not stop deterministic implementation. A pause is permitted only when the missing action changes business semantics, exposes a secret boundary or prevents production evidence from being generated.