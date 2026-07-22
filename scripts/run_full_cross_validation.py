from __future__ import annotations

import argparse
import json
from pathlib import Path

from ashare_f10.cross_validation.runner import run_full_cross_validation


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run full-history official cross-validation with progress output")
    result.add_argument("stock_code")
    result.add_argument("run_dir", type=Path)
    result.add_argument("--output", type=Path)
    result.add_argument("--max-periods", type=int)
    result.add_argument("--report", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    output_dir = args.output or args.run_dir / "cross_validation"

    def progress(event: dict) -> None:
        print(json.dumps({"type": "official_validation_progress", **event}, ensure_ascii=False), flush=True)

    result = run_full_cross_validation(
        args.stock_code,
        args.run_dir,
        output_dir,
        max_periods=args.max_periods,
        progress=progress,
    )
    report_path = args.report or output_dir / "visual-full-history-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    acceptance = str(result.get("acceptance_status") or "UNKNOWN")
    # A traceable source conflict is a successful validation run that needs review,
    # not an execution failure. Structural/classification failures still fail CI.
    allowed = {"PASS", "PASS_WITH_COVERAGE_GAPS", "FAIL_SOURCE_CONFLICT"}
    return 0 if acceptance in allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
