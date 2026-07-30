# W08 Result — A-SCOPE Handoff and Rollout Controller

## Status

`PASS`

## Delivered

- Immutable public Release input for the confirmed A-SCOPE request snapshot.
- Rollout state machine covering mandatory B001 smoke, full B001, B002–B027 and full-market reduction.
- At most two active full batches.
- Resume and reducer contracts that preserve successful sibling batches.
- Fixture, cutoff, request-fingerprint, ST-standard-path and conservation gates.

## Evidence

On implementation head `cabca6affeb5498393a4129218b2d9bba1524538`:

- A-SCOPE F10 Full Rollout contract: run `30547981935` — PASS.
- A-SCOPE F10 Batch Export: run `30547981636` — PASS.
- A-SCOPE F10 Real Smoke: run `30547981782` — PASS.

The production input remains fixed to Release `ascope-financial-requests-2026-07-30-v1` and cutoff `2026-07-30`.

## Exit

W08 is complete. Production evidence proceeds through W09; no fixture output can enter the live reduction path.
