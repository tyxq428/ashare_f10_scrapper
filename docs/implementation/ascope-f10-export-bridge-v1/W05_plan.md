# W05 Plan — GitHub Actions Batch Workflow

## Goal

Provide a safe, manually dispatchable and reusable GitHub Actions workflow for one batch or smoke subset, with immutable inputs, bounded concurrency, artifacts and resumable failure handling.

## Inputs

- source mode: release asset, workflow artifact, local/self-hosted path or fixture;
- request source identifier;
- `batch_id`;
- `as_of_date`;
- `smoke_count`;
- `resume_run_id`;
- `force_retry`.

Fixed production limits remain two stocks, four request-group workers and two attempts.

## Tasks

1. Add pinned-action workflow `ascope-f10-batch-export.yml`.
2. Resolve and hash the request snapshot.
3. Install the project with dependency caching.
4. Restore only a compatible prior checkpoint/artifact.
5. Run request validation and batch execution.
6. Upload batch outputs even for recoverable partial completion.
7. Expose batch status and resume inputs as workflow outputs.
8. Prevent secrets from entering publication or PR jobs.
9. Add fixture workflow coverage without live provider calls.
10. Ensure one failed batch does not cancel already successful sibling batches.

## Security

- default permissions: `contents: read`;
- no `pull_request_target` execution of untrusted code;
- third-party actions pinned to full commit SHA;
- no Codex, Responses relay or secret-bearing model job;
- request artifact provenance included in the manifest;
- fixture artifacts marked non-investment and cannot enter production reduction.

## Gates

- Workflow syntax and pin validation pass.
- Fixture dispatch emits the complete batch artifact contract.
- Recoverable partial output is uploaded with a resume checkpoint.
- Fixture and live modes cannot be confused.
- Security and state consistency checks pass.

## Exit

W05 passes when the fixture workflow can execute a smoke batch end-to-end and produce a resumable artifact without network F10 calls.