# W03 计划：Gate、Scope Guard 与 Failure Bundle

## 目标

把可确定性执行的规则从 Markdown 转为脚本：可信 Gate Profile、允许路径检查、Manifest、失败包和 Workflow 静态安全。

## 动作

1. 定义 G0–G5；
2. 建立只读 Gate Profile 映射，禁止任务文件注入任意 Shell；
3. 校验 Git changed paths 与任务允许路径；
4. 生成有长度上限的 Failure Bundle；
5. 静态检查新 Workflow 的 Action SHA、触发器、权限和 Secret 引用。

## Gate

G1：devflow 单元测试；越界、未知 Gate、危险 Workflow 和无边界日志必须失败。
