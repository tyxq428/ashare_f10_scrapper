# 影响感知 Gate 与安全缓存政策

## 目标

减少纯文档和 Devflow 基础设施改动对完整业务回归与真实网络 E2E 的重复消耗，同时保证未知或混合改动不会漏测。

## 影响分类

`change_impact.py` 是唯一确定性分类入口：

| 影响级别 | 典型路径 | 最小充分 Gate |
|---|---|---|
| `docs_only` | `README.md`、普通 `docs/**/*.md` | 文档链接、JSON-as-YAML、状态格式 |
| `devflow_only` | `AGENTS.md`、`docs/process/**`、`scripts/devflow/**`、Devflow/Codex Workflow | 文档、状态、Workflow 静态安全、Devflow Ruff/pytest、升级兼容 |
| `product` | `src/**`、业务测试、业务脚本、未知路径 | 完整 Test、真实 E2E、exact-main 关键回归 |

分类遵循保守升级：

- 任意未知路径按 `product`；
- 混合改动取最高影响级别；
- 空 diff 执行安全的 `devflow_only` Gate；
- 手工派发可以强制完整 Test 或真实 E2E，但不能强制降低 Gate。

## 稳定 Check

`Test` 与 `E2E 688521` 始终产生稳定的 GitHub Check：

- 不需要完整回归时，Workflow 明确记录影响分类和“有意跳过真实产品执行”的 PASS；
- 不复用旧 Run 的 Scope、Secret Audit、Gate 或 Post-Merge 结论；
- 跳过是当前 diff 的确定性结论，不是缓存命中。

## 允许缓存

只允许缓存可重新生成、不会代表安全或验收结论的依赖：

- pip 下载和 wheel；
- npm 下载缓存；
-稳定的模型 Prompt 前缀由上游平台自行缓存。

缓存键必须由受信依赖清单形成，例如 `pyproject.toml`。

## 禁止缓存

以下内容每次必须重新计算：

- changed-path Scope；
- Secret Audit；
- Artifact Manifest；
- 当前 `main` 的 Merge Base；
- Targeted、Full、E2E 和 Post-Merge 结论；
- Canonical State 一致性；
- 人工门槛和恢复预算判断。

## Fail Closed

分类脚本、基线 SHA 或路径读取失败时，不得静默降级为 docs-only；应失败或按 `product` 处理。
