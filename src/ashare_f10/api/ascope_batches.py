from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ashare_f10.config import settings

TERMINAL_STATUSES = {
    "COMPLETED",
    "COMPLETED_WITH_GAPS",
    "FAILED_RECOVERABLE",
    "FAILED_TERMINAL",
    "CANCELLED",
}
RETRYABLE_STATUSES = {"FAILED_RECOVERABLE", "CANCELLED"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CreateAscopeBatchRequest(BaseModel):
    request_package: str = Field(min_length=1, max_length=255)
    batch_id: str = Field(default="B001", pattern=r"^B\d{3}$")
    as_of_date: date
    smoke_count: int = Field(default=0, ge=0, le=500)
    force_retry: bool = False
    fixture_mode: bool = False
    stock_workers: int = Field(default=2, ge=1, le=2)
    max_attempts: int = Field(default=2, ge=1, le=2)
    soft_deadline_seconds: int = Field(default=18000, ge=60, le=18000)
    heartbeat_seconds: int = Field(default=30, ge=5, le=300)


class AscopeBatchManager:
    def __init__(
        self,
        root: Path,
        *,
        project_root: Path | None = None,
        command_builder: Callable[[dict[str, Any], Path], list[str]] | None = None,
    ):
        self.root = Path(root)
        self.requests_dir = self.root / "requests"
        self.jobs_dir = self.root / "jobs"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self._command_builder = command_builder or self._default_command
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._recover_interrupted()

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def _state_path(self, job_id: str) -> Path:
        return self.jobs_dir / job_id / "job.json"

    def _read_state(self, job_id: str) -> dict[str, Any]:
        path = self._state_path(job_id)
        if not path.exists():
            raise LookupError(job_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid A-SCOPE batch state: {path}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"invalid A-SCOPE batch state: {path}")
        return value

    def _write_state(self, value: dict[str, Any]) -> dict[str, Any]:
        value = dict(value)
        value["updated_at_utc"] = utc_now()
        self._atomic_json(self._state_path(str(value["job_id"])), value)
        return value

    def _safe_request_path(self, value: str) -> Path:
        name = str(value or "").strip()
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError("request_package must be one file or directory name")
        candidate = (self.requests_dir / name).resolve()
        root = self.requests_dir.resolve()
        if candidate.parent != root:
            raise ValueError("request_package escapes the configured request directory")
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        return candidate

    def list_request_packages(self) -> list[dict[str, Any]]:
        result = []
        for path in sorted(self.requests_dir.iterdir(), key=lambda item: item.name):
            if path.name.startswith("."):
                continue
            result.append(
                {
                    "name": path.name,
                    "kind": "directory" if path.is_dir() else "file",
                    "size_bytes": path.stat().st_size if path.is_file() else None,
                    "modified_at_utc": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=UTC
                    ).isoformat().replace("+00:00", "Z"),
                }
            )
        return result

    def _default_command(self, state: dict[str, Any], output_root: Path) -> list[str]:
        request = state["request"]
        command = [
            sys.executable,
            "-m",
            "ashare_f10.ascope_bridge.cli",
            "run-batch",
            state["request_path"],
            "--batch-id",
            request["batch_id"],
            "--as-of-date",
            request["as_of_date"],
            "--smoke-count",
            str(request["smoke_count"]),
            "--data-root",
            str(settings.data_dir),
            "--output-root",
            str(output_root),
            "--stock-workers",
            str(request["stock_workers"]),
            "--max-attempts",
            str(request["max_attempts"]),
            "--soft-deadline-seconds",
            str(request["soft_deadline_seconds"]),
            "--heartbeat-seconds",
            str(request["heartbeat_seconds"]),
        ]
        if request.get("force_retry"):
            command.append("--force-retry")
        if request.get("fixture_mode"):
            command.append("--fixture-mode")
        return command

    def _recover_interrupted(self) -> None:
        for path in self.jobs_dir.glob("*/job.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if value.get("status") not in {"PENDING", "RUNNING", "CANCEL_REQUESTED"}:
                continue
            value.update(
                status="FAILED_RECOVERABLE",
                retryable=True,
                error_code="API_PROCESS_RESTARTED",
                message="The API process restarted while the batch was active; resume from the persisted checkpoint.",
                pid=None,
                completed_at_utc=utc_now(),
            )
            self._atomic_json(path, value)

    def create(self, request: CreateAscopeBatchRequest) -> dict[str, Any]:
        request_path = self._safe_request_path(request.request_package)
        job_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        job_dir = self.jobs_dir / job_id
        output_root = job_dir / "output"
        job_dir.mkdir(parents=True, exist_ok=False)
        value = {
            "schema_version": 1,
            "job_id": job_id,
            "status": "PENDING",
            "retryable": False,
            "cancel_requested": False,
            "request_path": str(request_path),
            "request": {
                **request.model_dump(mode="json"),
                "as_of_date": request.as_of_date.isoformat(),
            },
            "output_root": str(output_root),
            "log_path": str(job_dir / "job.log"),
            "created_at_utc": utc_now(),
            "started_at_utc": None,
            "completed_at_utc": None,
            "updated_at_utc": utc_now(),
            "pid": None,
            "return_code": None,
            "error_code": "",
            "message": "",
            "batch_result": None,
        }
        self._write_state(value)
        self._start(job_id)
        return self.get(job_id)

    def _start(self, job_id: str) -> None:
        with self._lock:
            active = self._threads.get(job_id)
            if active and active.is_alive():
                raise RuntimeError(f"job already running: {job_id}")
            thread = threading.Thread(
                target=self._run_job,
                args=(job_id,),
                name=f"ascope-{job_id}",
                daemon=True,
            )
            self._threads[job_id] = thread
            thread.start()

    def _run_job(self, job_id: str) -> None:
        try:
            state = self._read_state(job_id)
            job_dir = self.jobs_dir / job_id
            output_root = Path(state["output_root"])
            output_root.mkdir(parents=True, exist_ok=True)
            log_path = Path(state["log_path"])
            state.update(
                status="RUNNING",
                retryable=False,
                cancel_requested=False,
                started_at_utc=state.get("started_at_utc") or utc_now(),
                completed_at_utc=None,
                return_code=None,
                error_code="",
                message="",
            )
            self._write_state(state)
            command = self._command_builder(state, output_root)
            process_kwargs: dict[str, Any] = {
                "cwd": str(self.project_root),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
            }
            if os.name == "nt":
                process_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                process_kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **process_kwargs)
            with self._lock:
                self._processes[job_id] = process
            state["pid"] = process.pid
            self._write_state(state)
            with log_path.open("a", encoding="utf-8") as log:
                log.write(f"[{utc_now()}] command={json.dumps(command, ensure_ascii=False)}\n")
                assert process.stdout is not None
                for line in process.stdout:
                    log.write(line)
                    log.flush()
            return_code = process.wait()
            state = self._read_state(job_id)
            state["pid"] = None
            state["return_code"] = return_code
            state["completed_at_utc"] = utc_now()
            if state.get("cancel_requested"):
                state.update(
                    status="CANCELLED",
                    retryable=True,
                    error_code="CANCELLED_BY_OPERATOR",
                    message="Cancellation requested; completed outputs and checkpoint were preserved.",
                )
            elif return_code == 0:
                state.update(status="COMPLETED", retryable=False)
            elif return_code == 2:
                state.update(
                    status="FAILED_RECOVERABLE",
                    retryable=True,
                    error_code="BATCH_PARTIAL",
                    message="The batch produced a resumable partial result.",
                )
            else:
                state.update(
                    status="FAILED_TERMINAL",
                    retryable=False,
                    error_code="BATCH_EXIT_NONZERO",
                    message=f"Batch process exited with code {return_code}.",
                )
            result_path = output_root / state["request"]["batch_id"] / "batch_run_result.json"
            if result_path.exists():
                try:
                    state["batch_result"] = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    state["batch_result"] = None
            self._write_state(state)
        except Exception as exc:  # noqa: BLE001
            try:
                state = self._read_state(job_id)
                state.update(
                    status="FAILED_TERMINAL",
                    retryable=False,
                    error_code=str(getattr(exc, "code", "API_JOB_EXCEPTION")),
                    message=str(exc),
                    pid=None,
                    completed_at_utc=utc_now(),
                )
                self._write_state(state)
            except Exception:  # noqa: BLE001
                pass
        finally:
            with self._lock:
                self._processes.pop(job_id, None)
                self._threads.pop(job_id, None)

    def get(self, job_id: str) -> dict[str, Any]:
        return self._read_state(job_id)

    def list(self, *, limit: int = 100) -> list[dict[str, Any]]:
        result = []
        paths = sorted(
            self.jobs_dir.glob("*/job.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in paths[:limit]:
            try:
                result.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return result

    def cancel(self, job_id: str) -> dict[str, Any]:
        state = self._read_state(job_id)
        if state.get("status") in TERMINAL_STATUSES:
            raise RuntimeError(f"job is already terminal: {job_id}")
        state["cancel_requested"] = True
        state["status"] = "CANCEL_REQUESTED"
        self._write_state(state)
        with self._lock:
            process = self._processes.get(job_id)
        if process and process.poll() is None:
            try:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
            except (OSError, ProcessLookupError, ValueError):
                process.terminate()
        return self.get(job_id)

    def resume(self, job_id: str) -> dict[str, Any]:
        state = self._read_state(job_id)
        if state.get("status") not in RETRYABLE_STATUSES:
            raise RuntimeError(f"job is not resumable: {job_id}")
        state["request"]["force_retry"] = True
        state.update(
            status="PENDING",
            retryable=False,
            cancel_requested=False,
            completed_at_utc=None,
            return_code=None,
            error_code="",
            message="",
        )
        self._write_state(state)
        self._start(job_id)
        return self.get(job_id)

    def read_log(self, job_id: str, *, offset: int = 0, limit: int = 65536) -> dict[str, Any]:
        state = self._read_state(job_id)
        path = Path(state["log_path"])
        if not path.exists():
            return {"job_id": job_id, "offset": offset, "next_offset": offset, "content": ""}
        size = path.stat().st_size
        start = min(max(offset, 0), size)
        with path.open("rb") as handle:
            handle.seek(start)
            payload = handle.read(min(max(limit, 1), 1024 * 1024))
        return {
            "job_id": job_id,
            "offset": start,
            "next_offset": start + len(payload),
            "content": payload.decode("utf-8", errors="replace"),
        }


manager = AscopeBatchManager(settings.data_dir / "_ascope_bridge")
router = APIRouter(prefix="/api/ascope/batches", tags=["ascope-batches"])


@router.get("/requests")
def list_ascope_request_packages() -> dict[str, Any]:
    return {"items": manager.list_request_packages()}


@router.post("")
def create_ascope_batch(request: CreateAscopeBatchRequest) -> dict[str, Any]:
    try:
        return manager.create(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("")
def list_ascope_batches(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    return {"items": manager.list(limit=limit)}


@router.get("/{job_id}")
def get_ascope_batch(job_id: str) -> dict[str, Any]:
    try:
        return manager.get(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="A-SCOPE batch job not found") from exc


@router.get("/{job_id}/log")
def get_ascope_batch_log(
    job_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(65536, ge=1, le=1024 * 1024),
) -> dict[str, Any]:
    try:
        return manager.read_log(job_id, offset=offset, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="A-SCOPE batch job not found") from exc


@router.post("/{job_id}/cancel")
def cancel_ascope_batch(job_id: str) -> dict[str, Any]:
    try:
        return manager.cancel(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="A-SCOPE batch job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{job_id}/resume")
def resume_ascope_batch(job_id: str) -> dict[str, Any]:
    try:
        return manager.resume(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="A-SCOPE batch job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
