# W07结果：Research Pack导出、CLI与断点恢复

## 状态

```yaml
phase: W07
status: COMPLETED
last_successful_step: research_pack_export_resume_and_quality_verified
next_action: W08_multi_sample_e2e_compatibility_performance
human_intervention_required: false
```

## 完成内容

1. 新增`ashare_f10.research_pack`模块，统一编排：
   - F10源事实；
   - 官方事实；
   - Canonical Observation；
   - Fact Lineage；
   - Research Section；
   - Evidence Graph。
2. 输出JSON、Excel、Parquet和DuckDB四种可消费格式。
3. 包内生成：
   - `checkpoint.json`；
   - `manifest.json`；
   - `summary.json`；
   - 阶段缓存；
   - 质量报告；
   - 完整表目录。
4. CLI新增：

```text
ashare-f10 research-pack <stock_code> <run_dir>
  --output <path>
  --as-of-date YYYY-MM-DD
  --force
```

5. 执行阶段固定为：

```text
LOAD_INPUTS
→ MAP_CANONICAL
→ EXTRACT_SECTIONS
→ BUILD_EVIDENCE
→ EXPORT
→ VALIDATE
```

6. 每个阶段写入检查点；输入指纹不变且交付文件仍通过质量验证时，第二次运行直接返回`cache_hit=true`。
7. 输入指纹包含数据文件SHA-256、研究截止日和Research Pack schema版本。
8. `artifacts.json`登记Research Pack全部核心交付路径。
9. 质量验证覆盖：
   - 文件存在且非空；
   - Excel和DuckDB可重新打开；
   - Source Fact、Observation和Lineage唯一键；
   - Observation血缘完整；
   - Evidence Graph无悬空边；
   - 常用DuckDB视图和索引可用。
10. 修复PyArrow读取集合字段时转为NumPy ndarray导致JSON序列化失败的问题。

## 自动验证

| Workflow | Run | 结果 |
|---|---:|---|
| Test | 607 | success |
| E2E 688521 | 225 | success |
| Official Validation 688521 | 177 | success |
| Raw Pack 688521 E2E | 77 | success |

## 专项测试

- 四种格式均可打开；
- Canonical Fact、Lineage和Evidence表完整；
- 相同输入第二次运行不改写交付文件；
- 截止日后的官方事实不会进入历史规范事实；
- checkpoint包含六个完整恢复阶段；
- Research Pack路径成功登记到运行目录`artifacts.json`。

## 问题排查记录

第一轮测试发现官方事实的`quality_flags`经Parquet往返后成为NumPy ndarray，导致：

```text
TypeError: Object of type ndarray is not JSON serializable
```

根因属于Arrow/Pandas集合标量转换，不是业务事实错误。适配层现在将Arrow/NumPy集合统一转换为普通Python list，修复后全套CI通过。

## 质量指标

```yaml
failed_tests: 0
workflow_failures: 0
blocking_items: 0
cache_reuse_verified: true
point_in_time_verified: true
all_delivery_formats_readable: true
human_intervention_required: false
```

## 恢复入口

```yaml
phase: W08
checkpoint: W07_COMPLETED
next_action: commit_W08_plan_and_run_multi_sample_matrix
```
