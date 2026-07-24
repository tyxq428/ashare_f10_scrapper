# W02 计划：Recovery Generation 永久归零

## 实施

- Schema v2 要求 `max_recovery_generations=0`；
- Schema v1 历史值可读，但有效值固定为 0；
- 删除生产 `recovery_task.py`，改为无执行权限的 Web 重规划资料生成器或完全移除；
- 更新模板、Runbook、Policy 和 Upgrade Compatibility。

## 验收

所有 Descriptor 的有效 Recovery Generation 上限为 0；没有脚本可自动创建或派发 Recovery Task。
