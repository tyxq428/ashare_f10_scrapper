# W08 Plan — A-SCOPE Handoff and Rollout Controller

## Goal

Connect the bridge to a durable A-SCOPE request source, coordinate the gated B001-to-B027 rollout and reduce completed batches into one validated full-market financial package.

## Tasks

1. Resolve request snapshots from:
   - GitHub Release asset;
   - compatible workflow artifact;
   - local/self-hosted path;
   - fixture.
2. Validate source repository, run/release identity, status and SHA256.
3. Create a rollout state with B001 smoke, B001 full and B002–B027 phases.
4. Enforce at most two active full batches.
5. Start full B001 only after smoke acceptance.
6. Start B002–B027 only after full B001 acceptance.
7. Resume failed or deferred batches without replaying successful ones.
8. Download completed batch artifacts and verify their fingerprints.
9. Reduce annual, quarterly and field-status tables across all batches.
10. Reconcile all 5,331 standard request securities.
11. Emit a full-market validation report and A-SCOPE-ready bundle manifest.
12. Refuse fixture, mismatched-cutoff, ST-standard-path or unverified batch contamination.

## Rollout states

- `WAITING_FOR_INPUT`
- `B001_SMOKE_READY`
- `B001_SMOKE_RUNNING`
- `B001_SMOKE_PASS`
- `B001_FULL_RUNNING`
- `B001_FULL_PASS`
- `FULL_ROLLOUT_RUNNING`
- `FULL_ROLLOUT_PARTIAL`
- `FULL_REDUCTION_READY`
- `COMPLETED`
- `BLOCKED`

## Gates

- Request source provenance is immutable and recorded.
- Smoke/full transitions cannot be bypassed.
- Active batch count never exceeds two.
- Successful batches are not restarted after a sibling failure.
- Full reducer input count equals 27 expected batches.
- Full-market security ledgers reconcile exactly to 5,331 requested securities.
- Output is compatible with A-SCOPE live-bundle preparation.

## Exit

W08 passes when a fixture rollout proves all phase transitions, bounded parallelism, resumability, contamination rejection and full-market reduction contracts. Production execution then moves to W09.