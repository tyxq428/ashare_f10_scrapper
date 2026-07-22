# F10研究映射包＋官方原文证据包优化计划

本目录用于持续记录从基线审计到最终交付的每一步计划、结果、质量指标和恢复入口。

## 当前状态

```yaml
phase: W00
status: COMPLETED
code_changes: 0
last_successful_step: baseline_audit_and_target_design
next_action: W01_parser_correctness_thin_slice
branch: plan/f10-research-mapping-evidence-pack-v1
baseline_main_commit: 6997c1a6894b2b9414aa196bbd631e9dbb2ce8b9
```

本阶段严格遵守用户要求：只校验仓库和数据、输出规划，不修改业务代码。

## 已完成文档

1. [00_task_contract.md](./00_task_contract.md)  
   定义目标、范围、输出、来源、禁止事项、完成标准和人工介入规则。

2. [01_baseline_audit_688521.md](./01_baseline_audit_688521.md)  
   审计仓库现有能力，以及688521官方事实包和交叉验证包；记录P0伪事实与覆盖指标问题。

3. [02_target_architecture.md](./02_target_architecture.md)  
   定义源事实、证据对象、规范事实、研究本体、版本链和两个目标数据包的输出契约。

4. [03_implementation_plan.md](./03_implementation_plan.md)  
   将实现拆成W01—W09，规定依赖、测试、检查点、Markdown和合并策略。

5. [04_acceptance_matrix.md](./04_acceptance_matrix.md)  
   定义结构、数据、来源、时点、对账、恢复和真实E2E验收标准。

## 最重要的基线发现

### P0：官方解析伪事实

`688521_official_full`中，解析器把：

```text
递延所得税资产 七、29
递延所得税负债 七、29
```

中的附注编号29识别成金额，并标为高置信官方直接事实。后续第一项代码工作必须先修复该类错误。

### 质量指标语义

当前交叉验证显示：

- 548条匹配；
- 0条真实冲突；
- 但官方解析和可比覆盖很低；
- 现有1.245%的`comparable_match_rate`主要是覆盖率，不应被称为准确率。

目标架构将拆分分类覆盖、报告覆盖、解析覆盖、可比覆盖、比较准确性和证据完整率。

### 数据链尚未统一

F10、官方报告解析、cross-validation和Raw Pack已经各自具备重要能力，但缺少统一：

- document_id；
- evidence_id；
- source_fact_id；
- observation_id；
- point-in-time版本链；
- 多源血缘和研究模块映射。

## 后续执行顺序

```text
W01 解析正确性闸门
-> W02 as-of-date与版本链
-> W03 对账语义、容差和质量指标
-> W04 研究本体与规范事实
-> W05 统一官方证据图
-> W06 盈利质量/分部/股本/治理章节解析器
-> W07 数据包导出、CLI和恢复
-> W08 多样本E2E、兼容性和性能
-> W09 UI/API对接
```

每个工作包开始和完成时都将在本目录新增Markdown，不因正常阶段成果暂停后续执行。
