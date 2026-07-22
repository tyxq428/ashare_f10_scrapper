# W02结果：Point-in-Time与文档版本链

## 状态

```yaml
phase: W02
status: COMPLETED
last_successful_step: point_in_time_selection_and_version_lineage_verified
next_action: W03_reconciliation_semantics_and_quality_metrics
human_intervention_required: false
```

## 完成内容

1. `OfficialDocument`新增稳定文档身份与时点字段：
   - `document_id`
   - `effective_at`
   - `available_at`
   - `retrieved_at`
   - `supersedes_document_id`
   - `is_boundary`
2. `OfficialFact`新增文档和事实时点血缘字段。
3. 新增`select_report_versions`：只从`available_at <= as_of_date`的版本中选择。
4. 更正版在截止日前可得时优先；在截止日后发布时进入`boundary_documents`，不进入基线事实。
5. `OfficialValidationRunner`和`FullCrossValidationRunner`均支持`as_of_date`。
6. CLI新增：

```text
validate-official --as-of-date YYYY-MM-DD
run-and-validate --as-of-date YYYY-MM-DD
```

7. 检查点、摘要和来源状态记录截止日、版本选择决策、边界文档和缺失报告期。
8. 解析缓存版本提升至`1.7.0`，兼容新增事实元数据。

## 薄切片结果

| 场景 | 预期 | 结果 |
|---|---|---|
| 原版在截止日前、更正版在截止日后 | 选原版，更正版列为边界 | 通过 |
| 原版和更正版均在截止日前 | 选更正版，记录supersedes | 通过 |
| 报告尚未发布 | 标记截止日缺失，不使用未来文件 | 通过 |
| 未传截止日 | 默认运行当日，兼容旧行为 | 通过 |

## 自动验证

| Workflow | Run | 结果 |
|---|---:|---|
| Test | 496 | success |
| E2E 688521 | 170 | success |
| Official Validation 688521 | 122 | success |
| Raw Pack 688521 E2E | 22 | success |

## 质量指标

```yaml
point_in_time_tests: 4
failed_tests: 0
workflow_failures_after_fix: 0
lint_rework: 1
blocking_items: 0
```

首次CI发现`Iterable`应从`collections.abc`导入，属于确定性Lint问题；修复后所有流程通过。

## 后续

W03将拆分覆盖率与准确率，增加指标级比较方法、绝对/相对容差和状态根因统计，避免将官方解析覆盖不足误读为数据不准确。
