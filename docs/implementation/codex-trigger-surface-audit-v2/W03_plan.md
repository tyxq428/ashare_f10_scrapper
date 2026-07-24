# W03 计划：永久触发面守卫

## 目标

- 全仓 Workflow 扫描直接和间接模型入口；
- 维护唯一 eligibility-only `Codex Task`；
- 定期及新建 `task/codex-*` 分支时运行历史 Re-run 审计；
- 验证所有 Agent Runtime Workflow 与机器清单一致；
- 新增回归测试覆盖：
  - 历史分支 Descriptor 未移除；
  - 历史分支 Action仍包含模型引用；
  - Relay Health被 Auto Recovery监听；
  - Secret Audit在来源验证前绑定 Environment；
  - 任何永久 Workflow包含 Forwarder或模型 Action。

## Gate

`validate_codex_entrypoints.py`、Workflow Validator、Ruff 和所有 Devflow tests 必须 PASS。
