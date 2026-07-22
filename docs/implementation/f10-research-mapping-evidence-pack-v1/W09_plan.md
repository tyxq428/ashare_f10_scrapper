# W09计划：Research Pack API与可视化消费契约

## 目标

在W08数据契约稳定后，以独立Research Pack路由和页面对接现有Web入口，不修改现有任务执行核心；展示覆盖、准确率、证据、时点和版本链，并支持`thin-slice`与`research-full`两种模式。

## 实施范围

1. 新增`/api/research-pack`稳定路由；
2. 支持从最新F10运行目录生成Research Pack任务；
3. `thin-slice`只验证最近两个报告期，`research-full`验证全部可用报告期；
4. 提供概览、规范事实筛选、来源状态筛选、证据穿透、文档版本链和Artifact下载；
5. 新增独立Research Pack页面，避免与可视化执行中心共享可变状态；
6. 新增API与静态页面回归测试；
7. 与最新`main`同步后执行最终全量回归。

## 验收标准

- UI分别展示分类覆盖、比较覆盖、比较准确率和证据完整度；
- 可筛选`PARSE_SUSPECT`、`SOURCE_CONFLICT`和`UNRESOLVED`；
- 点击规范事实可返回source fact、原始文档和证据位置；
- 展示`as_of_date`、文档版本标签和`SUPERSEDES`关系；
- 两种运行模式均写入任务状态和检查点；
- 原F10、Raw Pack、Cross Validation和Visual Execution API不破坏；
- Test、W08矩阵、688521官方验证和最终合并回归全部通过。

## 恢复入口

```yaml
phase: W09
checkpoint: W09_PLAN_COMMITTED
next_action: implement_research_pack_api_and_ui
```
