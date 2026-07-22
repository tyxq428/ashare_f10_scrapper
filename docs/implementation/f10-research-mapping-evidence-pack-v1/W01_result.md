# W01结果：官方PDF解析正确性闸门

## 状态

```yaml
phase: W01
status: COMPLETED
last_successful_step: parser_quality_gate_and_regression_verified
next_action: W02_point_in_time_and_version_chain
human_intervention_required: false
```

## 完成内容

1. `OfficialFact`新增向后兼容的解析质量元数据：
   - `source_status`
   - `quality_flags`
   - `parse_notes`
   - `raw_value`
2. 对财务报表行新增附注编号误识别检测。
3. `递延所得税资产 七、29`这类记录被标记为：

```text
source_status = PARSE_SUSPECT
quality_flags = NOTE_REFERENCE_AS_AMOUNT
confidence = low
```

4. 可疑事实保留在证据文件和Excel的`ParseSuspects`工作表中，但不会进入：
   - 双源数值对账；
   - 会计逻辑检查；
   - 完整交叉验证官方事实集。
5. 验证摘要新增：
   - 可用官方事实数；
   - 可疑解析数；
   - 事实状态统计；
   - 质量标记统计。
6. 存在可疑解析但其他验证通过时，验收状态为`PASS_WITH_PARSE_GAPS`，不再以无条件`PASS`掩盖解析覆盖缺口。

## 薄切片结果

| 案例 | 预期 | 结果 |
|---|---|---|
| 正常金额行 | 保留直接事实 | 通过 |
| 仅有`七、29`附注号 | 隔离为可疑事实 | 通过 |
| 附注号＋真实金额 | 保留真实金额 | 通过 |
| 括号负数和单位逻辑 | 保持原行为 | 通过 |
| 可疑事实参与逻辑检查 | 必须被排除 | 通过 |

## 自动验证

| Workflow | Run | 结果 |
|---|---:|---|
| Test | 471 | success |
| Official Validation 688521 | 110 | success |
| E2E 688521 | 158 | success |

## 质量指标

```yaml
new_regression_cases: 3
failed_tests: 0
workflow_failures: 0
blocking_items: 0
rework_required: false
```

## 影响范围

- 修复的是解析假阳性和下游污染问题；
- 没有猜测或补写缺失金额；
- 没有改变现有F10抓取逻辑；
- 没有与PR #18的SSE历史报告发现逻辑产生冲突。

## 后续

W02将增加严格的研究截止日、文档可得日、版本链和边界披露控制，防止更正版或未来公告泄漏到历史研究时点。
