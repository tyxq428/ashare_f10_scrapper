# W07 计划：一次性 Grant、原子预占与 Activation PR

## 实施

Grant 绑定任务 SHA、Descriptor Digest、Source Run、Source SHA、失败指纹、Allowed Files Hash 和签发者；TTL 不超过 60 分钟，`max_calls=1`。模型前写入 `RESERVED`，一旦预占，无论成功、失败、取消或超时都视为已消耗。

长期 `codex-task.yml` 保持无模型；用户明确批准具体任务后，由独立受审的一次性 Activation PR 临时加入模型 Job，执行一次后删除并恢复 `disabled`。

## 验收

重复 Dispatch、GitHub Re-run、不同分支同指纹和已消费 Grant 均不能进入模型。
