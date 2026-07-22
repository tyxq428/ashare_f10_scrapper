# 目标架构：F10研究映射包与官方原文证据包

> 本文定义目标数据契约和模块边界。  
> 当前阶段不实施代码。

## 1. 总体架构

```text
                         ┌──────────────────────────┐
                         │ 研究任务变量 / as_of_date │
                         └─────────────┬────────────┘
                                       │
          ┌────────────────────────────┼─────────────────────────────┐
          │                            │                             │
          ▼                            ▼                             ▼
┌──────────────────┐        ┌────────────────────┐       ┌────────────────────┐
│ F10结构化源       │        │ 法定披露与公司官方源 │       │ 政府/监管/行业官方源 │
│ Eastmoney等       │        │ SSE/SZSE/CNINFO/IR │       │ CSRC/法院/政府等     │
└────────┬─────────┘        └─────────┬──────────┘       └─────────┬──────────┘
         │                              │                            │
         ▼                              ▼                            ▼
┌──────────────────┐        ┌────────────────────┐       ┌────────────────────┐
│ Source Facts      │        │ Document Registry  │       │ Document Registry  │
│ 保留全部原始字段   │        │ 原始文件/版本/哈希   │       │ 原始文件/版本/哈希   │
└────────┬─────────┘        └─────────┬──────────┘       └─────────┬──────────┘
         │                              └────────────┬───────────────┘
         │                                           ▼
         │                                ┌────────────────────┐
         │                                │ Evidence Extraction │
         │                                │ 页/表/行/文本/置信度 │
         │                                └─────────┬──────────┘
         │                                          │
         └───────────────────┬──────────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ Canonical Fact Layer │
                  │ 本体、口径、时点、版本 │
                  └──────────┬───────────┘
                             │
             ┌───────────────┼────────────────┐
             ▼               ▼                ▼
      ┌────────────┐  ┌──────────────┐  ┌────────────────┐
      │ Reconcile  │  │ Derived Facts │  │ Coverage/Gaps  │
      │ 双源/多源对账│  │ 公式/单季/TTM │  │ 缺口/冲突/可疑 │
      └──────┬─────┘  └──────┬───────┘  └────────┬───────┘
             └───────────────┼────────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ Research Mapping Pack│
                  │ 财务/KPI/股本/治理等  │
                  └──────────────────────┘
```

## 2. 五层数据模型

## 2.1 L0：原始文件和响应

只读保存：

- F10原始HTTP响应；
- 官方PDF/HTML；
- 官方查询响应；
- 下载请求与响应头；
- 原始URL和最终URL；
- 文件SHA-256；
- 抓取时间；
- HTTP状态和权限状态。

原则：原始材料永不被清洗结果覆盖。

## 2.2 L1：源事实（Source Facts）

每条源记录忠实保留来源形态，不去重为单一经济事实。

建议主键：

```text
source_fact_id = hash(
  source_id |
  security_code |
  source_record_id |
  field_key |
  report_date/event_date |
  source_version
)
```

核心字段：

```text
source_fact_id
security_code
source_id
source_tier
source_family
source_dataset
source_record_id
source_field_key
source_field_name
raw_value
value_num
value_text
raw_unit
report_date
event_date
published_at
available_at
extracted_at
source_url
document_id
source_page
source_row
source_status
```

## 2.3 L2：证据对象（Evidence Objects）

一个证据对象说明“事实为何可以被相信或为何需要怀疑”。

建议主键：

```text
evidence_id = hash(document_sha256 | page | region/table/line | text_hash)
```

字段：

```text
evidence_id
document_id
document_sha256
canonical_url
package_relative_path
document_title
document_type
report_kind
report_date
published_at
available_at
version_label
supersedes_document_id
source_tier
page_number
page_width/page_height
bbox
line_start/line_end
table_id
row_index/column_index
raw_text
normalized_text
text_sha256
extraction_method
parser_version
parser_options_hash
target_registry_hash
ontology_version
confidence
quality_flags
```

### 证据质量标记

```text
TABLE_EXACT_ROW
TABLE_WRAPPED_ROW_RECONSTRUCTED
TEXT_EXACT_LINE
TEXT_FUZZY_ALIAS
UNIT_PAGE_EXPLICIT
UNIT_ROW_EXPLICIT
UNIT_INHERITED
UNIT_DEFAULTED
NOTE_REFERENCE_PRESENT
MULTIPLE_NUMERIC_CANDIDATES
PARSE_SUSPECT
OCR_USED
```

默认不使用OCR；确需OCR时必须显式标记。

## 2.4 L3：规范事实（Canonical Facts）

规范事实表示一个经济含义唯一的观察值。

建议唯一键：

```text
observation_id = hash(
  security_code |
  metric_id |
  scope |
  period_type |
  period_start |
  period_end/report_date |
  currency |
  canonical_unit |
  accounting_standard |
  version_id
)
```

核心字段：

```text
observation_id
security_code
metric_id
metric_name_cn
metric_name_en
research_module
metric_role
statement_type
scope
consolidation_scope
period_type
data_semantics
period_start
period_end
report_date
effective_at
published_at
available_at
as_of_date
value_num
value_text
canonical_unit
currency
scale
status
confidence
source_priority
preferred_source_fact_id
formula
calculation_inputs
version_id
supersedes_observation_id
```

