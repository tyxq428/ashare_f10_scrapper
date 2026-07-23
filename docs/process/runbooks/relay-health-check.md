# Runbook: private relay health check

Run this check only for first production enablement, a changed endpoint/key/model, or an auth/protocol/streaming failure.

1. Read Secrets only in the `agent-runtime` Environment job.
2. Register masks before network access.
3. Normalize a base URL privately to `/v1/responses`.
4. Send one streaming Responses request with minimal output and explicit no/low reasoning where supported.
5. Record only status class, stream/content indicators, event types, and expected-output match.
6. Never print endpoint, hostname, key, model, response body, raw exception, or headers.
7. Run the independent log leak audit after the Workflow reaches a terminal state.

A successful health check is silent. Authentication, endpoint, protocol, or secret-audit failure is a valuable incident.
