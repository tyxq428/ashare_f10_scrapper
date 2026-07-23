# Runbook: Codex Thin Worker

## Eligibility

Use Codex only when the objective, allowed files, forbidden files, gate profile, expected behavior, and stop conditions are already known. Do not use it for business semantics, source-priority decisions, broad architecture, destructive migrations, Workflow/Secret infrastructure, or open-ended repository discovery.

## Task package

Create a versioned Markdown task containing:

- objective and context;
- allowed and read-only paths;
- forbidden changes;
- exact behavioral requirements;
- trusted gate profile;
- one-session limit;
- output schema;
- failure and stop conditions.

## Execution

1. ChatGPT Web commits the task plan and package on a trusted branch.
2. The caller invokes the reusable workflow.
3. Relay health is checked only when configuration changed or previous protocol/auth health failed.
4. The read-only Secret job starts the localhost forwarder and invokes Codex with explicit low effort.
5. Deterministic scope and result verification runs outside model reasoning.
6. A safe patch, result, manifest, and audit summary are handed off.
7. The secret-free Publish job reapplies and verifies the patch, runs the mapped Gate, and pushes a work branch.
8. ChatGPT Web reviews the branch and creates or updates the PR.

A failure never starts a second Codex Session automatically. It produces a Failure Bundle and an interruption or human-required event.
