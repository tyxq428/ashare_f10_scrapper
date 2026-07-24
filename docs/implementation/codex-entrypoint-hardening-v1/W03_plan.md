# W03 计划：Pre-model 与不可重跑 Model Job 边界

## 实施

- Auto Recovery 不再监听 Codex Task；
- 基础设施重试只允许发生在模型调用前；
- 定义一次性 Grant 状态 `ISSUED → RESERVED → CONSUMED`；
- 进入 `RESERVED` 后，GitHub Re-run、重复 Dispatch、超时、取消或 Artifact 失败均不得再次启动模型。

## 验收

`model_job_rerunnable=false`；通用 `rerun-failed-jobs` 永远不能覆盖 Model-bearing Job。
