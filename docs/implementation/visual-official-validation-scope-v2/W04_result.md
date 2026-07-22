# W04结果：测试、Actions与并行开发安全

## 状态

`COMPLETED`

## 代码问题与修复

1. `visual_jobs_v2.py`与运行时适配器出现Ruff `I001`导入排序错误：使用Ruff自动修复并增加定向门禁。
2. Workflow错误地在静态HTML中搜索由API动态注入的范围文案：改为验证`visual-capabilities.json`。
3. 长时官方验证命令缓冲全部输出：改为流式日志、15秒心跳和输出行计数。
4. Raw Pack与官方验证并行写`artifacts.json`存在覆盖风险：增加运行时最终原子合并和回归测试。
5. PR #21开始修改共享`app_with_raw_pack.py`和`test.yml`：恢复这两个文件到main，并用规范`visual_execution.py`转发V2实现，使精确路径重叠降为0。

## 最终代码门禁

| 工作流 | Run | 结果 |
|---|---:|---|
| Test | #714 | PASS |
| Visual Execution Control | #33 | PASS |
| E2E 688521 | #261 | PASS |
| Raw Pack 688521 E2E | #111 | PASS |
| Official Full-History Validation 688521 | #218 | PASS |

## 并行开发审计

- 当前功能分支基于最新main；
- PR #21仍为Draft；
- 最终文件清单与PR #21无精确路径重叠；
- 共享入口通过小型兼容转发保持稳定；
- 合并前仍需再次确认main未前进。

## 验收

- Python编译、Ruff、pytest、网页/API、现有F10、Raw Pack和全历史官方验证均纳入门禁；
- 网络失败只定向重试，代码问题先读诊断再修复；
- 临时修复Workflow均在用途结束后删除。
