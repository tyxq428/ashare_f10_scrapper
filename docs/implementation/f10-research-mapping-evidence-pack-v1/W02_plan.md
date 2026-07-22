# W02计划：Point-in-Time与文档版本链

## 目标

为官方报告发现、下载、解析和双源验证增加严格研究截止日，确保历史研究回放不会使用截止日后发布的更正版、季度报告或临时公告。

## 数据时间字段

```text
report_date / effective_at  事实所属期间
publish_date / published_at 文件发布日期
available_at                研究者最早可获得日期
retrieved_at                本次系统抓取时间
as_of_date                  本次任务允许使用的截止日
```

## 实施内容

1. 扩展`OfficialDocument`，生成稳定`document_id`、可得日和版本链字段；
2. 新增point-in-time工具，统一日期校验和版本选择；
3. `OfficialValidationRunner`和`FullCrossValidationRunner`接受`as_of_date`；
4. 官方报告查询的`end_date`使用`as_of_date`；
5. 同一报告期仅从截止日当时已发布的版本中选择优先级最高者；
6. 截止日后的更正版进入边界文档列表，不进入基线事实；
7. 解析缓存键加入文档哈希和截止日语义；
8. CLI新增`--as-of-date`；
9. 检查点和摘要记录研究截止日、排除文档和版本选择理由。

## 薄切片

- 原版在截止日前、更正版在截止日后：选择原版；
- 原版和更正版均在截止日前：选择更正版；
- 报告期在截止日前但文件尚未发布：不加载；
- 未提供截止日：使用运行当日，保持向后兼容。

## 验收标准

- 不发生截止日后的官方文档泄漏；
- 文档版本选择可解释、可追溯；
- 现有默认运行行为兼容；
- CLI、单元测试、Official Validation和E2E通过。

## 恢复入口

```yaml
phase: W02
checkpoint: W02_PLAN_COMMITTED
next_action: implement_point_in_time_document_selection
```
