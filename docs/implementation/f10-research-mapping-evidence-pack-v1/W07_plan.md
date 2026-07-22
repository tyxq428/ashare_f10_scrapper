# W07计划：Research Pack导出、CLI与断点恢复

## 目标

将F10源事实、官方事实、Canonical Observation、Fact Lineage、Evidence Graph和研究专题一次性打包为可直接消费、可验证、可恢复的研究数据包。

## 输出目录

```text
research_pack/
├── checkpoint.json
├── manifest.json
├── summary.json
├── cache/
│   ├── source_facts.parquet
│   ├── canonical_observations.parquet
│   ├── fact_lineage.parquet
│   ├── evidence_nodes.parquet
│   └── evidence_edges.parquet
├── tables/
│   ├── *.parquet
├── exports/
│   ├── <code>_research_pack.json
│   ├── <code>_research_pack.xlsx
│   └── <code>_research_pack.duckdb
└── quality/
    └── research_pack_quality.json
```

## 执行阶段

```text
LOAD_INPUTS
→ MAP_CANONICAL
→ EXTRACT_SECTIONS
→ BUILD_EVIDENCE
→ EXPORT
→ VALIDATE
```

每一步完成后更新checkpoint，重复运行时从最近成功阶段继续。

## 实施内容

1. 新增`research_pack`包；
2. 自动定位F10 DuckDB、官方事实Parquet、官方文档和Raw Pack索引；
3. 输入指纹包含文件SHA-256、as-of-date和研究包schema版本；
4. 完成阶段结果保存为Parquet缓存；
5. 相同输入且交付文件完整时直接复用，不重跑；
6. `--force`只在明确要求时忽略缓存；
7. JSON使用流式表数组，避免大表一次性占用内存；
8. Excel输出摘要、规范事实、专题、来源和证据图索引；
9. DuckDB输出完整表并建立常用视图和索引；
10. 质量报告检查结构、唯一键、血缘、证据、冲突、空值状态和文件可打开性；
11. CLI新增：

```text
ashare-f10 research-pack <stock_code> <run_dir>
```

12. `artifacts.json`登记研究包路径。

## 验收标准

- JSON、Excel、Parquet和DuckDB均可打开；
- Source Fact、Canonical Observation、Lineage数量一致；
- 所有Observation均有lineage；
- 无悬空证据边；
- Canonical唯一键无重复；
- 相同输入第二次运行命中缓存；
- 中断后能从缓存阶段恢复；
- CLI和现有命令兼容；
- 单元测试及现有E2E通过。

## 恢复入口

```yaml
phase: W07
checkpoint: W07_PLAN_COMMITTED
next_action: implement_research_pack_runner_exporter_and_validator
```
