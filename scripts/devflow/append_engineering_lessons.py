import argparse
from pathlib import Path

LESSONS = """
## GHA-012 原始Workflow失败直接升级为用户中断

- **现象**：状态校验、Forwarder或Codex首次失败后，任务控制Issue立即出现`[TASK][INTERRUPTED]`，用户必须回到ChatGPT Web输入“继续”。
- **根因**：Incident Workflow直接监听`workflow_run`的非成功终态，没有在通知前执行错误分类、有限重试或受限代码修复。
- **修复**：新增`Devflow Auto Recovery`，先读取Job/Step元数据和安全摘要，自动执行失败Job重跑或一个Codex Recovery Generation；只有人工门槛、安全阻断、无法分类或预算耗尽才发送`devflow_notify`。
- **预防规则**：原始失败事件不得直接面向用户；通知必须是自动恢复控制器的最终决策输出。

## GHA-013 `/ack`文案让用户误以为会触发修复

- **现象**：控制Issue要求回复`/ack`，用户合理地理解为“确认后继续”，但实际没有任何Workflow监听该命令。
- **根因**：确认送达和恢复执行两种语义混在同一提示中。
- **修复**：通知明确说明`/ack`只确认已看到，不触发修复、重试、Codex、resume或状态更新；自动恢复必须在通知前完成。
- **预防规则**：ACK、retry和resume必须是不同命令和不同状态迁移；没有实现监听器时不得暗示命令会执行动作。

## GHA-014 依赖`GITHUB_TOKEN` Push隐式触发后续Gate

- **现象**：Codex Publish成功Push产品分支，但后续CI或Gate可能没有自动启动。
- **根因**：GitHub会抑制由仓库`GITHUB_TOKEN`产生的大多数递归事件，不能把普通Push当作可靠编排器。
- **修复**：Codex Publish显式发送`devflow_product_gate`，Product Gate合并后显式发送`devflow_post_merge`，最终通过`devflow_notify`完成通知。
- **预防规则**：多阶段Actions使用`workflow_dispatch`或`repository_dispatch`显式接力，并保留task-specific concurrency和幂等键。

## GHA-015 自动修复必须以Task Generation为预算单位

- **现象**：完全禁止第二次Codex会导致明确局部Gate失败仍需人工，而无限重试又会造成额度失控和错误循环。
- **根因**：没有区分“同一Agent会话无限循环”和“基于新失败证据创建一个新的受限修复代次”。
- **修复**：每个Task Generation保持一次Codex Session和零自动第二Session；Full/Post-Merge失败时最多创建一个继承原范围、Gate和风险政策的Recovery Generation。
- **预防规则**：预算必须同时限制Session、Generation、Root Cause和基础设施重试；任何自动恢复都不得扩大允许路径。

## GHA-016 Reusable Workflow边界未取得Environment Secrets

- **现象**：正式仓库`agent-runtime`中三个Secret名称和值均已配置；普通Job的安全presence探针全部为true，但本地`workflow_call`中的Secret-bearing Job连续报告Endpoint、Key和Model全部缺失，Forwarder和Codex均被跳过。
- **根因**：当前仓库运行环境下，Environment Secret在本地reusable workflow调用边界中的实际可见性与普通Job不同；继续重跑同一Workflow不会改变该边界。
- **修复**：把`environment: agent-runtime`直接绑定到入口`codex-task.yml`的普通只读Job；将可复用单元改为本地composite action，只通过显式inputs接收Key和Model；删除旧reusable workflow，并只通过显式`workflow_dispatch`运行默认分支的入口Workflow。
- **预防规则**：涉及Environment Secrets时必须先运行普通Job presence薄切片；Secret-bearing执行Job不得间接隐藏在未经真实验证的`workflow_call`边界中，复用优先使用composite action或已验证的直接Job模式。

## GHA-017 仓库Bot触发Codex未显式授权且绝对输出路径不稳定

- **现象**：Environment Preflight和localhost Forwarder已通过，官方Codex Action仍返回失败，未生成结构化结果，Scope Guard与Targeted Gate被跳过。
- **根因**：无人值守链由`github-actions[bot]`显式派发，而官方Action默认不允许Bot绕过写权限校验；同时流程把绝对`/tmp`路径作为`output-file` input，偏离官方相对路径与`final-message`输出模式。
- **修复**：仅授权`github-actions[bot]`，不开放任意用户或Bot；通过Output Schema约束`final-message`，Caller Job用环境变量和Python解析后写入工作区外的`/tmp/codex-result.json`。
- **预防规则**：Agent Action的触发者校验必须纳入薄切片；自动派发时显式列出可信Bot。模型输出先作为结构化Action output处理，不把绝对临时路径直接交给第三方Action。
""".strip()


def append_lessons(path: Path) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else "# 工程问题与复用经验集中记录\n"
    if "## GHA-012 原始Workflow失败直接升级为用户中断" in current:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(current.rstrip() + "\n\n" + LESSONS + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("docs/ENGINEERING_ISSUES_AND_LESSONS.md"),
    )
    args = parser.parse_args()
    changed = append_lessons(args.path)
    print(f"ENGINEERING_LESSONS_APPENDED={str(changed).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
