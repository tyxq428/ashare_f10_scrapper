# W01 计划：分层 SOP 与 AGENTS

## 目标

把 SOP v2 的长期规则拆为短根指令、Scoped `AGENTS.md`、Policies、Runbooks、Templates 和 Project Instructions，避免每次对话或 Codex Session 重复全文。

## 范围

- 根 `AGENTS.md`；
- `.github/`、`scripts/devflow/`、`validation/`、`tests/` scoped rules；
- `docs/process/**`。

## Gate

- 所有索引链接存在；
- 根文件保持短小；
- 规则无冲突；
- 不包含动态状态或 Secret；
- 数据语义和非错误不暂停规则保留。
