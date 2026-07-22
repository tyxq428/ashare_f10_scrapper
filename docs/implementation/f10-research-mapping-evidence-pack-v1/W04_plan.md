# W04计划：Canonical Research Ontology与Fact Lineage

## 目标

将东方财富宽覆盖源事实和官方披露事实映射为稳定、可复用的研究事实层，同时完整保留每条源记录和证据血缘。

## 四层数据模型

```text
Source Fact
→ Canonical Observation
→ Research View
→ Evidence / Lineage
```

### Source Fact

忠实保存每个接口或官方解析器的事实，不因规范化而删除原始记录。

### Canonical Observation

同一经济指标、公司、期间、口径和范围只形成一个规范观察值；官方直接披露优先于平台事实，但冲突不会被静默覆盖。

### Research View

按研究用途组织规范事实：

- company_master
- financial_statements
- quarterly_and_ttm
- profit_quality
- segments_and_kpis
- capital_structure
- governance_and_events
- market_and_consensus
- coverage_and_gaps

### Fact Lineage

记录规范观察值由哪些源事实支持、哪个事实被选中、选择理由和证据身份。

## 实施内容

1. 新增`research_mapping`包；
2. 新增稳定ID：`source_fact_id`、`observation_id`、`lineage_id`；
3. 建立v1研究指标本体和字段别名；
4. 对未显式映射字段生成稳定fallback metric，不丢字段；
5. 统一单位、期间、数据语义、范围和来源状态；
6. 建立来源优先级：官方直接、官方派生、平台直接、平台特有；
7. 多来源一致时形成`VERIFIED_MULTI_SOURCE`；
8. 同优先级或关键来源冲突时形成`SOURCE_CONFLICT`，不静默覆盖；
9. 保留所有候选源事实和选择理由；
10. 生成按研究模块拆分的DataFrame视图。

## 薄切片

- 营业收入在主表、主要指标和官方利润表重复出现；
- 归母净利润在不同数据集重复出现；
- 年度累计与Q4单季度不得合并；
- 官方直接值优先于东方财富值；
- 两个高优先级官方值冲突时进入`SOURCE_CONFLICT`；
- 未映射字段保留为fallback metric。

## 验收标准

- 稳定ID重复运行不变化；
- Source Fact数量不因映射减少；
- Canonical Observation唯一键无重复；
- 年度、累计季度、独立季度和时点值不混用；
- 每个规范事实至少有一条lineage；
- 冲突可见且不会被低质量来源覆盖；
- 单元测试和现有回归流程通过。

## 恢复入口

```yaml
phase: W04
checkpoint: W04_PLAN_COMMITTED
next_action: implement_canonical_ontology_mapper_and_lineage
```
