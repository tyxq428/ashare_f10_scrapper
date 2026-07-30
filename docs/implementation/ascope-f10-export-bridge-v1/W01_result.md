# W01 Result — PASS

## Implementation

Added a fail-closed A-SCOPE request package resolver under `ashare_f10.ascope_bridge`.

Supported inputs:

- ZIP archive;
- extracted directory;
- deterministic batch selection;
- optional first-N smoke selection;
- output snapshots and SHA256 fingerprints.

## Validation coverage

The resolver validates before any F10 fetch can start:

- exactly one request manifest;
- `READY` status;
- ISO cutoff and exact requested cutoff match;
- continuous `B001...Bxxx` batch IDs;
- manifest row and batch counts;
- required columns;
- exchange/code/security-ID consistency;
- standard-path ST/*ST exclusion;
- duplicate securities;
- required `available_at` contract;
- valid request states and date ranges.

## Verification

Local deterministic fixture:

- tests: `8 passed`;
- ZIP and directory inputs yielded identical selected rows;
- invalid status, cutoff, identity, ST, duplicate and count fixtures all failed closed.

Confirmed production snapshot validation:

- package: `ascope-financial-requests-30529291404.zip`;
- package SHA256: `8e5ed52ba310d05b0ee80a7d967cc2246577a5815d5b5edaad72483f3239dc77`;
- standard requests: `5,331`;
- batches: `27`;
- B001 source rows: `200`;
- B001 smoke rows: `5`;
- first/last smoke securities: `SZSE.000001` / `SZSE.000008`.

GitHub-hosted gates on commit `ce59d52b825b575df90d8cdb49fde74604437c8f`:

- Test run `30533509527`: PASS;
- State Consistency run `30533509501`: PASS;
- E2E 688521 run `30533509514`: PASS.

The earlier State Consistency failure was deterministically classified as an invalid null `last_product_commit_sha`, repaired once, and not blindly retried.

## Security

- network requests from the resolver: 0;
- Secret reads: 0;
- Codex calls: 0;
- Responses paid probes: 0.

## Acceptance

W01 passed. Continue automatically to W02 canonical financial mapping and point-in-time semantics.