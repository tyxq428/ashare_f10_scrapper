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

## GHA-018 移动的main被误算为候选分支越界修改

- **现象**：Codex、Scope Guard、Targeted Gate和Publish全部通过，产品分支只修改获准的两个文件；Product Gate却在Full Gate前报告Scope失败。
- **根因**：初始产品范围使用`git diff origin/main HEAD`。候选生成后`main`新增了观察/编排提交，双点Diff把`main`独有变化也算入候选差异。
- **修复**：先验证`expected_base_sha`是候选祖先，再以`git merge-base origin/main HEAD`作为初始范围基线；合并前rebase到最新main后，再以`origin/main..HEAD`重跑范围和Full Gate。
- **预防规则**：异步候选分支的初始差异必须相对共同祖先或固定批准基线计算，不能直接与移动主分支做双点Diff；真实Scope失败仍须Fail Closed。

## GHA-019 Product Gate未配置Git提交身份导致假人工门槛

- **现象**：Scope和Full Gate均通过，低风险候选进入自动合并后出现`Committer identity unknown`，系统错误发送`AUTO_MERGE_BLOCKED`人工通知。
- **根因**：Runner执行`git rebase`/`git merge --no-ff`前没有固定`user.name`和`user.email`；同时Product Gate直接通知，没有先交给统一恢复分类。
- **修复**：合并步骤固定使用`github-actions[bot]`提交身份；失败时Fail Closed并交给Auto Recovery。只有真实冲突、branch protection或权限拒绝才分类为`HUMAN_REQUIRED`。
- **预防规则**：任何在Runner创建Commit的步骤都必须显式配置Git身份；机械配置缺失不得升级为用户决策。

## GHA-020 Codex推理强度策略与历史Descriptor兼容

- **现象**：正式Thin Worker长期硬编码`effort: low`，与后续任务要求的最高推理强度不一致；直接收紧Schema又会使已发布历史控制分支无法继续Gate。
- **根因**：运行时策略、任务模板和历史元数据没有分层。
- **修复**：正式Action固定`effort: xhigh`，新模板和Recovery Generation写入`reasoning_effort: xhigh`；Schema v1只读兼容历史`low`，但历史值不能降低实际运行强度。
- **预防规则**：模型运行强度由版本化执行器强制；元数据迁移必须避免无意义重跑已经通过G1的历史候选。
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
