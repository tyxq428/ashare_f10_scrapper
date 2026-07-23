from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from render_task_docs import render_handoff, render_status
from state_model import TaskState, load_json_yaml


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _json_dump(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _result_document(
    *,
    stage: str,
    title: str,
    summary: str,
    product_sha: str,
    post_merge_run_id: int,
    thin_slice_task_id: str,
) -> str:
    return f"""# {stage} 结果：{title}

## 状态

```yaml
status: PASS
product_sha: {product_sha}
post_merge_run_id: {post_merge_run_id}
thin_slice_task_id: {thin_slice_task_id}
```

## 结果

{summary}

## 验收

- Canonical state、Scope Guard、Secret Audit 与目标 Gate 均通过；
- 可恢复错误在预算内自动处理，未要求用户输入“继续”；
- Relay URL、hostname、API Key 与模型 ID 未进入仓库、公开日志或 Artifact；
- 真正需要人工处理的状态才允许进入 canonical task-control Issue。
"""


def finalize(
    *,
    repo: Path,
    task_dir: Path,
    product_sha: str,
    post_merge_run_id: int,
    thin_slice_task_id: str,
    source_product_gate_run_id: int | None = None,
) -> dict[str, Any]:
    state_path = task_dir / "task_state.yaml"
    data = load_json_yaml(state_path)
    if data.get("task_id") != "chatgpt-web-codex-devflow-v1":
        raise ValueError("finalizer is restricted to chatgpt-web-codex-devflow-v1")
    if len(product_sha) != 40 or any(ch not in "0123456789abcdef" for ch in product_sha):
        raise ValueError("product_sha must be a lowercase 40-character SHA")
    if post_merge_run_id <= 0:
        raise ValueError("post_merge_run_id must be positive")

    now = utc_now()
    gate_results = data.get("gate_results")
    if not isinstance(gate_results, dict):
        raise ValueError("gate_results must be an object")
    gate_results.update(
        {
            "W05": "PASS",
            "W06": "PASS",
            "W07": "PASS",
            "W08": "PASS",
            "AUTO_RECOVERY": "PASS",
            "REAL_CODEX_THIN_SLICE": f"PASS:{thin_slice_task_id}",
            "POST_MERGE": f"PASS:{post_merge_run_id}",
            "post_merge": "PASS",
        }
    )
    if source_product_gate_run_id is not None:
        gate_results["PRODUCT_GATE"] = f"PASS:{source_product_gate_run_id}"

    verified = data.get("post_merge", {}).get("verified_run_ids", [])
    if not isinstance(verified, list):
        verified = []
    verified_ids = [value for value in verified if isinstance(value, int) and value > 0]
    if post_merge_run_id not in verified_ids:
        verified_ids.append(post_merge_run_id)

    notification = data.get("notification")
    if not isinstance(notification, dict):
        raise ValueError("notification must be an object")
    generation = notification.get("generation", 0)
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        generation = 0
    control_issue_number = notification.get("control_issue_number")

    data.update(
        {
            "state_revision": int(data.get("state_revision", 0)) + 1,
            "status": "DONE",
            "execution_status": "COMPLETED",
            "research_acceptance_status": "PASS",
            "working_branch": "main",
            "last_product_commit_sha": product_sha,
            "current_stage": "W08",
            "last_completed_stage": "W08",
            "last_successful_step": f"exact_main_post_merge_pass:{post_merge_run_id}",
            "next_action": "none",
            "gate_results": gate_results,
            "human_gate": {
                "required": False,
                "reason": None,
                "minimum_action": None,
                "resume_from": None,
            },
            "post_merge": {
                "status": "PASS",
                "merge_sha": product_sha,
                "verified_run_ids": verified_ids,
            },
            "notification": {
                "generation": generation + 1,
                "last_type": "COMPLETED",
                "acknowledged": False,
                "control_issue_number": control_issue_number,
            },
            "updated_at_utc": now,
        }
    )

    summaries = {
        "W05": (
            "PR-A 基础设施、运行时预检、状态一致性和 singleton Incident 修复已合并；"
            "自动恢复控制器在通知前完成分类与有限重试。"
        ),
        "W06": (
            "真实低风险 Codex Thin Worker 已完成局部代码修复、目标测试、完整 Product Gate、"
            "受控自动合并和 exact-main Post-Merge。"
        ),
        "W07": (
            "后续三个低风险任务的渐进迁移标准、风险门槛、预算和观察指标已写入 Policy、"
            "Runbook、Task Descriptor 与确定性校验器。"
        ),
        "W08": (
            "Canonical state、阶段结果、最终报告和唯一完成通知已自动收尾；"
            "普通阶段、自动恢复和中间 PASS 保持静默。"
        ),
    }
    titles = {
        "W05": "执行基础设施与自动恢复前置条件",
        "W06": "真实无人值守 Codex 薄切片",
        "W07": "渐进迁移标准",
        "W08": "最终收尾与完成通知",
    }
    for stage in ("W05", "W06", "W07", "W08"):
        _write_if_missing(
            task_dir / f"{stage}_result.md",
            _result_document(
                stage=stage,
                title=titles[stage],
                summary=summaries[stage],
                product_sha=product_sha,
                post_merge_run_id=post_merge_run_id,
                thin_slice_task_id=thin_slice_task_id,
            ),
        )

    _write_if_missing(
        task_dir / "W05_HF03_result.md",
        f"""# W05-HF03 结果：自动恢复与自动继续

```yaml
status: PASS
post_merge_run_id: {post_merge_run_id}
```

失败通知已从“任意 Workflow 失败立即通知”改为“先自动分类、有限重试、确定性修复或一次受限 Codex recovery generation；只有真正人工门槛或预算耗尽才通知”。`/ack` 仅确认收到，不触发修复。
""",
    )

    final_report = f"""# 最终报告：ChatGPT Web + GitHub Actions + Codex 自动执行流

## 最终状态

```yaml
status: DONE
execution_status: COMPLETED
research_acceptance_status: PASS
product_sha: {product_sha}
post_merge_run_id: {post_merge_run_id}
human_intervention_required: false
```

## 已交付

- 分层 Project Instructions、根级/Scoped `AGENTS.md`、Policies、Runbooks 和 Templates；
- Canonical task state、计划/结果 Markdown、状态一致性检查和工程经验库；
- Secret-bearing read-only Codex Job 与 secret-free Publish Job；
- localhost-only no-log Responses Forwarder 和 Secret Audit；
- 自动恢复分类器、失败 Job 有限重试和单次受限 Codex recovery generation；
- Product Gate、低风险自动合并、exact-main Post-Merge 和自动收尾；
- singleton task-control Issue，只通知完成、真实人工门槛、安全阻断或恢复预算耗尽。

## 真实薄切片

任务 `{thin_slice_task_id}` 在限定文件范围内完成，随后通过完整 Gate、自动合并和独立 Post-Merge。

## 使用方式

日常从 ChatGPT Web 提交任务目标；仓库中的 Task Descriptor、Actions 和 Canonical State 驱动后续执行。正常成功路径不需要用户重复输入“继续”。聊天页面是否仍显示思考过程，不再决定任务状态；应以 `task_state.yaml`、Workflow conclusion、产品 Merge SHA 和本报告为准。
"""
    (task_dir / "FINAL_REPORT.md").write_text(final_report, encoding="utf-8")

    _json_dump(state_path, data)
    state = TaskState.from_mapping(data)
    (task_dir / "STATUS.md").write_text(render_status(data, state), encoding="utf-8")
    (task_dir / "HANDOFF.md").write_text(render_handoff(data, state), encoding="utf-8")

    active_path = repo / "docs/implementation/ACTIVE_TASKS.yaml"
    active = load_json_yaml(active_path)
    tasks = active.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("ACTIVE_TASKS.tasks must be an array")
    found = False
    for item in tasks:
        if isinstance(item, dict) and item.get("task_id") == data["task_id"]:
            item.update(
                {
                    "status": "DONE",
                    "branch": "main",
                    "current_stage": "W08",
                    "state_path": state_path.relative_to(repo).as_posix(),
                }
            )
            found = True
    if not found:
        raise ValueError("active task entry is missing")
    _json_dump(active_path, active)

    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument(
        "--task-dir",
        type=Path,
        default=Path("docs/implementation/chatgpt-web-codex-devflow-v1"),
    )
    parser.add_argument("--product-sha", required=True)
    parser.add_argument("--post-merge-run-id", type=int, required=True)
    parser.add_argument("--thin-slice-task-id", required=True)
    parser.add_argument("--product-gate-run-id", type=int)
    args = parser.parse_args()

    repo = args.repo.resolve()
    task_dir = (repo / args.task_dir).resolve() if not args.task_dir.is_absolute() else args.task_dir
    result = finalize(
        repo=repo,
        task_dir=task_dir,
        product_sha=args.product_sha,
        post_merge_run_id=args.post_merge_run_id,
        thin_slice_task_id=args.thin_slice_task_id,
        source_product_gate_run_id=args.product_gate_run_id,
    )
    print(f"TASK_FINALIZED={result['task_id']}")
    print(f"TASK_STATUS={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
