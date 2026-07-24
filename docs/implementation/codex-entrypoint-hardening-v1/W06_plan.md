# W06 计划：真实零 Token 复现与证据绑定

## 实施

Prepare Job 必须在精确 Source SHA 上运行受信 Gate，提取失败文件、生成失败指纹并验证 Artifact Digest。任务分支提供的 `reproduction.json` 只能是请求数据，不能作为最终资格证据。

## 验收

- Gate 已通过 → `FAILURE_NOT_REPRODUCIBLE`；
- Source Run / Commit / Artifact Digest 不匹配 → 拒绝；
- 失败文件不被 Allowed Files 完整覆盖 → 拒绝；
- 全程不读取 Secret、不启动模型。