## 2.5 L4：研究映射视图（Research Views）

从规范事实生成不同研究模块，而不是复制另一套事实。

建议视图：

- `company_master`；
- `financial_statements`；
- `quarterly_facts`；
- `ttm_facts`；
- `profit_quality`；
- `segments`；
- `operating_kpis`；
- `capital_structure`；
- `share_count_bridge`；
- `capital_actions`；
- `governance`；
- `litigation_and_regulatory`；
- `market_data`；
- `consensus`；
- `events`；
- `source_coverage`；
- `unresolved_queue`。

## 3. 研究本体（Research Ontology）

## 3.1 Metric定义

每个 `metric_id` 应有稳定配置：

```yaml
metric_id: financial.revenue
name_cn: 营业收入
name_en: Revenue
research_module: financial_statements
metric_role: core_financial
statement_type: income_statement
data_semantics: flow
valid_scopes: [consolidated, parent]
canonical_unit: CNY
preferred_source_tier: T0_STATUTORY
comparison:
  method: numeric
  absolute_tolerance: 1.0
  relative_tolerance: 1.0e-8
  display_decimals: 2
period_rules:
  cumulative_allowed: true
  independent_quarter_allowed: true
aliases:
  official: [营业收入, 营业总收入]
  eastmoney: [OPERATE_INCOME, TOTAL_OPERATE_INCOME]
```

## 3.2 研究模块

一级模块建议：

```text
company
financials
profit_quality
segments
operating_kpi
orders_and_capacity
capital_structure
governance
capital_allocation
risk_and_compliance
market_and_consensus
industry_and_policy
```

## 3.3 Metric Role

同一模块内进一步区分：

- `core_financial`；
- `supplementary_financial`；
- `accounting_policy`；
- `non_recurring`；
- `operating_driver`；
- `capacity`；
- `price`；
- `volume`；
- `capital_action`；
- `governance_event`；
- `market_derived`；
- `consensus_estimate`；
- `source_metadata`。

## 4. 状态模型

## 4.1 事实状态

```text
FACT_DIRECT
FACT_CALCULATED
FACT_ZERO_EXPLICIT
FACT_TEXT_DIRECT
BOUNDARY_DISCLOSURE
```

## 4.2 覆盖与缺口状态

```text
DOCUMENT_NOT_LOADED
DOCUMENT_NOT_FOUND
SOURCE_ROUTE_NOT_IMPLEMENTED
PERMISSION_BLOCKED
PARSER_COVERAGE_GAP
PARSE_SUSPECT
NOT_DISCLOSED_IN_SOURCE
NOT_APPLICABLE_TO_SOURCE
OFFICIAL_PERIOD_NOT_LOADED
FUTURE_FREE_SOURCE_REQUIRED
UNRESOLVED
```

## 4.3 对账状态

```text
EXACT_MATCH
WITHIN_TOLERANCE
DERIVED_MATCH
TEXT_MATCH_NORMALIZED
SET_MATCH
MISSING_SOURCE_A
MISSING_SOURCE_B
UNIT_CONFLICT
PERIOD_CONFLICT
SCOPE_CONFLICT
VERSION_CONFLICT
VALUE_CONFLICT
SOURCE_CONFLICT
```

避免使用一个 `MISSING_OFFICIAL` 覆盖所有缺口根因。

## 5. 版本与Point-in-time模型

## 5.1 必需时间字段

- `report_date/effective_at`：事实对应经济期间；
- `published_at`：文件正式发布日期；
- `available_at`：研究系统可可靠获得的时间；
- `extracted_at`：本次抓取/解析时间；
- `as_of_date`：研究任务允许使用的信息截止日。

可纳入基线条件：

```text
available_at <= as_of_date
```

## 5.2 文档版本链

```text
original -> corrected -> revised -> withdrawn
```

每个版本保留，默认规范事实选择截止日内最高优先级有效版本。

不得删除原版后只保留更正版，否则无法回放历史研究时点。

## 5.3 事实版本链

更正报告导致数值变化时：

- 新建 `version_id`；
- `supersedes_observation_id` 指向旧值；
- 旧值状态改为历史有效，而非物理删除；
- 输出变化原因、文档和影响范围。

## 6. 源路由架构

## 6.1 定期财务报告

用于：

- 三张表；
- 财务附注；
- 分部；
- 非经常性损益；
- 研发；
- 现金流补充；
- 股本与股东；
- 重大事项摘要。

## 6.2 临时公告

用于：

- 回购；
- 股权激励；
- 可转债；
- 定增；
- 解禁和减持；
- 并购重组；
- 重大合同；
- 诉讼、处罚和担保；
- 业绩预告/快报；
- 月度经营数据。

## 6.3 公司官网/IR

用于：

- 产品与业务说明；
- 投资者演示；
- 调研记录；
- 经营KPI；
- 管理层指引。

不能替代法定财务文件，但可作为业务事实补充。

## 6.4 市场平台数据

用于：

