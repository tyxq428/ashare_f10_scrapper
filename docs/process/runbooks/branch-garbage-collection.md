# Runbook：受管分支垃圾回收

## 适用范围

只处理框架创建并可由命名规则识别的分支：

```text
task/codex-*
codex/*
recovery/*
runtime/*
```

`feature/*`、`fix/*`、默认分支和无法证明归属的分支永不由该 Workflow 删除。

## 默认流程

任务通过 exact-main Post-Merge 后，`Devflow Post Merge` 派发一次：

```text
devflow_branch_gc
execute: false
```

`Devflow Branch Garbage Collection` 随后：

1. 校验 task/publish 分支名称和 40 位 Merge SHA；
2. 读取 `ACTIVE_TASKS.yaml`；
3. 获取开放 PR 的 head 分支；
4. 验证 Merge SHA 已在 `origin/main` 祖先链；
5. 生成 `branch-gc-plan.json`；
6. 默认只写 Job Summary 和 Artifact，不删除远端分支。

## 删除模式

只有人工或后续版本化政策显式传入：

```yaml
execute: true
```

才会删除规划器标记为 `DELETE` 的分支。删除前仍会检查远端分支是否存在；重复运行时已不存在的分支被视为幂等完成。

## 必须保留

出现以下任一条件时必须 `KEEP`：

- 默认分支；
- 非受管前缀或非法名称；
- 活动任务引用；
- 开放 PR head；
- Merge SHA 无法验证；
- 规划器或 GitHub 元数据读取失败。

## 通知

垃圾回收成功、dry-run 和已不存在分支均保持静默，不创建邮件。只有权限或安全边界无法确定时才由正常恢复策略处理。
