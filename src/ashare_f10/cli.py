from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.progress import Progress

from ashare_f10.config import settings
from ashare_f10.export.bundle import build_exports
from ashare_f10.fetch.pipeline import FetchPipeline

app = typer.Typer(help="A股F10投研平台命令行")
console = Console()


@app.command()
def fetch(
    stock_code: Annotated[str, typer.Argument(help="六位A股代码")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="输出目录")] = None,
    workers: Annotated[int | None, typer.Option("--workers", help="接口并发数")] = None,
    force: Annotated[bool, typer.Option("--force", help="忽略现有检查点重新执行")] = False,
) -> None:
    """拉取固定接口清单并生成JSON、Excel、Parquet和DuckDB。"""
    if workers:
        settings.max_workers = workers
    run_dir = output or settings.data_dir / stock_code / "manual"
    run_dir.mkdir(parents=True, exist_ok=True)

    with Progress() as progress:
        task = progress.add_task("拉取F10接口", total=113)

        def on_progress(event: dict) -> None:
            if event.get("type") == "group_completed":
                progress.advance(task)
                progress.update(task, description=f"{event.get('family')} ({event.get('record_count')}条)")

        pipeline = FetchPipeline(stock_code, run_dir, settings=settings, progress=on_progress)
        combined = pipeline.run(resume=not force)
    artifacts = build_exports(combined, run_dir)
    console.print("[bold green]完成[/bold green]")
    console.print_json(json.dumps(artifacts, ensure_ascii=False))


@app.command()
def validate(path: Path) -> None:
    """验证一个运行目录的核心交付文件。"""
    combined = path / "combined.json"
    artifacts = path / "artifacts.json"
    failures: list[str] = []
    for item in (combined, artifacts):
        if not item.exists():
            failures.append(f"缺少文件：{item}")
        else:
            try:
                json.loads(item.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                failures.append(f"JSON不可解析：{item}: {exc}")
    if failures:
        for failure in failures:
            console.print(f"[red]{failure}[/red]")
        raise typer.Exit(1)
    console.print("[green]验证通过[/green]")


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = settings.host,
    port: Annotated[int, typer.Option()] = settings.port,
    reload: Annotated[bool, typer.Option()] = False,
) -> None:
    """启动本地网页。"""
    uvicorn.run("ashare_f10.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
