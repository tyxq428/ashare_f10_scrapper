# W01 计划：Environment 平台保护确认

## 唯一人工动作

在 GitHub 仓库页面执行：

```text
Settings
→ Environments
→ agent-runtime
```

确认或配置：

1. **Required reviewers**：添加 `tyxq428`；
2. 单维护者仓库不要勾选 **Prevent self-review**，否则同一账号发起的任务无法批准；若未来增加第二位可信维护者，再开启该选项；
3. 若页面提供 **Allow administrators to bypass configured protection rules**，将其关闭；
4. **Deployment branches and tags**：改为 Selected branches and tags，仅允许 `main`；
5. 不打开、不复制、不修改三个 Environment Secret 的值。

## 完成确认

用户只需回复：

```text
agent-runtime 已配置 Required Reviewer=tyxq428、仅允许 main，并已关闭可用的管理员绕过；未读取或修改 Secret。
```

## 恢复入口

收到确认后：

- 不运行 Relay Health；
- 不运行 Secret Audit；
- 不运行 Responses 探针；
- 不运行 Codex；
- 仅更新 W01/W02 结果、FINAL_REPORT、STATUS、HANDOFF 与 ACTIVE_TASKS。
