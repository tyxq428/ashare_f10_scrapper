# Policy: monitoring, recovery, and valuable notifications

## Observability

Commands expected to exceed five minutes must stream output or emit a heartbeat containing UTC time, quiet duration, completed units, and bounded progress metadata. Checkpoints must survive Runner, network, and ChatGPT Web interruption.

## Failure classification

Classify before acting:

- `INFRA_RETRYABLE`: network, timeout, rate limit, transient platform;
- `MECHANICAL`: formatter, deterministic import/order, cache cleanup;
- `IMPLEMENTATION`: code or test logic;
- `DATA_QUALITY`: malformed, missing, unit or period issue;
- `RESEARCH_REVIEW_REQUIRED`: evidence-backed conflict or coverage gap;
- `PERMISSION_BLOCKED`;
- `SECURITY_BLOCKED`;
- `BUSINESS_DECISION_REQUIRED`;
- `PARALLEL_CONFLICT`;
- `REPEATED_FAILURE`.

Retry only the failed scope. Never repeat permission, schema, security, CAPTCHA, or business-decision failures blindly. A Codex task receives one Session; a second Session requires a newly diagnosed task package from ChatGPT Web.

## Failure bundle

Every stop writes a bounded bundle with task/stage, command, first root error, relevant tail, changed files, attempts, failure class, minimum human action, and recovery entry. Do not attach unbounded raw logs or secret-bearing HTTP details.

## Notifications

Only these user-facing states notify:

- `[TASK][COMPLETED]`;
- `[TASK][INTERRUPTED]`;
- `[TASK][HUMAN_REQUIRED]`;
- `[TASK][SECURITY_BLOCKED]`.

Intermediate PASS, stage completion, retries, branch pushes, PR updates, cache hits, and audit PASS are silent. Use one control Issue per task and deduplicate by `task_id + type + generation`. Assign and explicitly mention the owner only on a valuable state transition.
