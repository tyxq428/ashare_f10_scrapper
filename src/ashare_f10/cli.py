from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.progress import Progress

from ashare_f10.config import settings
from ashare_f10.cross_validation.runner import run_full_cross_validation
from ashare_f10.export.bundle import build_exports
from ashare_f10.fetch.pipeline import FetchPipeline
from ashare_f10.raw_sources.runner import run_raw_pack
from ashare_f10.research_pack.runner import run_research_pack
from ashare_f10.validation.runner import run_official_validation

app = typer.Typer(help="A股F10投研平台命令行")
console = Console()


def _run_raw_pack_if_requested(
    stock_code: str,
    run_dir: Path,
    *,
    include_raw_pack: bool,
    raw_pack_packs: str,
    raw_pack_max_docs: int,
) -> dict | None:
    if not include_raw_pack:
        return None
    console.print("[cyan]正在生成官方Raw Pack[/cyan]")
    result = run_raw_pack(
        stock_code,
        run_dir,
        f10_run_dir=run_dir,
        packs=raw_pack_packs,
        max_docs=raw_pack_max_docs,
    )
    console.print(
        f"[green]Raw Pack完成：{result['document_count']}条资料，状态={result['status_counts']}[/green]"
    )
    return result


def _status_color(status: str) -> str:
    if status.startswith("FAIL"):
        return "red"
    if status.startswith("PASS_WITH") or status.startswith("PARTIAL"):
        return "yellow"
    return "green" if status in {"PASS", "COMPLETED"} else "yellow"


@app.command()
def fetch(
    stock_code: Annotated[str, typer.Argument(help="六位A股代码")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="输出目录")] = None,
    workers: Annotated[int | None, typer.Option("--workers", help="接口并发数")] = None,
    force: Annotated[bool, typer.Option("--force", help="忽略现有检查点重新执行")] = False,
    include_raw_pack: Annotated[
        bool, typer.Option("--include-raw-pack/--no-raw-pack", help="同时生成官方Raw Pack")
    ] = False,
    raw_pack_packs: Annotated[
        str, typer.Option("--raw-pack-packs", help="Raw Pack资料包：default/all/逗号分隔pack_id")
    ] = "default",
    raw_pack_max_docs: Annotated[
        int, typer.Option("--raw-pack-max-docs", min=1, max=5000, help="Raw Pack最多文档数")
    ] = 200,
) -> None:
    """拉取固定接口清单并生成JSON、Excel、Parquet、DuckDB和可选官方Raw Pack。"""
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
    raw_pack_result = _run_raw_pack_if_requested(
        stock_code,
        run_dir,
        include_raw_pack=include_raw_pack,
        raw_pack_packs=raw_pack_packs,
        raw_pack_max_docs=raw_pack_max_docs,
    )
    if raw_pack_result is not None:
        artifacts["raw_pack"] = raw_pack_result["output_dir"]
        artifacts["raw_pack_summary"] = str(run_dir / "reports" / stock_code / "raw_pack_summary.json")
    console.print("[bold green]完成[/bold green]")
    console.print_json(json.dumps(artifacts, ensure_ascii=False))


@app.command("raw-pack")
def raw_pack(
    stock_code: Annotated[str, typer.Argument(help="六位A股代码")],
    run_dir: Annotated[Path, typer.Option("--run-dir", help="已完成F10拉取的运行目录")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Raw Pack输出根目录")] = None,
    packs: Annotated[str, typer.Option("--packs", help="default/all/逗号分隔pack_id")] = "default",
    max_docs: Annotated[int, typer.Option("--max-docs", min=1, max=5000)] = 200,
) -> None:
    """基于已完成F10版本生成官方原文、官网、实体风险和条件资料Raw Pack。"""
    result = run_raw_pack(
        stock_code,
        output or run_dir,
        f10_run_dir=run_dir,
        packs=packs,
        max_docs=max_docs,
    )
    console.print_json(json.dumps(result, ensure_ascii=False))


@app.command("validate-official")
def validate_official(
    stock_code: Annotated[str, typer.Argument(help="六位A股代码")],
    run_dir: Annotated[Path, typer.Argument(help="已完成F10拉取的运行目录")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="验证结果输出目录")] = None,
    annual_year: Annotated[int, typer.Option("--annual-year", help="年度报告所属年度")] = 2025,
    quarter_year: Annotated[int, typer.Option("--quarter-year", help="第一季度报告所属年度")] = 2026,
    as_of_date: Annotated[
        str | None, typer.Option("--as-of-date", help="研究截止日YYYY-MM-DD；默认运行当日")
    ] = None,
) -> None:
    """使用免费官方披露文件对F10财务数据进行独立薄切片验证。"""
    result = run_official_validation(
        stock_code,
        run_dir,
        output,
        annual_year,
        quarter_year,
        as_of_date,
    )
    status = str(result.get("acceptance_status", "UNKNOWN"))
    color = _status_color(status)
    console.print(f"[{color}]官方交叉验证状态：{status}[/{color}]")
    console.print_json(json.dumps(result, ensure_ascii=False))
    if status.startswith("FAIL"):
        raise typer.Exit(1)


