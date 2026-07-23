# Repository Agent Contract

This file is the repository-wide entry point for ChatGPT Web, Codex and other coding agents.

## Required reading order

1. `docs/process/README.md`;
2. `docs/implementation/ACTIVE_TASKS.yaml`;
3. the active task's `task_state.yaml`, `HANDOFF.md` and current `Wxx_plan.md`;
4. the nearest scoped `AGENTS.md` for every file being changed;
5. current branch, PR and GitHub Checks.

## Non-negotiable rules

1. `task_state.yaml` is the canonical task state. Chat history is not a state store.
2. Every work package requires `Wxx_plan.md` before implementation and `Wxx_result.md` after verified completion.
3. Continue automatically after successful, retryable or ordinary intermediate states. Pause only for a real error, permission/security block, irreversible action or business decision.
4. Separate `execution_status` from `research_acceptance_status`; a source conflict is not a program crash.
5. Jobs expected to exceed five minutes need streaming output or a fixed heartbeat and a stale threshold.
6. Retry only classified transient failures, with finite attempts, while preserving successful checkpoints.
7. Never infer zero, absence or safety from `NO_MATCH`, missing evidence or an unavailable source.
8. Never put relay URLs, hostnames, API keys, model identifiers or transformed secret values in tracked files, logs, issues, PRs or artifacts.
9. Codex is a bounded thin worker: one task, explicit allowed paths, one session, `low` effort, deterministic gates, no automatic second session.
10. A secret-bearing Codex job must be repository read-only. Publication occurs in a separate job that receives no relay secrets.
11. Any changed path outside the declared scope, secret-audit match or manifest mismatch is `SECURITY_BLOCKED`.
12. Mechanical checks belong in scripts and CI, not prose-only instructions.
13. Audit concurrent PR path overlap when a branch is created and again immediately before merge.
14. Do not mark a task complete until independent post-merge verification passes.
15. Valuable notifications are limited to `COMPLETED`, `INTERRUPTED`, `HUMAN_REQUIRED` and `SECURITY_BLOCKED`.

Full policies, runbooks and templates are indexed at `docs/process/README.md`.
