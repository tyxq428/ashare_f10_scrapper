# Test instructions

- Tests must assert the public contract and the real data source, not incidental implementation details.
- Reproduce production failures with representative error text or deterministic fixtures.
- Every bug fix requires a regression test that fails before the fix.
- Include negative tests that prevent a broad fix from accepting unrelated failures or hiding real conflicts.
- Do not use live network calls in unit tests.
- Explicit zero, missing, unavailable, permission-blocked, source-conflict, and parse-suspect cases must remain distinguishable.
- Devflow tests must not read actual Environment Secrets or external endpoints.
