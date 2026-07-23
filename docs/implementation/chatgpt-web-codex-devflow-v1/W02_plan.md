# W02 计划：Canonical State 与一致性引擎

## 目标

建立唯一机器可读任务状态、活动任务索引、状态渲染和确定性一致性检查，消除 PR、README、阶段文档和聊天进度漂移。

## 检查项

- 必需字段和合法状态；
- 同一任务一个活动分支；
- 合同、主计划、HANDOFF 和当前计划存在；
- 已完成阶段有对应结果；
- `DONE` 需要 post-merge PASS；
- `WAITING_HUMAN` 需要最小人工动作与恢复入口；
- execution 与 research acceptance 分离；
- 产品提交采用祖先关系，不保存自引用 HEAD。

## Gate

G0/G1：状态脚本单元测试和当前任务一致性。
