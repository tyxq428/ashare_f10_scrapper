# Test Scoped Rules

These rules apply to `tests/**`.

- Reproduce confirmed failures with the smallest deterministic fixture, including the actual error wording when classification depends on text.
- Assert both the positive path and the nearest dangerous negative path.
- Tests must target the real source of runtime data; do not assert dynamically injected content in a static template.
- Preserve explicit-zero versus missing-value distinctions.
- New retry classifications require a matching non-retryable regression.
- Scope and security tests must fail closed.
- Avoid live network access in unit tests. Live official-source checks belong to named E2E workflows.
- Do not weaken or delete an existing regression merely to make a new patch pass.
