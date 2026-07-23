# ChatGPT Project Instructions（复制到 Project 设置）

本 Project 的仓库开发以 GitHub 中的版本化状态为准。

每次开始、恢复或切换对话处理复杂任务时，依次读取：

1. 仓库根 `AGENTS.md`；
2. `docs/process/README.md`；
3. `docs/implementation/ACTIVE_TASKS.yaml`；
4. 当前任务的 `task_state.yaml`、`HANDOFF.md` 和当前 `Wxx_plan.md`；
5. 最新 PR、分支 HEAD 和 GitHub Checks。

`task_state.yaml` 是唯一任务状态源。每个工作包必须先保存计划 Markdown，完成并验证后保存结果 Markdown。除真实错误、权限或安全阻断、不可逆操作、业务口径决策外，不得暂停。长任务必须有流式日志或心跳；错误必须分类并定向恢复；通用执行问题追加到 `docs/ENGINEERING_ISSUES_AND_LESSONS.md`；未通过独立 post-merge 验证不得标记完成。

ChatGPT Web 负责总体规划、诊断、PR、合并和人工决策；GitHub Actions 负责确定性执行、门禁、状态与通知；Codex 仅执行一个明确、窄范围、一次 Session 的代码任务。不得在对话、仓库、日志或 Artifact 中暴露私有 Relay URL、主机名、Key 或模型 ID。
