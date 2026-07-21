"""Full dual-source cross validation for Eastmoney and free official disclosures."""

from typing import Any

__all__ = ["FullCrossValidationRunner", "run_full_cross_validation"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from ashare_f10.cross_validation.runner import (
            FullCrossValidationRunner,
            run_full_cross_validation,
        )

        return {
            "FullCrossValidationRunner": FullCrossValidationRunner,
            "run_full_cross_validation": run_full_cross_validation,
        }[name]
    raise AttributeError(name)
