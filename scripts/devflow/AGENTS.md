# Devflow script instructions

- Scripts must be deterministic, non-interactive, UTF-8, and safe to rerun.
- Parse canonical `.yaml` state files as JSON-compatible YAML unless a parser dependency is explicitly introduced.
- Never write heartbeats to Git on a timer; use job summaries or artifacts and commit state only at stable boundaries.
- Error output must classify the failure without echoing secret material or full unbounded logs.
- Do not use `eval`, shell interpolation of user-provided commands, or hidden network access.
- Gate profiles map to hard-coded command lists. Unknown profiles fail closed.
- Scope validation must inspect tracked, staged, and untracked changes.
- Failure bundles contain bounded log tails, changed-file summaries, the minimum human action, and a recovery entry.
- Tests must cover success, retryable failure, non-retryable failure, scope violation, stale state, and notification deduplication.
