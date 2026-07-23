# Policy: Gates, security, and merge

## Gate levels

- **G0**: state, docs, branch, workflow syntax, permissions, and secret-safety.
- **G1**: task-specific static checks and deterministic tests.
- **G2**: existing full `Test` workflow.
- **G3**: real bounded module thin slice.
- **G4**: product E2E or multi-sample matrix.
- **G5**: independent post-merge verification.

A task declares the minimum profile. A higher Gate does not erase a failed lower Gate.

## Codex security boundary

The Secret-bearing job:

- declares `environment: agent-runtime`;
- has repository read-only permissions;
- uses a localhost, no-log Responses forwarder;
- runs one bounded prompt and one output schema;
- validates changed paths and scans the handoff.

The separate Publish job:

- does not declare the Environment or relay Secrets;
- verifies manifest and allowed paths again;
- reapplies the patch in a clean checkout;
- runs a trusted gate profile;
- pushes only a work branch.

Never execute arbitrary commands from task YAML, untrusted Issues, fork PRs, comments, or downloaded artifacts. Never use `pull_request_target` to execute untrusted content.

## Merge policy

ChatGPT Web reviews the actual diff and Checks, creates or updates the PR, refreshes the branch against latest `main`, audits parallel PR file overlap, and merges only after all declared pre-merge Gates pass. Important changes remain incomplete until G5 passes on the merged SHA. A post-merge failure creates a separate hotfix path and blocks 100% completion.
