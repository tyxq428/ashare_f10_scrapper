# Runbook：Devflow 升级兼容

## 目的

执行器、State、Task Descriptor、Workflow 或模板升级前，先证明旧任务仍可读、新任务不会降级、已完成任务不会被重新打开。

## 固定兼容矩阵

`tests/fixtures/devflow/` 保存最小不可变 Fixture：

- schema-v1 已完成 State；
- schema-v2 运行中 State；
- schema-v1 Low Descriptor；
- schema-v2 XHigh Descriptor；
- 必须拒绝的 schema-v2 Low Descriptor。

`upgrade_compatibility.py` 验证：

1. v1/v2 State 均可读取；
2. 历史 v1 `low` 元数据不会降低实际运行时 `xhigh`；
3. v2 Descriptor 必须显式 `xhigh` 和 Context Budget；
4. v2 Low 必须 Fail Closed；
5. v1→v2 State 迁移预览不修改输入、可重复执行且保持 `DONE`；
6. 未知 State/Descriptor schema 均被拒绝。

## 迁移原则

- 迁移器先生成预览，不直接覆盖历史证据；
- 已完成任务保持 `DONE`、Post-Merge PASS 和原 Run/SHA；
- 历史字段只读兼容，不决定新运行时政策；
- 新 Recovery Generation 使用当前 schema 和 XHigh；
- 未知版本不做猜测性转换。

## Workflow

`Devflow Upgrade Compatibility` 在核心脚本、模板、Fixture 和相关测试变化时运行。失败时上传仅含兼容矩阵的有界 Artifact，不包含 Prompt、源代码正文或 Secret。

## 发布门槛

任何 Devflow 版本升级都必须同时通过：

```text
State Consistency
Workflow Static Policy
Upgrade Compatibility
Devflow Unit Tests
exact-main Infrastructure Post-Merge
```
