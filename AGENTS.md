# Repository Agent Contract

This file is the repository-wide entry point for ChatGPT Web, Codex and other coding agents.

## Required reading order

1. `docs/process/README.md`;
2. `docs/implementation/ACTIVE_TASKS.yaml`;
3. the active task's `task_state.yaml`, `HANDOFF.md` and current `Wxx_plan.md`;
4. the nearest scoped `AGENTS.md` for every file being changed;
5. current branch, PR and GitHub Checks.

## Non-negotiable rules

1. `task_state.yaml` is the canonical task state. Chat history and the Web thinking animation are not state stores.
2. Every work package requires `Wxx_plan.md` before implementation and `Wxx_result.md` after verified completion.
3. Continue automatically after successful, retryable or ordinary intermediate states. Pause only for a real permission/security block, irreversible action, business decision, unclassifiable failure or exhausted recovery budget.
4. Every failure must pass through deterministic classification and bounded recovery before it can create a task-control notification.
5. Retry only failed infrastructure operations with a verified transient classification; preserve successful checkpoints.
6. **Codex is disabled by default.** ChatGPT Web and deterministic GitHub Actions are the normal execution path.
7. A Codex session is allowed only after a task-bound, user-approved, unexpired authorization passes reproduction, failure-file coverage, context, duplicate-fingerprint and usage-budget gates.
8. Never auto-dispatch, auto-retry or synthesize a Codex task from State Consistency, Workflow, Devflow Core, formatting, fixture, security, permission, documentation, business-semantics or source-conflict failures.
9. When explicitly authorized, Codex remains a bounded thin worker: one immutable task generation, 2–5 explicit safe files, one XHigh session, no automatic second session and deterministic acceptance gates.
10. XHigh cost is controlled with a Context Budget: no chat-history injection, no full-SOP injection, bounded file bytes and bounded failure excerpts. Never silently downgrade reasoning effort.
11. A secret-bearing job must be repository read-only. Publication, Product Gate, merge and Post-Merge run without relay secrets.
12. Any changed path outside the declared scope, secret-audit match or manifest mismatch is `SECURITY_BLOCKED` and cannot be retried blindly.
13. Never put relay URLs, hostnames, API keys, model identifiers or transformed secret values in tracked files, logs, issues, PRs or artifacts.
14. Separate platform `execution_status`, domain acceptance and `security_status`; a source conflict is not a program crash.
15. Never infer zero, absence or safety from `NO_MATCH`, missing evidence or an unavailable source.
16. Jobs expected to exceed five minutes need streaming output or a fixed heartbeat and a stale threshold.
17. Mechanical checks belong in scripts and CI, not prose-only instructions.
18. Audit concurrent PR path overlap when a branch is created and immediately before merge.
19. Do not mark a task complete until exact-main Post-Merge and canonical closeout pass.
20. Valuable notifications are limited to `COMPLETED`, `INTERRUPTED`, `HUMAN_REQUIRED` and `SECURITY_BLOCKED`; retries and deterministic repairs are silent.
21. `/ack` only confirms receipt. It never triggers repair, retry, Codex, resume or state changes.

Full policies, runbooks and templates are indexed at `docs/process/README.md`.
