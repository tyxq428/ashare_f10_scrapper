# W03结果：对账语义、指标级容差与质量指标

## 状态

```yaml
phase: W03
status: COMPLETED
last_successful_step: semantic_comparison_and_quality_metrics_verified
next_action: W04_canonical_research_ontology_and_lineage
human_intervention_required: false
```

## 完成内容

1. 新增指标级比较策略：
   - `numeric`
   - `percentage`
   - `per_share`
   - `integer`
   - `date`
   - `text`
   - `set`
2. 字段注册表条目新增：
   - `comparison_method`
   - `canonical_unit`
   - `absolute_tolerance`
   - `relative_tolerance`
   - `display_decimals`
3. 数值比较不再统一使用一元阈值，而是采用：

```text
允许误差 = max(官方展示精度, 字段绝对容差, 数值规模 × 相对容差)
```

4. 金额统一归一至元；EPS、百分比和整数分别采用独立容差。
5. 日期执行规范日期比较，名单执行集合比较，普通文本执行规范化文本比较。
6. 每条比较记录新增：
   - 实际比较方法；
   - 根因；
   - 绝对容差；
   - 相对容差。
7. 质量摘要拆分为：
   - `comparison_coverage`
   - `comparison_accuracy`
   - `target_extraction_coverage`
   - `evidence_completeness`
   - `unresolved_rate`
   - `root_cause_counts`
8. 旧`comparable_match_rate`保留为`comparison_accuracy`兼容别名，并明确标记deprecated。
9. Test工作流增加可下载的Pytest诊断包，后续失败可直接从Artifact恢复排查。

## 指标语义

```text
comparison_accuracy
= 成功匹配 /（成功匹配 + 真实冲突）

comparison_coverage
= 已真正完成比较 / 应进入比较的事实
```

因此“548项匹配、0项真实冲突”的准确率语义为100%；低覆盖率仍通过独立覆盖指标如实展示，不再被误读为数据准确率低。

## 薄切片结果

| 场景 | 结果 |
|---|---|
| 亿元与元归一 | 通过 |
| 大额金额相对容差 | 通过 |
| 百分比基点容差 | 通过 |
| 每股指标小数容差 | 通过 |
| 日期规范化 | 通过 |
| 名单集合比较 | 通过 |
| 缺失官方事实只降低覆盖率 | 通过 |
| 未加载报告期不进入准确率分母 | 通过 |

## 问题排查

首次测试失败原因：旧回归测试只提供`status`列，质量汇总直接读取证据列导致`KeyError`。

修复方式：质量汇总对稀疏诊断Frame使用带索引的默认Series，保持API和历史测试兼容。修复后全套测试通过。

## 自动验证

| Workflow | Run | 结果 |
|---|---:|---|
| Test | 528 | success |
| E2E 688521 | 184 | success |
| Official Validation 688521 | 136 | success |
| Raw Pack 688521 E2E | 36 | success |

## 质量指标

```yaml
new_policy_tests: 5
existing_regression_tests: passed
failed_tests_after_fix: 0
workflow_failures_after_fix: 0
blocking_items: 0
```

## 后续

W04将把东方财富源事实和官方源事实映射为稳定的Canonical Fact，并建立Source Fact、Canonical Observation、Research View和Fact Lineage四层模型。
