# One-time Codex Grants

The repository remains `mode: disabled`. A Grant file may exist only inside an independently reviewed, task-specific Activation PR after explicit user authorization.

Required shape:

```json
{
  "schema_version": 1,
  "grant_id": "grant-task-id",
  "task_id": "task-id",
  "approved_by": "tyxq428",
  "approval_source": "chatgpt_web",
  "descriptor_sha256": "sha256:<64 hex>",
  "task_commit_sha": "<40 hex>",
  "source_run_id": 123,
  "source_commit_sha": "<40 hex>",
  "failure_fingerprint": "...",
  "allowed_files_hash": "sha256:<64 hex>",
  "max_calls": 1,
  "state": "ISSUED",
  "issued_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "expires_at_utc": "YYYY-MM-DDTHH:MM:SSZ"
}
```

Rules:

- TTL must not exceed 60 minutes;
- the Activation workflow must reserve the Grant before any Secret or model step;
- `RESERVED` and `CONSUMED` are terminal for model-start eligibility;
- task, fingerprint and Grant may each appear only once in the usage ledger;
- cancellation, timeout, transport failure and Artifact failure still consume the Grant;
- `github-actions[bot]` cannot receive or use a Grant;
- a Grant never dispatches a model by itself.
