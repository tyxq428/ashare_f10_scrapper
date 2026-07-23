# Runbook: incident handling and post-merge verification

## Incident

1. Identify the canonical task and stage.
2. Deduplicate against the current notification generation.
3. Classify the failure and preserve successful checkpoints.
4. Build a bounded Failure Bundle.
5. Set canonical status to `BLOCKED`, `WAITING_HUMAN`, or `SECURITY_BLOCKED` only when warranted.
6. Create or reuse the task control Issue, assign the owner, and add one explicit mention with minimum action and recovery entry.
7. Stop reminders after `/ack` or an acknowledged state; resolve the incident only after the recovery Gate passes.

## Post-merge

1. Record the merged SHA.
2. Run the independent G5 profile on exact `main` code, not the pre-merge branch result.
3. If G5 passes, write the final result and allow `DONE`.
4. If G5 fails, mark `POST_MERGE_BLOCKED`, create a dedicated hotfix branch, run only affected Gates plus required regressions, merge, and repeat G5.
5. Remove temporary validation branches and workflows after verified closeout.
