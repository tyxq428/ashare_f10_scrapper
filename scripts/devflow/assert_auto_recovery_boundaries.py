from __future__ import annotations

import argparse
from pathlib import Path


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    controlled = text.split(
        "      - name: Prove automatic paid, Bark and Codex paths are absent",
        1,
    )[0]
    errors: list[str] = []
    for forbidden in (
        "actions/workflows/codex-task.yml/dispatches",
        "steps.decision.outputs.action == 'RETRY_CODEX'",
        "python scripts/devflow/recovery_task.py",
        "      - Codex Task\n",
        "      - Devflow Relay Health\n",
        "      - Devflow Incident\n",
        "      - Devflow Terminal State Notification\n",
        "BARK_PUSH_URL",
        "notification-runtime",
    ):
        if forbidden in controlled:
            errors.append(forbidden)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workflow",
        type=Path,
        default=Path(".github/workflows/devflow-auto-recovery.yml"),
    )
    args = parser.parse_args()
    errors = validate(args.workflow)
    if errors:
        for error in errors:
            print(f"AUTO_RECOVERY_FORBIDDEN_PATH={error}")
        return 1
    print("AUTOMATIC_CODEX_PATHS=0")
    print("AUTOMATIC_PAID_RELAY_PROBE_RETRIES=0")
    print("AUTOMATIC_BARK_RETRIES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
