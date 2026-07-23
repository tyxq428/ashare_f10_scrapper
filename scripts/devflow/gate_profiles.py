from __future__ import annotations

GATE_PROFILES: dict[str, list[list[str]]] = {
    "devflow-targeted": [
        ["python", "-m", "compileall", "-q", "scripts/devflow"],
        ["python", "scripts/devflow/validate_workflows.py"],
        ["pytest", "-q", "tests/test_devflow.py"],
    ],
    "resilient-command-targeted": [
        ["ruff", "check", "scripts/run_resilient_command.py", "tests/test_resilient_fetch.py"],
        ["pytest", "-q", "tests/test_resilient_fetch.py"],
    ],
}


def get_gate_profile(name: str) -> list[list[str]]:
    try:
        commands = GATE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown gate profile: {name}") from exc
    return [list(command) for command in commands]
