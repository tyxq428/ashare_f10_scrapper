from __future__ import annotations

"""Stable entry point for versioned Devflow workflow policy."""

from validate_workflows_v2 import main, validate_file

__all__ = ["main", "validate_file"]


if __name__ == "__main__":
    raise SystemExit(main())