@app.command("run-and-validate")
def run_and_validate(
    stock_code: Annotated[str, typer.Argument(help="六位A股代码")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="任务输出目录")] = None,
    workers: Annotated[int | None, typer.Option("--workers", help="东方财富接口并发数")] = None,
    max_periods: Annotated[
        int | None, typer.Option("--max-periods", help="最多验证最近N个报告期；默认全部")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="忽略东方财富检查点重新执行")] = False,
    as_of_date: Annotated[
        str | None, typer.Option("--as-of-date", help="研究截止日YYYY-MM-DD；默认运行当日")
    ] = None,
) -> None:
    """一次输入股票代码，生成东方财富、官方披露和双源比较数据包。"""
    if workers:
        settings.max_workers = workers
    run_dir = output or settings.data_dir / stock_code / "manual-full-validation"
    run_dir.mkdir(parents=True, exist_ok=True)
    pipeline = FetchPipeline(stock_code, run_dir, settings=settings)
    combined = pipeline.run(resume=not force)
    for _retry_index in range(2):
        if int(combined.get("metadata", {}).get("failed_group_count", 0)) == 0:
            break
        pipeline = FetchPipeline(stock_code, run_dir, settings=settings)
        combined = pipeline.run(resume=True)
    if int(combined.get("metadata", {}).get("failed_group_count", 0)):
        raise typer.Exit(1)
    build_exports(combined, run_dir)
    result = run_full_cross_validation(
        stock_code,
        run_dir,
        run_dir / "cross_validation",
        max_periods=max_periods,
        as_of_date=as_of_date,
    )
    console.print_json(json.dumps(result, ensure_ascii=False))
    if str(result.get("acceptance_status", "")).startswith("FAIL"):
        raise typer.Exit(1)


@app.command("research-pack")
def research_pack(
    stock_code: Annotated[str, typer.Argument(help="六位A股代码")],
    run_dir: Annotated[Path, typer.Argument(help="已完成F10或双源验证的运行目录")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Research Pack输出目录")
    ] = None,
    as_of_date: Annotated[
        str | None, typer.Option("--as-of-date", help="研究截止日YYYY-MM-DD；默认运行当日")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="忽略相同输入的已完成Research Pack缓存")
    ] = False,
) -> None:
    """生成规范事实、研究专题和官方证据图Research Pack。"""
    result = run_research_pack(
        stock_code,
        run_dir,
        output,
        as_of_date=as_of_date,
        force=force,
    )
    status = str(result.get("status", "UNKNOWN"))
    color = _status_color(status)
    console.print(f"[{color}]Research Pack状态：{status}[/{color}]")
    console.print_json(json.dumps(result, ensure_ascii=False))
    if status.startswith("FAIL"):
        raise typer.Exit(1)


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
            failures.append(f"存在{failed_group_count}个失败请求组：{', '.join(failed_groups[:10])}")
        for group in combined_payload.get("groups", []):
            records = group.get("records", [])
            reported = int(group.get("record_count", len(records)))
            if reported != len(records):
                failures.append(
                    f"请求组{group.get('group_id')}记录数不一致：record_count={reported}, records={len(records)}"
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
        raw_pack_path = artifacts_payload.get("raw_pack")
        if raw_pack_path:
            quality_path = Path(raw_pack_path) / "quality" / "raw_pack_quality.json"
            if not quality_path.exists():
                failures.append(f"Raw Pack质量报告不存在：{quality_path}")
            else:
                quality = json.loads(quality_path.read_text(encoding="utf-8"))
                if quality.get("status") != "PASS":
                    failures.append(f"Raw Pack质量验证未通过：{quality.get('failures')}")
        research_quality = artifacts_payload.get("research_pack_quality")
        if research_quality:
            quality_path = Path(research_quality)
            if not quality_path.is_absolute():
                quality_path = Path.cwd() / quality_path
            if not quality_path.exists():
                failures.append(f"Research Pack质量报告不存在：{quality_path}")
            else:
                quality = json.loads(quality_path.read_text(encoding="utf-8"))
                if quality.get("status") != "PASS":
                    failures.append(f"Research Pack质量验证未通过：{quality.get('failures')}")

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
    uvicorn.run("ashare_f10.api.app_with_raw_pack:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
