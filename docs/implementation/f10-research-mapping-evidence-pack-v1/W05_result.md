# W05结果：统一Official Evidence Graph

## 状态

```yaml
phase: W05
status: COMPLETED
last_successful_step: unified_evidence_graph_verified
next_action: W06_research_section_extractors
human_intervention_required: false
```

## 完成内容

1. 新增`ashare_f10.evidence`包。
2. 统一以下对象为证据图：
   - OfficialDocument；
   - Raw Pack SourceDocument；
   - 附件；
   - 解析文本；
   - Source Fact；
   - Canonical Observation；
   - 页级和行级Evidence Location。
3. 节点类型：

```text
SECURITY
DOCUMENT
ATTACHMENT
PARSED_TEXT
EVIDENCE_LOCATION
SOURCE_FACT
CANONICAL_OBSERVATION
```

4. 边类型：

```text
DESCRIBES_SECURITY
SUPERSEDES
ATTACHED_TO
PARSED_FROM
DERIVED_FROM_DOCUMENT
LOCATED_AT
PART_OF_DOCUMENT
SELECTED_FOR
SUPPORTS
CONFLICTS_WITH
QUARANTINED_FOR
```

5. 只有URL而没有独立文档记录的源事实，会建立明确标注的placeholder文档节点，不丢失来源，也不伪造原始文件。
6. 官方文档保留URL、SHA-256、文本哈希、版本、可得日、文件路径和实体匹配信息。
7. Evidence Location保留PDF页码和原始行。
8. Canonical Observation可通过确定性BFS查询穿透至Source Fact、文档和位置证据。
9. 更正版与原版通过`SUPERSEDES`连接。
10. Raw Pack附件与解析文本分别连接父文档。
11. 质量报告检查：
   - 节点重复；
   - 边重复；
   - 悬空边；
   - Observation lineage覆盖率；
   - Observation evidence覆盖率。

## 薄切片结果

| 场景 | 结果 |
|---|---|
| 官方利润表事实→PDF页码→原始行 | 可穿透 |
| 东方财富事实只有接口URL | 建立placeholder文档 |
| 更正版→原版 | 版本链保留 |
| 多源规范事实 | 多条支持边保留 |
| 可疑解析事实 | `QUARANTINED_FOR` |
| Raw Pack附件 | 连接父文档 |
| Parsed Text | 连接原始文档 |
| 重复构建 | 节点和边ID稳定 |

## 自动验证

| Workflow | Run | 结果 |
|---|---:|---|
| Test | 570 | success |
| E2E 688521 | 206 | success |
| Official Validation 688521 | 158 | success |
| Raw Pack 688521 E2E | 58 | success |

## 质量指标

```yaml
new_evidence_graph_tests: 5
dangling_edges: 0
duplicate_node_ids: 0
duplicate_edge_ids: 0
observation_lineage_coverage_in_fixture: 1.0
observation_evidence_coverage_in_fixture: 1.0
blocking_items: 0
```

## 后续

W06将基于Canonical Observation和Source Fact生成盈利质量、分部KPI、研发、股本资本事项、治理风险和缺口清单等研究专题包。
