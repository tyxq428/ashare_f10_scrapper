# W00 计划：基线、权限与安全预检

## 目标

在不修改现有投研业务逻辑的前提下，为 `ChatGPT Web Supervisor + GitHub Actions Executor + Codex Thin Worker` 正式改造建立可追溯基线、任务合同、唯一状态源和安全边界。

## 基线

- 仓库：`tyxq428/ashare_f10_scrapper`
- 默认分支：`main`
- 启动基线提交：`75a5b93b047bd844fc5d0b7950507cba746fdd50`
- 工作分支：`feature/chatgpt-web-codex-devflow-v1`
- 任务 ID：`chatgpt-web-codex-devflow-v1`

## 本阶段动作

1. 审计开放 PR、活动分支与共享 Workflow 路径；
2. 建立任务合同、主计划、`task_state.yaml`、`HANDOFF.md` 和 `DECISIONS.md`；
3. 确认正式 Environment 只通过 Secret 名称引用，不读取或公开 URL、Key、模型值；
4. 固定角色边界：Secret-bearing Codex Job 只读，Secret-free Publish Job 才能写仓库；
5. 记录当前 Test、重试、心跳、工程经验库的可复用能力；
6. 定义 W01—W08 的连续执行和人工介入条件。

## 禁止事项

- 不在仓库、日志、Artifact、Issue 或 PR 中写入真实中转站 URL、域名、Key 或模型 ID；
- 不修改 F10、Raw Pack、官方验证、Research Pack 的业务语义；
- 不使用 `pull_request_target` 执行不可信代码；
- 不让持有中转站 Secret 的 Job 同时拥有仓库写权限；
- 不因普通 PASS、阶段自然结束或可自动恢复错误暂停。

## 验收标准

- 分支从指定 `main` 基线创建；
- 当前没有开放 PR 与本任务发生不可自动解决的路径冲突；
- 任务状态和恢复入口已持久化；
- 安全边界、Gate、通知与 post-merge 要求写入主计划；
- 若 Environment Secret 缺失，后续健康检查必须安全进入 `WAITING_HUMAN`，不得打印值。

## 恢复入口

```yaml
phase: W00
checkpoint: W00_PLAN_COMMITTED
next_action: materialize_contract_state_and_layered_process
human_intervention_required: false
```
