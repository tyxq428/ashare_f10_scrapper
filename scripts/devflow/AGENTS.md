# Devflow Script Rules

These rules apply to `scripts/devflow/**`.

- Scripts must be deterministic, non-interactive and usable on GitHub-hosted Ubuntu runners.
- Machine-readable output goes to JSON files; terminal output is bounded and must not contain secrets or raw upstream errors.
- Treat files received through artifacts as untrusted data: verify SHA-256, declared paths and size before use.
- Do not execute commands read from task files. Resolve a trusted `gate_profile` to commands owned by this repository.
- State validation must fail closed for malformed state, missing plans/results, invalid terminal states and missing recovery instructions.
- Secret audit reports only pass/fail counts; it must never print a matching value or surrounding bytes.
- Failure bundles contain the first root error, a bounded tail, affected paths, completed gates and a recovery entry; never copy an unbounded log.
- Unit tests are required for state transitions, path guards, endpoint normalization, secret variants and workflow static policy.
