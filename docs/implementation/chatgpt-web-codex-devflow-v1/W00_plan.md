# W00 计划：基线、权限与安全预检

## 目标

从最新 `main` 建立唯一开发分支，固定任务合同、canonical state、角色边界和正式 Environment Secret 名称，不触碰投研业务逻辑。

## 动作

1. 审计开放 PR、主分支和共享 Workflow；
2. 建立任务目录和活动任务索引；
3. 固定 Secret Job 只读、Publish Job 无 Secret；
4. 定义 Relay URL/Key/模型不得进入 Public 内容；
5. 定义连续执行和人工门槛。

## Gate

G0：分支、合同、状态、安全约束和无并行冲突。

## 恢复入口

```yaml
phase: W00
checkpoint: W00_PLAN_COMMITTED
next_action: establish_contract_and_state
human_intervention_required: false
```
