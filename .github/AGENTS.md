# GitHub Actions instructions

- Use least-privilege job permissions; do not rely only on workflow-level defaults.
- Do not use `pull_request_target` to check out or execute untrusted pull-request code.
- Secret-bearing jobs must not have `contents: write`, `pull-requests: write`, or issue-write permissions.
- Write-capable jobs must not reference the `agent-runtime` Environment or relay Secrets.
- The real relay endpoint must be consumed only by a localhost, no-log forwarder; Codex receives a localhost Responses URL.
- Register masks for the endpoint, hostname, key, model identifier, URL-encoded variants, and Base64 variants before network calls.
- Never print environment variables, authentication headers, raw upstream errors, or private forwarder configuration.
- Upload artifacts by explicit allowlist. Never upload `$HOME`, the entire workspace, `.codex`, environment snapshots, or raw HTTP logs.
- Pin third-party actions to full commit SHAs in production workflows.
- Workflow inputs select a trusted task file and gate profile; they must never become arbitrary shell commands.
- Successful audits and intermediate gates are silent. Notify only valuable task terminal states.
- A reusable workflow must preserve or reduce caller permissions and must declare `environment: agent-runtime` directly on the secret-bearing job.
