# W08结果：多样本E2E、兼容性与性能验收

## 阶段结论

W08已完成。Research Pack通过确定性多市场矩阵、真实深交所CNINFO样本、上交所688521回归、Point-in-Time、缓存、稳定ID、可移动性和多格式重新打开验收。

## 实施成果

- 新增`tests/test_research_pack_acceptance_matrix.py`，覆盖上交所、深交所、北交所未接入状态、更正版本、明确为零、制造业专题、包移动和缓存行为。
- 新增`tests/test_w08_cninfo_false_conflicts.py`，固定002352真实样本中的假冲突回归。
- 新增`scripts/verify_research_pack_e2e.py`，验证JSON、Excel、Parquet、DuckDB、Manifest、Checkpoint、Evidence Graph和Fact Lineage。
- 新增`.github/workflows/research-pack-matrix.yml`，分为确定性矩阵与真实CNINFO薄切片两部分。
- 为杜邦派生金额字段增加数值比较政策；修正速动比率的非速动资产扣除口径。

## 真实002352排查结果

第一轮27条表面冲突被全部解释并修复：

- 25条来自杜邦金额字段缺少展示单位，误走文本比较；
- 2条来自速动比率公式未扣除全部非速动流动资产；
- 没有发现需要人工裁决的权威来源冲突。

修复后，官方派生事实在两侧均为数值时强制使用数值比较；速动比率按披露口径扣除存货、预付款项、合同资产、其他流动资产、应收款项融资及一年内到期的非流动资产等项目。

## 验收结果

- 编译、Ruff和全量Pytest通过；
- 688521 E2E、官方全历史验证和Raw Pack回归通过；
- 002352真实CNINFO双源薄切片通过且无未解释真实冲突；
- 截止日回放不使用未来文档；
- 相同输入命中缓存，稳定ID保持一致；
- 输入、本体、注册表或提取器版本变化会触发缓存失效；
- 包移动后JSON、Excel、Parquet和DuckDB仍可重新读取；
- Evidence Graph无悬空边，Canonical Observation均有Lineage；
- 不需要人工介入，允许进入W09。

## 恢复入口

```yaml
phase: W08
status: COMPLETED
last_successful_step: multi_sample_e2e_and_live_cninfo_verified
next_action: W09_API_UI_and_final_delivery
human_intervention_required: false
```
