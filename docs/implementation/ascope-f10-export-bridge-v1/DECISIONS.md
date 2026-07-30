# Decisions

## D001 — Build a bridge, not a second F10 collector

The task reuses existing `FetchPipeline`, resilient retry logic, normalized facts and completed run directories. No duplicate endpoint collector is introduced.

## D002 — Point-in-time correctness is a hard gate

A row without a reliable `available_at` cannot enter the formal A-SCOPE output. It is recorded as a data gap. `report_period` is not an allowed substitute.

## D003 — Financial institutions use separate applicability rules

Bank, insurance, securities and other financial companies do not receive fabricated industrial metrics. Inapplicable fields remain null with status `NOT_APPLICABLE`.

## D004 — Full-market official PDF validation remains off

The bridge may supplement disclosure-date metadata, but it does not download and parse every official report PDF. Deep official validation remains reserved for the later shortlist.

## D005 — Batch and network concurrency are bounded

At most two batches and two stocks per batch may run concurrently. Existing per-stock endpoint workers remain four. One stock receives at most two attempts.

## D006 — Cache decisions are fingerprinted

A cache hit requires compatible request, cutoff, mapping and export schema fingerprints. Re-exporting from a compatible completed run is preferred to a new fetch.

## D007 — Rollout is gated

B001 first-five smoke precedes full B001. Full B001 precedes B002–B027. Candidate-count or schedule pressure cannot bypass a failed gate.

## D008 — Codex remains disabled

Implementation and validation use ChatGPT Web, repository code and deterministic GitHub Actions. Codex and paid Responses probes remain zero.