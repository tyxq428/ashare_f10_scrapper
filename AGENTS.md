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
4. Every failure must pass through deterministic classification and bounded auto recovery before it can create a task-control notification.
5. Retry only the failed Job, step or request group for classified transient failures; preserve successful checkpoints.
6. Codex is a bounded thin worker: one task generation, explicit allowed paths, one session, **XHigh** effort, deterministic gates and no automatic second session.
7. XHigh cost is controlled with a deterministic Context Budget: no chat-history injection, no full-SOP injection, bounded allowed files/bytes and bounded log excerpts. Never silently downgrade reasoning effort.
8. A Full or Post-Merge Gate may create at most one new Codex Recovery Generation, inheriting the original scope and security policy.
9. A secret-bearing Codex job must be repository read-only. Publication, Product Gate, automatic merge and Post-Merge run without relay secrets.
10. Only an explicitly approved `risk_class=low` task with at most five safe files and passing Scope, Secret, Targeted, Full and Post-Merge Gates may auto-merge.
11. Any changed path outside the declared scope, secret-audit match or manifest mismatch is `SECURITY_BLOCKED` and cannot be retried blindly.
12. Never put relay URLs, hostnames, API keys, model identifiers or transformed secret values in tracked files, logs, issues, PRs or artifacts.
13. Separate platform `execution_status` from domain acceptance status; a source conflict is not a program crash. Legacy `research_acceptance_status` is a compatibility field, not a Core lifecycle concept.
14. Never infer zero, absence or safety from `NO_MATCH`, missing evidence or an unavailable source.
15. Jobs expected to exceed five minutes need streaming output or a fixed heartbeat and a stale threshold.
16. Mechanical checks belong in scripts and CI, not prose-only instructions.
17. Audit concurrent PR path overlap when a branch is created and again immediately before merge.
18. Do not mark a task complete until exact-main Post-Merge and canonical closeout pass.
19. Valuable notifications are limited to `COMPLETED`, `INTERRUPTED`, `HUMAN_REQUIRED` and `SECURITY_BLOCKED`; retries and automatic repairs are silent.
20. `/ack` only confirms receipt. It never triggers repair, retry, Codex, resume or state changes.

Full policies, runbooks and templates are indexed at `docs/process/README.md`.
