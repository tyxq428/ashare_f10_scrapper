# Handoff

## Resume point

Read `task_state.yaml`, Issue #71, PR #72, `W09_plan.md`, `W09_smoke_result.md` and `W10_plan.md`. The task branch started from main SHA `208c5450455e8fd678b0551b01bcead114a34893`.

## Current work

W00-W08 are complete. W09's PR-head real B001 first-five smoke passed in run `30547981782` with all five securities completed, no future rows, no duplicate-resolution rows, no failures and no deferrals. The remaining W09 gate is exact-main smoke followed by full B001.

The workflows now implement the continuation chain:

```text
PR merge to main
→ exact-main A-SCOPE F10 Real Smoke
→ source-gated A-SCOPE F10 Full Rollout
→ full B001
→ B002-B027, max two active batches
→ full-market reduction
```

## Verified implementation foundations

- immutable production request Release and request-package hashing;
- canonical annual/quarterly mapping with real `available_at` handling;
- industrial and financial-industry templates;
- standalone-quarter derivation and revision/conflict quarantine;
- completed-run reuse and fingerprinted single-stock exports;
- two-stock batch runner, bounded retries, checkpoints and soft-deadline deferral;
- reducer conservation, PIT, duplicate and contamination gates;
- Windows, API, fixture, real-smoke and rollout execution surfaces;
- completed transient raw F10 trees are pruned after compact audit evidence and canonical exports are preserved.

## Fixed decisions

- Input: Release `ascope-financial-requests-2026-07-30-v1` derived from `ascope-financial-requests-30529291404.zip`.
- Cutoff: `2026-07-30`.
- Smoke: first five rows of B001.
- Full rollout: full B001, then B002-B027 with at most two active batches.
- Official PDF validation: disabled for full-market export.
- Disclosure-date metadata lookup: allowed only when required.
- Codex and paid Responses probes: zero.

## Failure recovery

- Do not use a full workflow rerun for a single batch/provider failure.
- Restore the affected batch checkpoint and retry only `FAILED_RETRYABLE` or `DEFERRED_TIME_BUDGET` securities.
- Preserve all successful sibling batch artifacts.
- Treat unknown semantics or provenance conflicts as `BLOCKED`; never guess or write zero.

## Do not do

- Do not alter the existing F10 request-group manifest.
- Do not fill unknown `available_at` with `report_period`.
- Do not convert missing, not-disclosed or not-applicable fields to zero.
- Do not start B002 before exact-main smoke and full B001 acceptance.
- Do not publish fixture or partial output as a full-market production package.
