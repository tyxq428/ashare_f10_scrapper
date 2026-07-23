# Runbook：启动新任务

1. 读取根 `AGENTS.md`、本目录索引和活动任务列表。
2. 审计 `main`、开放 PR、共享文件和当前工作流。
3. 生成稳定 `task_id`，从最新 `main` 创建唯一活动分支。
4. 建立 `00_contract.md`、`01_master_plan.md`、`task_state.yaml`、`HANDOFF.md`、`DECISIONS.md`。
5. 在 `ACTIVE_TASKS.yaml` 登记任务、分支、阶段和 PR。
6. 由 ChatGPT Web Supervisor 预先创建唯一 `[TASK CONTROL] <task-id>` Issue，指派给 `tyxq428`，并把 Issue 编号写入 `task_state.yaml.notification.control_issue_number`。自动通知启用前必须完成这一步。
7. 写 `W00_plan.md`，再执行环境、权限、Secret 名称、网络和输出路径预检。
8. 建立 Draft PR；PR 描述引用 canonical task directory，不复制另一份状态。
9. 将任务拆成可独立验证的工作包；每包明确允许路径、禁止路径、Gate、失败分类和人工门槛。
10. 正常成功路径自动继续。只有根 `AGENTS.md` 定义的真实门槛才能暂停。
