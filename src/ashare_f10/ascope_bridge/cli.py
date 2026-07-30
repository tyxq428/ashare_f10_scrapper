from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from ashare_f10.ascope_bridge.batch import run_batch
from ashare_f10.ascope_bridge.fixture import fixture_stock_processor
from ashare_f10.ascope_bridge.production_processor import canonical_stock_processor
from ashare_f10.ascope_bridge.reducer import reduce_batch
from ashare_f10.ascope_bridge.request_package import resolve_request_package

app = typer.Typer(help="A-SCOPE F10 batch export bridge")
console = Console()


def _print(value: object) -> None:
    if hasattr(value, "to_dict"):
        value = value.to_dict()  # type: ignore[union-attr]
    console.print_json(json.dumps(value, ensure_ascii=False))


@app.command("resolve")
def resolve_command(
    source: Annotated[
        Path,
        typer.Argument(help="Request ZIP or extracted directory"),
    ],
    batch_id: Annotated[str, typer.Option("--batch-id")] = "B001",
    as_of_date: Annotated[str, typer.Option("--as-of-date")] = "2026-07-30",
    smoke_count: Annotated[
        int,
        typer.Option("--smoke-count", min=0),
    ] = 0,
    output: Annotated[
        Path,
        typer.Option("--output", "-o"),
    ] = Path("ascope-request"),
) -> None:
    _print(
        resolve_request_package(
            source,
            batch_id=batch_id,
            as_of_date=as_of_date,
            smoke_count=smoke_count,
            output_dir=output,
        )
    )


@app.command("run-batch")
def run_batch_command(
    source: Annotated[
        Path,
        typer.Argument(help="Request ZIP or extracted directory"),
    ],
    batch_id: Annotated[str, typer.Option("--batch-id")] = "B001",
    as_of_date: Annotated[str, typer.Option("--as-of-date")] = "2026-07-30",
    smoke_count: Annotated[
        int,
        typer.Option("--smoke-count", min=0),
    ] = 0,
    data_root: Annotated[
        Path,
        typer.Option("--data-root"),
    ] = Path("data"),
    output_root: Annotated[
        Path,
        typer.Option("--output-root"),
    ] = Path("ascope-output"),
    stock_workers: Annotated[
        int,
        typer.Option("--stock-workers", min=1, max=2),
    ] = 2,
    max_attempts: Annotated[
        int,
        typer.Option("--max-attempts", min=1, max=2),
    ] = 2,
    soft_deadline_seconds: Annotated[
        float,
        typer.Option("--soft-deadline-seconds", min=0),
    ] = 0,
    heartbeat_seconds: Annotated[
        int,
        typer.Option("--heartbeat-seconds", min=1),
    ] = 30,
    fixture_mode: Annotated[
        bool,
        typer.Option("--fixture-mode"),
    ] = False,
    force_retry: Annotated[
        bool,
        typer.Option("--force-retry"),
    ] = False,
    reduce: Annotated[
        bool,
        typer.Option("--reduce/--no-reduce"),
    ] = True,
) -> None:
    resolved = resolve_request_package(
        source,
        batch_id=batch_id,
        as_of_date=as_of_date,
        smoke_count=smoke_count,
        output_dir=output_root / batch_id / "request",
    )
    optional: dict[str, Any] = {
        "processor": fixture_stock_processor if fixture_mode else canonical_stock_processor
    }
    result = run_batch(
        resolved,
        data_root=data_root,
        output_root=output_root,
        max_stock_workers=stock_workers,
        max_attempts=max_attempts,
        soft_deadline_seconds=soft_deadline_seconds,
        heartbeat_seconds=heartbeat_seconds,
        force_retry=force_retry,
        **optional,
    )
    payload: dict[str, Any] = {"batch_run": result.to_dict()}
    if reduce:
        reduction = reduce_batch(
            resolved,
            batch_output_dir=Path(result.output_dir),
        )
        payload["reduction"] = reduction.to_dict()
        if fixture_mode:
            manifest_path = Path(reduction.batch_manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixture_mode"] = True
            manifest["non_investment_output"] = True
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    _print(payload)
    if result.status in {"FAILED_TERMINAL", "BLOCKED"}:
        raise typer.Exit(1)
    if result.status == "FAILED_RECOVERABLE":
        raise typer.Exit(2)


@app.command("reduce-batch")
def reduce_batch_command(
    source: Annotated[
        Path,
        typer.Argument(help="Request ZIP or extracted directory"),
    ],
    batch_output: Annotated[
        Path,
        typer.Argument(help="Existing batch output directory"),
    ],
    batch_id: Annotated[str, typer.Option("--batch-id")] = "B001",
    as_of_date: Annotated[str, typer.Option("--as-of-date")] = "2026-07-30",
    smoke_count: Annotated[
        int,
        typer.Option("--smoke-count", min=0),
    ] = 0,
) -> None:
    resolved = resolve_request_package(
        source,
        batch_id=batch_id,
        as_of_date=as_of_date,
        smoke_count=smoke_count,
    )
    _print(reduce_batch(resolved, batch_output_dir=batch_output))


@app.command("checkpoint")
def checkpoint_command(
    path: Annotated[
        Path,
        typer.Argument(help="Batch checkpoint.json"),
    ],
) -> None:
    console.print_json(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
