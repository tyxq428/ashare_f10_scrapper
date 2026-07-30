# W09 Plan — First Real Production Batch

## Goal

Prove the bridge against the immutable production request package before allowing the 5,331-security rollout.

## Inputs

- Release asset: `ascope-financial-requests-2026-07-30-v1.zip`.
- Cutoff: `2026-07-30`.
- Batch: `B001`.
- Mandatory smoke subset: first five securities.

## Sequence

1. Run the five-security real smoke on the PR head.
2. Require all five securities to reach a completed state.
3. Require positive annual, quarterly and field-status output counts.
4. Require zero future rows, duplicate-resolution rows, failed rows and deferred rows.
5. Permit `PASS_WITH_GAPS` only when every missing/not-applicable field is explicitly classified and no value is converted to zero.
6. Re-run the smoke on exact `main` after merge.
7. Start full B001 automatically only after the exact-main smoke succeeds.
8. Preserve compact fetch reports and canonical exports; remove completed transient raw trees to stay inside hosted-runner disk limits.
9. If full B001 fails, restore its checkpoint and retry only failed/deferred securities.

## Acceptance

- Production request source and cutoff match the confirmed contract.
- Fixture and non-investment markers are absent.
- Input count: 5 for smoke, 200 for full B001.
- Conservation: every requested security has exactly one terminal state.
- Future rows: 0.
- Duplicate-resolution rows: 0 for the smoke; any later duplicate must have an explicit resolution record.
- Successful stocks are not fetched again after unrelated failures.

## Exit

W09 passes after exact-main smoke and full B001 both satisfy production acceptance. W10 then starts B002–B027 with at most two batches active.
