# W05结果：合并、Post-merge验证与复盘

## 状态

`COMPLETED` — 任务完成度`100%`

## 正式合并

- 功能PR：[#24](https://github.com/tyxq428/ashare_f10_scrapper/pull/24)
- 功能合并提交：`5167a91b8b17dc16326fa9d35d7301e80695e1ed`
- 合并前基线：功能分支相对`main`为ahead 41、behind 0。
- 合并前与Draft PR #21的当前变更文件精确路径交集为0。

## 合并前最终门禁

| 工作流 | Run | 结果 |
|---|---:|---|
| Test | #716 | PASS |
| Visual Execution Control | #34 | PASS |
| E2E 688521 | #262 | PASS |
| Raw Pack 688521 E2E | #112 | PASS |
| Official Full-History Validation 688521 | #219 | PASS（仅重跑失败Job后通过） |

#219第一次执行遇到单个东方财富接口组的临时失败。处理时没有重复执行其他已成功工作流，只重跑该失败Job。

## 第一次Post-merge验证及发现的问题

临时验证PR [#25](https://github.com/tyxq428/ashare_f10_scrapper/pull/25)只修改一个无害测试标记，不合并。

它发现SSE官方来源出现以下瞬时网络错误时，有限重试器未正确识别：

```text
NewConnectionError
Failed to establish a new connection
[Errno 101] Network is unreachable
Max retries exceeded
```

该问题属于重试分类缺口，而非官方验证业务逻辑错误。PR #25因此关闭且未合并，验证分支随后重置到`main`。

## 网络重试热修复

- 热修复PR：[#26](https://github.com/tyxq428/ashare_f10_scrapper/pull/26)
- 热修复合并提交：`434f31baca281e9eb4e38e9f2e1c3151cbee5c56`
- 修改范围：`scripts/run_resilient_command.py`和`tests/test_resilient_fetch.py`。
- 新增识别：`Network is unreachable`、`NewConnectionError`、`Failed to establish a new connection`、`Max retries exceeded`及常见网络errno。
- 非网络类`OfficialSourceError`仍不会盲目重试。

热修复门禁：

| 工作流 | Run | 结果 |
|---|---:|---|
| Test | #725 | PASS |
| Visual Execution Control | #36 | PASS |
| E2E 688521 | #264 | PASS |
| Official Full-History Validation 688521 | #221 | PASS |

## 最终Post-hotfix验证

临时验证PR [#27](https://github.com/tyxq428/ashare_f10_scrapper/pull/27)同样只包含无害测试标记，不合并。

| 工作流 | Run | 结果 |
|---|---:|---|
| Test | #729 | PASS |
| Visual Execution Control | #37 | PASS |
| E2E 688521 | #265 | PASS |
| Raw Pack 688521 E2E | #114 | PASS |
| Official Full-History Validation 688521 | #222 | PASS |

PR #27已关闭且未合并，临时验证分支已强制重置到`main`的`434f31baca281e9eb4e38e9f2e1c3151cbee5c56`。

## 688521全历史验收基线

- 官方报告：23份；
- 官方事实：2,975条；
- F10与官方对账记录：135,956条；
- 分类覆盖率：100%；
- 上市日期：2020-08-18；
- 上市后应披露报告发现缺口：0；
- 会计逻辑检查：63项PASS；
- TTM检查：2项PASS；
- 保留1项有官方证据支持的真实来源差异，界面显示“完成，需复核”。

## 清理与最终结论

- PR #24：已合并；
- PR #25：已关闭、未合并、分支已重置；
- PR #26：已合并；
- PR #27：已关闭、未合并、分支已重置；
- 临时修复Workflow：均已在用途结束后删除；
- Windows正式入口：`scripts/start-web.ps1`和`/run.html`；
- 必须人工介入项：0；
- 剩余必做项：0。
