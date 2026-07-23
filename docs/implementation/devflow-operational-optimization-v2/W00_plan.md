# W00 计划：基线、漂移审计与执行边界

## 目标

1. 固定 `main` 基线 `4f9fbdc0c46d334c2789e74d65a1b7921d02d23f`；
2. 确认无开放 PR；
3. 记录根 `AGENTS.md` 的 Low 文案与生产 `effort: xhigh` 的漂移；
4. 建立后续改动的完整路径清单；
5. 建立回滚与合并门禁。

## 只读审计范围

- `AGENTS.md` 与 scoped `AGENTS.md`；
- `docs/process/**`；
- `docs/process/templates/**`；
- `scripts/devflow/**`；
- `.github/actions/codex-thin-worker/action.yml`；
- `.github/workflows/test.yml`；
- `.github/workflows/e2e-688521.yml`；
- Devflow State/Product Gate/Post-Merge/Incident/Infrastructure workflows；
- `tests/test_devflow*.py`。

## 已确认漂移

```text
AGENTS.md: Codex ... low effort
生产Composite Action: effort: xhigh
```

## 预期输出

- `W00_result.md`；
- 更新 Canonical State 到 W01；
- `W01_plan.md`；
- 可追踪的第一批实现提交。

## Gate

- 当前分支由最新 `main` 创建；
- 无开放 PR；
- 计划文档先于实现；
- 不读取或输出任何 Secret；
- 不调用 Codex。
