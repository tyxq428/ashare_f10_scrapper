# Handoff

## Resume point

Read `task_state.yaml`, Issue #71 and the current `Wxx_plan.md`. The branch was created from main SHA `208c5450455e8fd678b0551b01bcead114a34893`.

## Current work

W00 is establishing canonical task state, path scope and a Draft PR. The next product work is W01: parse and validate the confirmed A-SCOPE request package and B001 smoke subset without issuing any F10 network request.

## Fixed decisions

- Input snapshot: `ascope-financial-requests-30529291404.zip`
- Cutoff: `2026-07-30`
- Smoke: first five rows of B001
- Full rollout: B001, then B002–B027 at maximum two active batches
- Official PDF validation: disabled for full-market export
- Disclosure-date metadata lookup: allowed only when required
- Codex: disabled, zero calls

## Do not do

- Do not alter the existing F10 request-group manifest.
- Do not fill an unknown `available_at` with `report_period`.
- Do not convert missing or inapplicable fields to zero.
- Do not rerun completed securities after an unrelated failure.
- Do not start B002 before B001 acceptance.
