# SOP v2 source map

The user-provided `通用高效率任务执行_标准化流程_v2.0.md` is the source baseline for this layered process. It is not discarded. Its rules were redistributed as follows:

| SOP v2 concern | Authoritative v3 layer |
|---|---|
| Task contract, completion, work packages | `policies/execution-and-state.md` |
| Canonical state, plan/result docs, recovery | policy + task templates |
| Heartbeats, stall detection, failure classes | `policies/monitoring-recovery-and-notification.md` |
| Gate hierarchy, parallel audit, post-merge | `policies/gates-security-and-merge.md` |
| Missing vs zero, source conflict, point-in-time | `policies/data-and-research-semantics.md` |
| New/resumed task operations | `runbooks/start-or-resume-task.md` |
| Codex bounded execution | `runbooks/run-codex-thin-worker.md` |
| Incidents and post-merge hotfix | `runbooks/handle-incident-and-post-merge.md` |
| Reusable formats | `templates/` |
| High-frequency mandatory rules | root and scoped `AGENTS.md` |
| Deterministic enforcement | `scripts/devflow/` and GitHub Workflows |

This normalized source map prevents two independently maintained full SOP copies from drifting. The original uploaded file remains the historical input; all future policy edits occur in the authoritative layered documents above.
