# W07 Plan — Local and API Batch Execution Surface

## Goal

Expose the bridge through a reproducible CLI, Windows runbook and lightweight API/job surface without duplicating the underlying batch runner.

## Tasks

1. Add CLI commands to:
   - resolve a request package;
   - export a batch;
   - resume a batch;
   - reduce a batch;
   - inspect a checkpoint.
2. Add a Windows PowerShell wrapper using the project virtual environment.
3. Add API endpoints for creating, reading and cancelling A-SCOPE batch jobs if the web service is running.
4. Reuse the same models and state files as GitHub Actions.
5. Return streaming logs and a fixed heartbeat for jobs longer than five minutes.
6. Prevent API cancellation from deleting completed per-stock outputs.
7. Document local fixture, smoke, full-batch and resume commands.
8. Add tests for command validation, API state transitions and cancellation safety.

## Gates

- CLI and workflow call the same batch runner.
- Windows path quoting and leading-zero stock codes are preserved.
- API job state survives process restart through persisted checkpoint state.
- Cancellation stops new work but preserves completed outputs.
- Local fixture run emits the same batch manifest as CI.

## Exit

W07 passes when fixture execution is equivalent across CLI, Windows wrapper and API entrypoints.