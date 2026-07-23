from __future__ import annotations

import argparse
from pathlib import Path

LESSON_SECTIONS = (
    """## GHA-021 Agent指令与真实Codex运行强度漂移

- **现象**：根`AGENTS.md`仍声明Low，但正式Composite Action已经固定XHigh，后续Web或其他Agent可能按错误文档生成任务。
- **根因**：运行时、模板、Recovery生成器和人类可读指令没有共同的静态一致性门禁。
- **修复**：统一根指令、schema-v2模板、Recovery与Composite Action为XHigh；静态Workflow测试拒绝`effort: low`；schema-v1 Low仅只读兼容。
- **预防规则**：模型运行策略必须由版本化执行器强制，并在文档、模板和恢复生成器之间做确定性一致性检查。
""",
    """## GHA-022 XHigh没有Context Budget会放大固定上下文成本

- **现象**：即使是极小修改，Codex仍有固定系统、工具和多轮上下文开销；把聊天历史、完整SOP或过多文件交给XHigh会快速增加Token和时延。
- **根因**：只限制Session次数，没有在模型调用前约束任务文件数、字节数、日志和附加上下文。
- **修复**：引入schema-v2显式Context Budget，并在读取Relay Secret、启动Forwarder和调用模型前Fail Closed；结果进入Secret Audit、Manifest和Publish复核。
- **预防规则**：XHigh成本通过窄任务和确定性Context Budget控制，禁止静默降级推理强度或附加完整聊天/SOP绕过预算。
""",
    """## GHA-023 非产品改动重复运行完整Test和真实E2E

- **现象**：纯文档或Devflow规则修改也会安装全部依赖、执行完整pytest并抓取真实F10数据。
- **根因**：Workflow只按事件触发，没有根据累积diff区分docs、devflow和product影响。
- **修复**：新增`change_impact.py`；稳定Test/E2E Check按影响运行最小充分Gate，未知路径保守升级为product；只缓存pip依赖。
- **预防规则**：缓存只能加速依赖，Scope、Secret、Gate、main差异和Post-Merge结论必须每次重算；跳过必须是当前diff的显式PASS结论。
""",
    """## STATE-001 平台Core硬编码研究验收字段

- **现象**：通用执行框架把`research_acceptance_status`当作核心生命周期字段，其他项目无法表达自身验收语义。
- **根因**：平台执行状态与领域验收状态未分层。
- **修复**：State schema-v2引入`acceptance.domain/status/reason_code/details_path`与独立`security_status`；schema-v1映射为research只读兼容。
- **预防规则**：Core只理解执行、验收、安全、人工和Post-Merge；来源冲突等领域语义由Adapter扩展，执行成功且需复核不等于程序失败。
""",
    """## GIT-003 已完成任务的受管分支持续堆积

- **现象**：`task/codex-*`、`codex/*`、recovery和runtime分支在任务完成后保留，增加导航噪声和误操作风险。
- **根因**：流程保存了Run/SHA/Result，但没有显式分支生命周期和安全删除规划器。
- **修复**：新增fail-closed Branch GC，只处理受管前缀，并保护默认分支、活动任务、开放PR和未验证Merge SHA；第一阶段固定dry-run。
- **预防规则**：删除必须由确定性计划批准且幂等；非受管或无法证明安全的分支永不自动删除。
""",
    """## GHA-024 Devflow升级缺少固定兼容矩阵

- **现象**：收紧State或Task Descriptor schema时，可能破坏历史任务、重新打开DONE任务或让旧Low元数据影响新运行时。
- **根因**：兼容性依赖当前仓库偶然数据，没有不可变Fixture、迁移预览和独立Workflow。
- **修复**：增加v1/v2 State、v1 Low/v2 XHigh/v2非法Low Descriptor Fixture，验证非破坏幂等迁移、未知版本拒绝和effective XHigh。
- **预防规则**：Devflow核心升级必须通过独立Upgrade Compatibility Gate；历史元数据只读兼容，新执行策略由当前版本强制。
""",
)


def append_lessons(path: Path) -> bool:
    current = (
        path.read_text(encoding="utf-8")
        if path.exists()
        else "# 工程问题与复用经验集中记录\n"
    )
    additions: list[str] = []
    for section in LESSON_SECTIONS:
        heading = section.splitlines()[0]
        if heading not in current:
            additions.append(section.strip())
    if not additions:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        current.rstrip()
        + "\n\n"
        + "\n\n".join(additions)
        + "\n",
        encoding="utf-8",
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(
            "docs/ENGINEERING_ISSUES_AND_LESSONS.md"
        ),
    )
    args = parser.parse_args()
    changed = append_lessons(args.path)
    print(
        "ENGINEERING_LESSONS_APPENDED="
        f"{str(changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
