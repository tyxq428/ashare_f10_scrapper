# 决策记录

## D-001｜Codex 默认禁用

Codex 不是默认执行器。ChatGPT Web 和确定性 Actions 是正常路径；任务完成后仍保持全局禁用。

## D-002｜禁止自动模型链路

Bot、Auto Recovery、State Consistency、Post-Merge、Workflow failure 和 failed-job rerun 均不得创建、派发或重跑 Codex Session。

## D-003｜显式资格不等于立即执行

即使将来用户明确授权且资格检查通过，当前 `codex-task.yml` 仍只记录候选，不包含模型 Job。任何重新启用都必须经过独立受审 PR 和用户再次明确要求。

## D-004｜影响感知但最终完整验证

日常 PR 根据 `docs_only / devflow_only / product` 选择最小 Gate；合并前仍强制一次完整 Test 和真实 E2E。

## D-005｜状态解耦

Core 使用 `execution_status`、通用 `acceptance` 和 `security_status`；投研领域语义通过 acceptance domain 扩展。

## D-006｜Branch GC Fail Closed

默认 `execute=false`，只对受管前缀生成删除计划；无法证明已合并、仍有开放 PR、属于活动任务或未知分支时一律保留。
