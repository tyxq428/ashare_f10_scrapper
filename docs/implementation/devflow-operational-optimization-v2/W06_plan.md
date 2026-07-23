# W06 Plan：零模型预合并验证

## Gate

1. Workflow 静态安全；
2. Canonical State 和文档链接；
3. Ruff 与全部 `test_devflow*.py`；
4. Upgrade Compatibility；
5. Impact Classification；
6. 手工强制完整 Test；
7. 手工强制真实 E2E；
8. 确认优化期间 Codex 调用数为 0。

失败时由 ChatGPT Web 读取确定性日志并直接修复，不派发模型。
