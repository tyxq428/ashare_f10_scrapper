# Codex one-time approvals

The repository default is `.devflow/codex-policy.yaml` with `mode: disabled`.

An approval file may be added only after the user explicitly authorizes one concrete task in ChatGPT Web. It must be JSON, named `<approval-id>.json`, and contain:

```json
{
  "schema_version": 1,
  "approval_id": "codex-approval-task-id",
  "task_id": "task-id",
  "approved_by": "tyxq428",
  "approval_source": "chatgpt_web",
  "descriptor_sha256": "sha256:...",
  "failure_fingerprint": "...",
  "max_calls": 1,
  "issued_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "expires_at_utc": "YYYY-MM-DDTHH:MM:SSZ"
}
```

The approval is invalid when the descriptor changes, the fingerprint changes, the expiry passes, the user differs, or the usage ledger already contains the task/fingerprint. Creating an approval does not itself dispatch a model call. `github-actions[bot]` is never an approved actor.
