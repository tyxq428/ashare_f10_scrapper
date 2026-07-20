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

        # A single public endpoint can occasionally return a transient 502/503
        # while the other 112 groups succeed. Reuse the completed checkpoints
        # and retry only failed groups before exporting the final package.
        for retry_index in range(1, 3):
            failed_count = int(combined.get("metadata", {}).get("failed_group_count", 0))
            if failed_count == 0:
                break
            console.print(
                f"[yellow]检测到{failed_count}个失败请求组，正在进行第{retry_index}次增量重试[/yellow]"
            )
            pipeline = FetchPipeline(stock_code, run_dir, settings=settings, progress=on_progress)
            combined = pipeline.run(resume=True)

    artifacts = build_exports(combined, run_dir)
    console.print("[bold green]完成[/bold green]")
    console.print_json(json.dumps(artifacts, ensure_ascii=False))


@app.command()
def validate(path: Path) -> None:
    """验证一个运行目录的完整性、请求组状态和核心交付文件。"""
    combined_path = path / "combined.json"
    artifacts_path = path / "artifacts.json"
    failures: list[str] = []
    combined_payload: dict | None = None
    artifacts_payload: dict | None = None

    for item in (combined_path, artifacts_path):
        if not item.exists():
            failures.append(f"缺少文件：{item}")
            continue
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
            if item == combined_path:
                combined_payload = payload
            else:
                artifacts_payload = payload
        except Exception as exc:  # noqa: BLE001
            failures.append(f"JSON不可解析：{item}: {exc}")

    if combined_payload is not None:
        metadata = combined_payload.get("metadata", {})
        failed_group_count = int(metadata.get("failed_group_count", 0))
        if failed_group_count:
            failed_groups = [
                f"{group.get('family')}({group.get('group_id')})"
                for group in combined_payload.get("groups", [])
                if not group.get("success")
            ]
            failures.append(
                f"存在{failed_group_count}个失败请求组：{', '.join(failed_groups[:10])}"
            )
        for group in combined_payload.get("groups", []):
            records = group.get("records", [])
            reported = int(group.get("record_count", len(records)))
            if reported != len(records):
                failures.append(
                    f"请求组{group.get('group_id')}记录数不一致："
                    f"record_count={reported}, records={len(records)}"
                )

    if artifacts_payload is not None:
        for key in ("json", "excel", "parquet", "duckdb"):
            value = artifacts_payload.get(key)
            if not value:
                failures.append(f"artifacts.json缺少{key}路径")
                continue
            artifact_path = Path(value)
            if not artifact_path.is_absolute():
                artifact_path = Path.cwd() / artifact_path
            if not artifact_path.exists() or artifact_path.stat().st_size == 0:
                failures.append(f"交付文件不存在或为空：{key} -> {artifact_path}")

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
