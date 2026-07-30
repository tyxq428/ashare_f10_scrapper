# Handoff

## Resume point

Read `task_state.yaml`, Issue #71, PR #72 and the current `Wxx_plan.md`. The branch was created from main SHA `208c5450455e8fd678b0551b01bcead114a34893`.

## Current work

W00-W04 are complete. W05 has a pinned, read-only GitHub Actions batch workflow whose pull-request fixture run `30538896094` completed successfully and uploaded the resumable batch artifact. Resume by completing W05 acceptance documentation, then formalize W06 reducer acceptance and add the W07 local Windows/operator surface.

## Implemented foundations

- request-package parsing and immutable package/batch hashes;
- canonical annual/quarterly mapping with point-in-time `available_at` handling;
- industrial and financial-industry templates;
- standalone-quarter derivation and revision/conflict quarantine;
- completed single-stock run reuse and fingerprinted exports;
- two-stock batch runner, bounded retries, checkpoints and soft-deadline deferral;
- batch reducer, conservation/PIT/duplicate gates and output manifests;
- PR-safe fixture batch workflow with immutable artifact upload.

## Fixed decisions

- Input snapshot: `ascope-financial-requests-30529291404.zip`
- Cutoff: `2026-07-30`
- Smoke: first five rows of B001
- Full rollout: B001, then B002-B027 at maximum two active batches
- Official PDF validation: disabled for full-market export
- Disclosure-date metadata lookup: allowed only when required
- Codex: disabled, zero calls

## Remaining production boundary

The confirmed ZIP currently exists outside GitHub Actions. W08 must establish a durable release/artifact handoff before the real B001 smoke can run. This is a data-transport boundary, not a blocker for W05-W07 deterministic implementation and fixture validation.

## Do not do

- Do not alter the existing F10 request-group manifest.
- Do not fill an unknown `available_at` with `report_period`.
- Do not convert missing or inapplicable fields to zero.
- Do not rerun completed securities after an unrelated failure.
- Do not start B002 before B001 acceptance.
