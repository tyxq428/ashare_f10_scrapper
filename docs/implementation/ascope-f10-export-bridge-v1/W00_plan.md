# W00 Plan — Bootstrap and Preflight

## Goal

Create the unique task control surface, freeze scope and verify that implementation can proceed without a permission, secret or conflicting-path blocker.

## Inputs

- User confirmation dated 2026-07-30
- Main SHA `208c5450455e8fd678b0551b01bcead114a34893`
- Request-package metadata supplied with `ascope-financial-requests-30529291404.zip`
- Repository-wide `AGENTS.md` and task start runbook

## Tasks

1. Audit current main, open PRs and path overlap.
2. Create `feature/ascope-f10-export-bridge-v1` from main.
3. Create and assign Task Control Issue #71.
4. Persist contract, master plan, state, decisions, handoff and manual-action ledger.
5. Register the active task in `ACTIVE_TASKS.yaml`.
6. Open a Draft PR referencing the canonical directory.
7. Verify Codex remains disabled and no secret-bearing path is needed for W01.
8. Write `W00_result.md` and advance to W01 automatically.

## Allowed paths

Only the paths declared in `00_contract.md`.

## Gates

- Unique active branch: PASS required
- Control Issue assigned to `tyxq428`: PASS required
- Active task index and canonical state agree: PASS required
- Existing open PR path overlap: no overlapping product path required
- Codex/Responses paid calls: exactly zero
- Secret access for W01: not required

## Failure policy

- Existing unrelated Bark PRs are non-blocking if they do not overlap bridge product paths.
- A branch name collision, path-scope conflict or inability to write canonical state is blocking.
- Ordinary GitHub API transient failures receive bounded retry without duplicating files or Issues.

## Exit

W00 passes when the Draft PR exists, the canonical state is registered, scope is frozen and W01 can begin without human input.