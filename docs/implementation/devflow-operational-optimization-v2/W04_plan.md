# W04 计划：受管分支垃圾回收

## 目标

为框架创建的控制、产品、恢复和观察分支建立 fail-closed 生命周期管理，第一阶段只执行 dry-run。

## 实施范围

- `scripts/devflow/branch_gc.py`；
- `.github/workflows/devflow-branch-gc.yml`；
- Post-Merge dry-run dispatch；
- 单元测试和 Runbook。

## 验收

- 只识别 `task/codex-*`、`codex/*`、`recovery/*`、`runtime/*`；
- 默认分支、活动任务、开放 PR、未验证 Merge SHA 和非受管分支始终保留；
- 默认 `execute=false`；
- 重复删除已不存在分支为幂等完成；
- 不访问 Relay Secrets，不发送普通成功邮件。
