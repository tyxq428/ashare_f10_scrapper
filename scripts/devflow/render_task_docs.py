from __future__ import annotations

import argparse
from pathlib import Path

from state_model import TaskState, load_json_yaml


def render_status(data: dict[str, object], state: TaskState) -> str:
    human = data["human_gate"]
    post_merge = data["post_merge"]
    return f"""# STATUS：{state.task_id}

```yaml
status: {state.status}
execution_status: {state.execution_status}
research_acceptance_status: {state.research_acceptance_status}
current_stage: {state.current_stage}
last_completed_stage: {state.last_completed_stage or 'null'}
branch: {state.working_branch}
pull_request: {data.get('pull_request') or 'pending'}
next_action: {data['next_action']}
post_merge: {post_merge['status']}
human_intervention_required: {str(human['required']).lower()}
```

本文件由 `task_state.yaml` 生成；冲突时以 canonical state 为准。
"""


def render_handoff(data: dict[str, object], state: TaskState) -> str:
    human = data["human_gate"]
    minimum_action = human.get("minimum_action") or "无"
    reason = human.get("reason") or "无"
    return f"""# HANDOFF：{state.task_id}

## 当前事实

- 状态：{state.status}
- 阶段：{state.current_stage}
- 分支：`{state.working_branch}`
- PR：{data.get('pull_request') or 'pending'}
- 最后成功步骤：`{data['last_successful_step']}`
- 下一动作：`{data['next_action']}`

## 当前阻塞

{reason}

## 最小人工动作

{minimum_action}

## 恢复读取顺序

1. `task_state.yaml`
2. 最新 GitHub Checks 与 Artifact
3. 当前 `Wxx_plan.md` / `Wxx_result.md`
4. 本文件
5. `docs/process/README.md`

## 重试预算

`{data['retry_budget']}`
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    args = parser.parse_args()

    data = load_json_yaml(args.task_dir / "task_state.yaml")
    state = TaskState.from_mapping(data)
    (args.task_dir / "STATUS.md").write_text(render_status(data, state), encoding="utf-8")
    (args.task_dir / "HANDOFF.md").write_text(render_handoff(data, state), encoding="utf-8")
    print("TASK_DOCS_RENDERED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
