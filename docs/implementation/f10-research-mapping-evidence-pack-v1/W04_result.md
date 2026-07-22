# W04结果：Canonical Research Ontology与Fact Lineage

## 状态

```yaml
phase: W04
status: COMPLETED
last_successful_step: canonical_observations_and_lineage_verified
next_action: W05_unified_evidence_graph
human_intervention_required: false
```

## 完成内容

1. 新增`ashare_f10.research_mapping`包。
2. 建立四层模型：

```text
Source Fact
→ Canonical Observation
→ Research View
→ Fact Lineage
```

3. 新增稳定ID：
   - `source_fact_id`
   - `observation_id`
   - `lineage_id`
4. 建立v1研究指标本体，覆盖：
   - 公司主表；
   - 三张表；
   - 盈利质量；
   - 研发；
   - 股本和筹码；
   - 治理和事件；
   - 市场与一致预期。
5. 未显式映射的字段不会丢失，而是进入稳定fallback metric：

```text
source.<family>.<field_key>
```

6. 统一金额单位至元，并保留原始单位和值。
7. Canonical Observation唯一键包含：

```text
证券代码 | metric_id | 报告期 | 事件日 | period_type | data_semantics | scope
```

确保年度累计、独立季度、时点值和事件不会混合。
8. 来源优先级：官方直接披露 > 官方派生 > 东方财富直接事实 > 平台特有事实。
9. 多来源一致时标记`VERIFIED_MULTI_SOURCE`。
10. 单来源时标记`SINGLE_SOURCE`。
11. 可用来源存在差异时标记`SOURCE_CONFLICT`，规范值留空，不静默选值。
12. `PARSE_SUSPECT`事实保留于Source Fact和Lineage，但不会被选为规范事实。
13. 生成九类Research View。

## 薄切片结果

| 场景 | 结果 |
|---|---|
| 官方营业收入＋东方财富营业收入 | 汇聚为一个多源验证事实 |
| 万元与元 | 正确归一 |
| FY与Q4 | 保持两个独立观察值 |
| 高优先级来源冲突 | `SOURCE_CONFLICT`，不补值 |
| 可疑官方解析 | 保留但隔离 |
| 未映射字段 | 进入coverage_and_gaps |
| 截止日后事实 | 排除 |
| 重复运行 | ID稳定 |

## 自动验证

| Workflow | Run | 结果 |
|---|---:|---|
| Test | 551 | success |
| E2E 688521 | 196 | success |
| Official Validation 688521 | 148 | success |
| Raw Pack 688521 E2E | 48 | success |

## 质量指标

```yaml
new_mapping_tests: 6
source_fact_loss: 0
canonical_duplicate_keys: 0
silent_conflict_resolution: 0
failed_tests: 0
blocking_items: 0
```

## 后续

W05将把官方报告、Raw Pack文档、Source Fact、Canonical Observation和页级证据统一为一个Evidence Graph，使研究视图可以逐层穿透到原始PDF、网页快照、页码、原始行和SHA-256。
