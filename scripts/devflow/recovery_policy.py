from __future__ import annotations

"""Compatibility entry point for the versioned recovery policy.

The implementation lives in ``recovery_policy_v2`` so upgrades can retain a
stable import/CLI path while the policy evolves behind deterministic tests.
"""

from recovery_policy_v2 import RecoveryDecision, classify, main

__all__ = ["RecoveryDecision", "classify", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
