# W06 Result — PASS

## Implementation

Completed deterministic batch reduction and quality gates for:

- annual, quarterly and field-status concatenation;
- completed, failed and deferred ledgers;
- explicit empty outputs with stable headers;
- formal-row point-in-time checks;
- annual and quarterly duplicate-key rejection;
- request-security and cutoff reconciliation;
- input-count conservation;
- field coverage by financial template, field and status;
- data-gap, future-row and duplicate-resolution sidecars;
- output SHA256 manifest and versioned validation report.

## Fixture artifact verification

Downloaded and inspected artifact `ascope-f10-B001-30538896094` from run `30538896094`.

Validation report:

- status: `PASS`;
- input count: 5;
- successful count: 5;
- failed count: 0;
- deferred count: 0;
- annual rows: 5;
- quarterly rows: 5;
- field-status rows: 10;
- data-gap rows: 0;
- future rows: 0;
- duplicate-resolution rows: 0;
- conservation: PASS;
- formal future rows: 0;
- errors: none.

Batch manifest records SHA256 for every required output and preserves `fixture_mode=true` plus `non_investment_output=true`.

## Failure-closed coverage

The reducer test suite verifies explicit rejection of unknown securities, changed request identity, duplicate keys, future formal rows, nonterminal checkpoint states and missing per-stock outputs. Missing, conflicting and not-applicable data remain sidecar states rather than numeric zero.

## Security and cost

- Codex calls: 0;
- Responses paid probes: 0;
- full-market official PDF validation: disabled;
- no provider request is needed for reduction.

## Acceptance

W06 passed. Continue automatically to W07 local operator and Windows runbook surface.
