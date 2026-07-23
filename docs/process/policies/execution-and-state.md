# Policy: execution contract and canonical state

## Task contract

A complex task starts only after the objective, scope, inputs, outputs, constraints, forbidden actions, acceptance criteria, rollback boundary, and human-intervention rules are explicit.

## One task, one control plane

Each active task has exactly one:

- task ID;
- active branch;
- pull request;
- JSON-compatible `task_state.yaml`;
- current stage plan;
- recovery entry.

`docs/implementation/ACTIVE_TASKS.yaml` is the repository index. Chat history, PR prose, and Workflow summaries may explain state but cannot override the canonical state file.

## Stage discipline

- Commit `Wxx_plan.md` before implementation.
- Commit `Wxx_result.md` only after the stage's declared Gate passes.
- A result records changed files, commands, Run IDs, Commit SHA, actual deviations, unresolved items, and next action.
- Normal success enters the next stage automatically.

## State model

Keep independent fields for:

- lifecycle `status`;
- `execution_status`;
- product or research `acceptance_status`;
- `post_merge_gate`;
- human gate and minimum action.

Do not store a self-referential current HEAD in state. Store the start base and the last verified product commit; state-only commits may follow it.

## Pause rules

Pause only for a real unresolved code or data error, missing permission/private data, security block, irreversible operation, or business decision. Ordinary warnings, review findings, cache hits, intermediate success, retryable infrastructure errors, and stage boundaries are not pause reasons.
