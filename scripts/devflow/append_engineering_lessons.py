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
