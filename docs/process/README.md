# ChatGPT Web + GitHub Actions development process

This directory is the durable operating manual for repository tasks driven by ChatGPT Web and executed through GitHub Actions, with Codex available as a bounded code-editing worker.

## Instruction layers

| Layer | Location | Purpose |
|---|---|---|
| L0 | ChatGPT Project Instructions | Startup, recovery, and role boundaries |
| L1 | `/AGENTS.md` | Short repository-wide mandatory rules |
| L2 | Scoped `AGENTS.md` files | Directory-specific controls |
| L3 | `policies/` | Stable governance and semantics |
| L4 | `runbooks/` | Step-by-step operating procedures |
| L5 | `templates/` | Repeatable task artifacts |
| L6 | `docs/implementation/<task-id>/` | Current task facts and checkpoints |
| L7 | Workflows and `scripts/devflow/` | Deterministic enforcement |

## Canonical reading order

1. `/AGENTS.md`;
2. this index and the relevant policy or runbook;
3. `docs/implementation/ACTIVE_TASKS.yaml`;
4. active `task_state.yaml`, `HANDOFF.md`, and current stage plan;
5. current branch, pull request, and Checks.

## Core documents

- `policies/execution-and-state.md`
- `policies/monitoring-recovery-and-notification.md`
- `policies/gates-security-and-merge.md`
- `policies/data-and-research-semantics.md`
- `runbooks/start-or-resume-task.md`
- `runbooks/run-codex-thin-worker.md`
- `runbooks/handle-incident-and-post-merge.md`

The former SOP v2 is preserved as a normalized source snapshot under `archive/` and remains the source of principles that were redistributed into these layers.
