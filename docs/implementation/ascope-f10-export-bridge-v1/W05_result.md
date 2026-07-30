# W05 Result — PASS

## Implementation

Added `.github/workflows/ascope-f10-batch-export.yml` with:

- pull-request fixture execution and manual/reusable entrypoints;
- `contents: read` and `actions: read` default permissions;
- checkout, setup, upload and download actions pinned to full commit SHAs;
- fixture and HTTPS URL request modes;
- strict batch/date/count input validation;
- optional compatible prior-artifact restoration;
- fixed two-stock concurrency and two-attempt limit;
- five-hour soft deadline inside a bounded job timeout;
- output upload before batch exit-code propagation;
- explicit fixture/live contamination validation;
- immutable artifact names including batch and run ID.

## Fixture execution

GitHub Actions run `30538896094` completed successfully and uploaded artifact `ascope-f10-B001-30538896094` with digest:

`sha256:0e2641c12cc60f5a4a5ad64da47e017071ba1a04cba7d0a755f7bc5459520866`

The artifact contains the complete request snapshot, checkpoint, five per-stock exports, reduced financial tables, field coverage, ledgers, validation report and batch manifest.

## Acceptance evidence

- input securities: 5;
- completed: 5;
- failed: 0;
- deferred: 0;
- batch status: `PASS`;
- fixture marker: `true`;
- non-investment marker: `true`;
- resumable checkpoint: present;
- formal artifact uploaded before final result propagation.

## Security and cost

- Codex calls: 0;
- Responses paid probes: 0;
- provider calls in fixture run: 0;
- no `pull_request_target`;
- no write permission in the production batch workflow;
- no automatic trading.

## Acceptance

W05 passed. Continue automatically to W06 batch reduction and QA acceptance.
