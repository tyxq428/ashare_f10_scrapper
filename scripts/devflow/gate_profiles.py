REPOSITORY_FULL: list[list[str]] = [
    ["python", "-m", "compileall", "-q", "src", "scripts"],
    ["node", "--check", "src/ashare_f10/web/research-grid.js"],
    ["node", "--check", "src/ashare_f10/web/static-search-worker.js"],
    ["node", "--check", "src/ashare_f10/web/app.js"],
    ["node", "--check", "src/ashare_f10/web/job-center-v2.js"],
    ["node", "--check", "src/ashare_f10/web/raw-pack.js"],
    ["node", "--check", "src/ashare_f10/web/run.js"],
    ["node", "--check", "src/ashare_f10/web/research-pack.js"],
    ["node", "tests/static-search-worker-smoke.cjs"],
    [
        "ruff",
        "check",
        "src",
        "tests",
        "scripts/run_resilient_fetch.py",
        "scripts/run_resilient_command.py",
    ],
    ["pytest", "--cov=ashare_f10", "--cov-report=term-missing"],
]

DEVFLOW_TESTS = [
    "tests/test_devflow.py",
    "tests/test_devflow_codex_environment.py",
    "tests/test_devflow_operational_optimization.py",
]

GATE_PROFILES: dict[str, list[list[str]]] = {
    "devflow-targeted": [
        ["python", "-m", "compileall", "-q", "scripts/devflow"],
        ["python", "scripts/devflow/validate_docs.py"],
        ["python", "scripts/devflow/validate_workflows.py"],
        ["ruff", "check", "scripts/devflow", *DEVFLOW_TESTS],
        ["pytest", "-q", *DEVFLOW_TESTS],
    ],
    "devflow-auto-recovery-targeted": [
        ["python", "-m", "compileall", "-q", "scripts/devflow"],
        ["python", "scripts/devflow/validate_workflows.py"],
        ["ruff", "check", "scripts/devflow", *DEVFLOW_TESTS],
        ["pytest", "-q", *DEVFLOW_TESTS],
    ],
    "resilient-command-targeted": [
        ["ruff", "check", "scripts/run_resilient_command.py", "tests/test_resilient_fetch.py"],
        ["pytest", "-q", "tests/test_resilient_fetch.py"],
    ],
    "repository-full": REPOSITORY_FULL,
    "resilient-command-post-merge": [
        ["ruff", "check", "scripts/run_resilient_command.py", "tests/test_resilient_fetch.py"],
        ["pytest", "-q", "tests/test_resilient_fetch.py"],
        *REPOSITORY_FULL,
    ],
}


def get_gate_profile(name: str) -> list[list[str]]:
    try:
        commands = GATE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown gate profile: {name}") from exc
    return [list(command) for command in commands]
