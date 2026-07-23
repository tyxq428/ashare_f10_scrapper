# GitHub Actions Scoped Rules

These rules apply to `.github/**` and extend the root `AGENTS.md`.

- New third-party actions must be pinned to a full immutable commit SHA.
- Do not use `pull_request_target` to execute or inspect untrusted PR code.
- Do not accept arbitrary shell commands through workflow inputs, issue text or comments.
- Use trusted gate-profile identifiers mapped to repository-owned commands.
- Secret values and private endpoints belong in GitHub Environment Secrets, never Variables or YAML literals.
- The Codex job declares `environment: agent-runtime`, `contents: read`, a localhost Responses endpoint and `safety-strategy: drop-sudo`.
- A separate publication job may use `contents: write` but must not reference the environment or relay secrets.
- Upload artifacts through explicit allowlists. Never upload `$HOME`, the whole workspace, environment snapshots or raw HTTP logs.
- Long-running commands require unbuffered output, heartbeats and timeouts.
- Successful intermediate gates, retries and audits are silent. Notify only valuable terminal or human-required states.
- Workflows that can change the repository must be idempotent and protected by task-specific concurrency groups.
