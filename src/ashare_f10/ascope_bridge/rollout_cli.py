from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ashare_f10.ascope_bridge.rollout import (
    initialize_rollout,
    load_rollout,
    planned_actions,
    reduce_full_market,
    save_rollout,
)

app = typer.Typer(help="A-SCOPE F10 full-rollout controller and reducer")
console = Console()


def _print(value: object) -> None:
    console.print_json(json.dumps(value, ensure_ascii=False))


@app.command("initialize")
def initialize_command(
    source: Annotated[Path, typer.Argument(help="Request ZIP or extracted directory")],
    state_path: Annotated[Path, typer.Option("--state-path")],
    as_of_date: Annotated[str, typer.Option("--as-of-date")] = "2026-07-30",
    smoke_count: Annotated[int, typer.Option("--smoke-count", min=1)] = 5,
    fixture_mode: Annotated[bool, typer.Option("--fixture-mode")] = False,
) -> None:
    _print(
        initialize_rollout(
            source,
            as_of_date=as_of_date,
            state_path=state_path,
            smoke_count=smoke_count,
            fixture_mode=fixture_mode,
            max_active_batches=2,
        )
    )


@app.command("plan")
def plan_command(
    state_path: Annotated[Path, typer.Argument(help="rollout_state.json")],
) -> None:
    state = load_rollout(state_path)
    _print(
        {
            "phase": state["phase"],
            "max_active_batches": state["max_active_batches"],
            "active_batches": state["active_batches"],
            "actions": planned_actions(state),
        }
    )


@app.command("touch")
def touch_command(
    state_path: Annotated[Path, typer.Argument(help="rollout_state.json")],
) -> None:
    _print(save_rollout(state_path, load_rollout(state_path)))


@app.command("reduce-full")
def reduce_full_command(
    source: Annotated[Path, typer.Argument(help="Request ZIP or extracted directory")],
    batches_root: Annotated[
        Path,
        typer.Argument(help="Directory containing B001 through B027 output directories"),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir")],
    as_of_date: Annotated[str, typer.Option("--as-of-date")] = "2026-07-30",
    fixture_mode: Annotated[bool, typer.Option("--fixture-mode")] = False,
) -> None:
    batch_dirs = sorted(
        path
        for path in batches_root.iterdir()
        if path.is_dir() and len(path.name) == 4 and path.name.startswith("B")
    )
    _print(
        reduce_full_market(
            source,
            batch_dirs,
            as_of_date=as_of_date,
            output_dir=output_dir,
            fixture_mode=fixture_mode,
        )
    )


if __name__ == "__main__":
    app()
