# 决策记录

## D001｜Artifact是投递观察证据，不是任务状态源

Canonical task state和task-control Issue继续是权威结果。`bark-delivery-result.json` 只证明通知Transport发生了什么；回执缺失或上传失败不得撤销任务终态。

## D002｜记录HTTP状态但不记录响应内容

HTTP status和curl exit code足以区分服务端接受、网络失败和HTTP失败。响应正文、响应头、Endpoint、DNS、IP和原始错误没有必要且可能泄漏信息，因此永久禁止进入Artifact、Issue和日志。

## D003｜Issue只写安全回执索引

Bark Job在Artifact上传后，向同一个canonical task-control Issue追加：delivery status、request initiated、request count、HTTP status、Incident Run ID、Artifact ID和Artifact URL。该评论不包含Secret或Endpoint。

## D004｜回执上传和索引评论均Fail Open

Artifact或Issue回执评论失败不会触发Auto Recovery，不会重试Bark，不会改变canonical DONE。Job Summary必须明确区分Transport结果和观察层结果。

## D005｜本任务完成事件就是Live测试

不创建synthetic测试Workflow。实现先合入main，再用本任务的原子DONE closeout触发真实 `COMPLETED` 事件；该事件最多发起一次Bark并生成回执Artifact。

## D006｜At-most-once优先于自动补发

即使Artifact上传或回执评论失败，也不通过UI Re-run或自动重试补发Bark。未来通知继续使用新的逻辑事件和新的fingerprint。

## D007｜通知细节由专用Validator维护

`validate_workflows.py` 已将 `validate_notification_channels()` 的全部错误并入总Workflow Gate。回执的单文件Artifact、保留期、唯一脚本使用者、Issue索引和安全排除项集中在专用Validator中，避免在两个文件复制同一规则并产生漂移；总Workflow验证仍会永久执行这些检查。