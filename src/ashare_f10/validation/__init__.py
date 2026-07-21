"""Free official-source validation for A-share F10 data."""

from ashare_f10.validation.runner import OfficialValidationRunner, run_official_validation

VALIDATION_SCHEMA_VERSION = "1.0.0"

__all__ = ["OfficialValidationRunner", "VALIDATION_SCHEMA_VERSION", "run_official_validation"]