- 行情；
- 市值与估值；
- 机构预测；
- 行业排名；
- 资金和持仓；
- 研报索引。

这些默认是来源特定或派生事实，不标记为官方直接披露。

## 7. F10研究映射包输出契约

建议目录：

```text
research_mapping_pack/
├── manifest.json
├── schema/
│   ├── ontology.json
│   ├── metric_registry.json
│   └── status_dictionary.json
├── source/
│   ├── source_facts.parquet
│   └── source_records_index.parquet
├── canonical/
│   ├── canonical_facts.parquet
│   ├── fact_lineage.parquet
│   ├── versions.parquet
│   └── formulas.parquet
├── views/
│   ├── company_master.parquet
│   ├── financial_statements.parquet
│   ├── quarterly_ttm.parquet
│   ├── profit_quality.parquet
│   ├── segments_kpis.parquet
│   ├── capital_structure.parquet
│   ├── governance_events.parquet
│   ├── market_consensus.parquet
│   └── gaps_conflicts.parquet
├── research_mapping.duckdb
├── research_mapping.xlsx
└── quality/
    ├── coverage.json
    ├── validation.json
    └── unresolved.json
```

## 8. 官方原文证据包输出契约

```text
official_evidence_pack/
├── manifest.json
├── documents/
│   ├── original/
│   └── normalized/
├── parsed/
│   ├── text/
│   ├── markdown/
│   ├── pages/
│   └── tables/
├── index/
│   ├── documents.parquet
│   ├── pages.parquet
│   ├── evidence.parquet
│   ├── entity_matches.parquet
│   └── version_chain.parquet
├── evidence.duckdb
├── evidence_index.xlsx
└── quality/
    ├── document_coverage.json
    ├── parser_quality.json
    ├── suspicious_extractions.json
    ├── permission_blocks.json
    └── unresolved.json
```

## 9. 双源/多源对账规则

## 9.1 先规范化，再比较

不得直接比较源值：

```text
原始值
-> 单位规范
-> 期间规范
-> 范围规范
-> 版本选择
-> metric_id映射
-> 指标级容差
-> 比较
```

## 9.2 多对一血缘

同一营业收入可能出现在：

- 利润表；
- 主要财务指标；
- 单季度表；
- 页面汇总；
- 研报摘要。

规范层只保留一个首选观察值，但 `fact_lineage` 保留全部源记录和优先级，不通过简单drop_duplicates丢失来源。

## 9.3 准确性与覆盖分离

对外展示至少六个指标：

```text
classification_coverage
report_coverage
extraction_coverage
comparison_coverage
comparison_accuracy
evidence_completeness
```

## 10. 解析质量闸门

一个官方事实只有满足以下条件才可进入 `FACT_DIRECT`：

1. 能定位到明确报表/章节；
2. 匹配到可信字段标签；
3. 金额来自预期金额列或已成功重建的跨行表格；
4. 单位来源明确；
5. 数字不是附注编号、页码或项目序号；
6. 通过字段级范围检查；
7. 需要时通过会计逻辑或前后期关系；
8. 证据对象完整。

否则进入 `PARSE_SUSPECT` 或 `PARSER_COVERAGE_GAP`，不得静默升级为高置信事实。

## 11. 缓存与幂等

### 11.1 文档缓存键

```text
canonical_url + response_etag/last_modified + document_sha256
```

### 11.2 解析缓存键

```text
document_sha256
+ parser_version
+ target_registry_hash
+ ontology_version
+ parser_options_hash
```

### 11.3 映射缓存键

```text
source_fact_hash
+ ontology_version
+ mapping_registry_hash
```

重复运行不应改变事实ID或输出顺序；只有输入、配置或版本变化时重算受影响范围。

## 12. CLI目标形态

建议最终提供：

```bash
# 快速薄切片
ashare-f10 research-pack 688521 --preset thin-slice --as-of-date 2026-07-21

# 完整首次覆盖数据包
ashare-f10 research-pack 688521 --preset research-full --as-of-date 2026-07-21

# 仅构建研究映射包
ashare-f10 map-research 688521 --run-dir ...

# 仅构建官方证据包
ashare-f10 evidence-pack 688521 --run-dir ... --packs statutory,capital,governance

# 从最近检查点恢复
ashare-f10 resume <task-id>
```

具体命名在实现阶段可调整，但必须保持：一个任务合同、一个as-of-date、一个统一manifest和一个恢复入口。

## 13. 与现有模块的迁移关系

| 现有模块 | 目标位置 | 迁移原则 |
|---|---|---|
| `fetch` | Source Facts | 保留接口行为，增加稳定血缘 |
| `validation` | Evidence/legacy thin slice | 逐步复用统一解析与状态模型 |
| `cross_validation` | Reconciliation | 分离覆盖和准确性，改用规范事实 |
| `raw_sources` | Document/Evidence Registry | 与官方定期报告统一document_id和manifest |
| `export` | Pack Exporters | 输出契约版本化 |
| `formula` | Derived Facts | 公式注册、输入血缘和版本化 |

初期允许新旧输出并行，完成回归后再决定废弃旧接口，避免一次性破坏现有用户。
