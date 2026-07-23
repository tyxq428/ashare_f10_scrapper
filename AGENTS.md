# Repository agent instructions

Read these files before starting or resuming a non-trivial repository task:

1. `docs/process/README.md`;
2. `docs/implementation/ACTIVE_TASKS.yaml`;
3. the active task's `task_state.yaml`, `HANDOFF.md`, and current `Wxx_plan.md`;
4. the latest branch head, pull request, and GitHub Checks.

Mandatory rules:

- The repository is the durable source of truth; chat history is secondary.
- Use one active branch, one pull request, and one canonical `task_state.yaml` per task.
- Commit `Wxx_plan.md` before implementation and `Wxx_result.md` after verified completion.
- Do not pause after normal progress, warnings, cache hits, or recoverable failures.
- Pause only for a real error that cannot be safely repaired, missing permission or private data, irreversible risk, security block, or a business decision.
- Long-running commands must stream output or emit heartbeats and preserve checkpoints.
- Classify failures before retrying; retry only the failed scope and never repeat a non-retryable failure blindly.
- Keep `execution_status` separate from research or product `acceptance_status`.
- Never interpret missing or `NO_MATCH` data as zero or non-existence.
- Record reusable execution failures and prevention rules in `docs/ENGINEERING_ISSUES_AND_LESSONS.md`.
- Audit parallel pull requests when a branch is created and immediately before merge.
- Important changes require independent post-merge verification before being marked 100% complete.
- Never place relay endpoints, hostnames, API keys, model identifiers, credentials, or transformed secret values in tracked files, logs, artifacts, issues, or pull requests.
- Codex is a thin worker: it receives a bounded task, allowed paths, a trusted gate profile, and one session. It does not redesign the project or start the next stage.
- A secret-bearing Codex job must be repository-read-only. A separate secret-free job may apply a verified patch and push a work branch.
- Any out-of-scope edit, secret-audit failure, or untrusted trigger is `SECURITY_BLOCKED`.
- Only `COMPLETED`, `INTERRUPTED`, `HUMAN_REQUIRED`, and `SECURITY_BLOCKED` produce user-facing task notifications.

More specific `AGENTS.md` files apply to their directory subtree and take precedence when they do not weaken these controls.
