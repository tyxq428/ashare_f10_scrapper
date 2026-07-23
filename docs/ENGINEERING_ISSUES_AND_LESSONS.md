# 工程问题与复用经验集中记录

本文件集中记录项目执行中出现过、容易在后续项目重复发生的问题。新增问题应追加，不应散落在聊天或临时日志中。

## 记录格式

- **ID**：稳定编号；
- **现象**：用户或系统看到的问题；
- **根因**：技术或流程原因；
- **修复**：本次采取的动作；
- **预防规则**：后续项目启动前应自动检查的规则。

---

## ENV-001 PowerShell函数吞掉命令参数

- **现象**：`pip install -e`中的`-e`被PowerShell解析为函数参数缩写，脚本中断。
- **根因**：包装函数使用`ValueFromRemainingArguments`或可缩写参数名，外部命令短参数被PowerShell绑定。
- **修复**：整条命令用字符串数组传入，函数只接收一个`[string[]]$Command`。
- **预防规则**：Windows包装器统一采用命令数组，不把外部CLI参数暴露为PowerShell函数参数。

## ENV-002 Windows PowerShell默认文本编码破坏Base64

- **现象**：分片拼接后`FromBase64String`报非法字符。
- **根因**：Windows PowerShell 5.1的`Set-Content/Add-Content`默认写入UTF-16/BOM。
- **修复**：避免文本方式拼接Base64；使用字节流或自包含压缩包。
- **预防规则**：涉及哈希、Base64和二进制传输时必须指定字节级处理并在写入后复核SHA-256。

## GHA-001 工作流文件写权限不足

- **现象**：GitHub App可以写普通文件，但拒绝创建或修改`.github/workflows/*.yml`。
- **根因**：缺少Workflows写权限。
- **修复**：使用具备权限的连接器操作，或用户侧SSH/PAT；不要让默认`GITHUB_TOKEN`动态生成工作流。
- **预防规则**：开发前检查本轮是否涉及工作流；工作流变更和普通代码变更分开提交。

## GHA-002 长时任务缺少可观测性

- **现象**：Action长时间无普通日志，难以判断卡住还是仍在运行。
- **根因**：外部命令输出被缓冲，没有心跳和目录进度快照。
- **修复**：增加流式输出、固定心跳、已完成请求组/缓存/目录大小统计。
- **预防规则**：预计超过5分钟的Job必须有心跳；超过阈值主动检查Job步骤和Artifact。

## GHA-003 临时网络错误导致整条流程重复运行

- **现象**：相同步骤因HTTP 502、超时等需要多次完整执行。
- **根因**：未区分可重试网络错误和代码/权限错误，也未复用已成功检查点。
- **修复**：有限指数退避，只重试失败组或失败Job，保留成功缓存。
- **预防规则**：先分类`RETRYABLE/NON_RETRYABLE`；网络错误只重跑失败部分，验证码、权限和Schema错误不得盲目重试。

## UX-001 将薄切片参数暴露给最终用户

- **现象**：页面要求用户输入“年度报告年份”和“一季度报告年份”，用户需要先知道股票上市时间且误以为一次只能验证两份报告。
- **根因**：验证阶段的两报告薄切片接口直接进入正式UI，没有转换为用户业务范围。
- **修复**：网页改为“最近2个报告期/最近3年/最近5年/上市以来”，默认上市以来；后台自动识别上市日期和报告期。
- **预防规则**：正式UI不得直接暴露薄切片、测试fixture或内部实现参数；必须转换为业务语言。

## UX-002 技术参数默认全部展开

- **现象**：并发、轮询、重试轮数、退避秒数、文档上限与业务配置混在同一层。
- **根因**：以开发者配置表单代替用户任务流程。
- **修复**：常用页面只保留股票代码、研究模式、资料范围和开始按钮；技术参数折叠到高级设置。
- **预防规则**：默认界面最多展示完成任务所需的最少业务决策。

## UX-003 旧任务显示内部状态`UNKNOWN`

- **现象**：任务已经完成，但F10阶段显示`UNKNOWN`。
- **根因**：旧任务没有新的Sidecar状态文件，页面直接显示默认枚举。
- **修复**：根据主任务状态、完成组数和Artifact推导阶段状态。
- **预防规则**：新增状态存储必须提供旧数据推导和迁移策略。

## UX-004 内部字段被渲染为下载链接

- **现象**：`fact_count`等非文件值出现在下载按钮区域，点击可能404。
- **根因**：前端遍历全部Artifact键，没有校验类型和允许列表。
- **修复**：只渲染已知文件Artifact且值为非空路径字符串。
- **预防规则**：下载UI使用显式白名单，不遍历任意后端字典。

## DATA-001 来源冲突不等于执行失败

- **现象**：全历史官方验证成功发现真实来源冲突时，用户容易把`FAIL_SOURCE_CONFLICT`理解为程序崩溃。
- **根因**：执行状态和研究验收状态混用。
- **修复**：执行层显示“完成，需复核”，保留冲突、证据和警告；只有代码异常才显示任务失败。
- **预防规则**：区分`execution_status`与`research_acceptance_status`。

## GIT-001 并行开发分支覆盖风险

- **现象**：多个PR同时修改main，功能分支测试通过后仍可能落后或产生冲突。
- **根因**：合并前没有再次刷新main和检查文件交集。
- **修复**：开发分支独立；合并前比较ahead/behind、检查开放PR文件交集、同步最新main并重跑门禁。
- **预防规则**：所有长任务至少执行“创建分支时”和“合并前”两次并行开发审计。

## CODE-001 Ruff导入排序应由工具修复

- **现象**：新增可视化运行时模块在CI中触发`I001`，手工阅读看似有序但不符合Ruff实际分组规则。
- **根因**：别名导入与普通名称导入在Ruff/isort规则下会被拆分，人工猜测容易反复失败。
- **修复**：使用一次性Ruff `--fix`任务生成精确变更，并为运行时模块保留定向Ruff门禁。
- **预防规则**：机械格式错误直接交给同版本工具修复，不凭视觉判断手改。

## GHA-004 动态配置错误地在静态HTML中验收

- **现象**：页面和API均正常，但Workflow在静态`run.html`中查找“上市以来全部报告”而失败。
- **根因**：范围选项由`/api/visual-execution/capabilities`动态注入，不存在于静态HTML。
- **修复**：静态HTML只验证页面骨架和旧字段已删除；动态选项改为验证Capabilities JSON。
- **预防规则**：测试断言必须对准真实数据来源，不能把运行时注入内容当作静态模板内容。

## GHA-005 长时子进程输出被完整缓冲

- **现象**：全历史官方验证持续运行但Actions长时间无日志，看起来像卡住。
- **根因**：`subprocess.run(..., stdout=PIPE)`直到命令结束才返回全部输出。
- **修复**：改用`Popen`流式读取，安静期间每15秒输出心跳、静默时长和输出行数。
- **预防规则**：预计超过5分钟的外部命令必须流式输出并提供固定心跳。

## UX-005 覆盖缺口和部分来源不可用被静默显示为普通完成

- **现象**：`PASS_WITH_COVERAGE_GAPS`或`PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE`没有真实数值冲突，却仍需要研究者注意，原页面可能显示普通“已完成”。
- **根因**：只把`FAIL_*`和`manual_review_required`映射为需复核。
- **修复**：所有非`PASS`研究验收状态均显示“完成，需复核”，并提供针对覆盖缺口或来源不可用的中文说明。
- **预防规则**：程序执行状态与研究结论状态分离；非PASS研究状态不得静默绿灯。

## DATA-002 并行可选阶段竞争写Artifact清单

- **现象**：Raw Pack与官方验证并行结束时都可能读写`artifacts.json`，理论上存在最后写入覆盖另一个阶段结果的风险。
- **根因**：两个独立Runner各自执行非原子的读—改—写。
- **修复**：可视化运行时在两个Future全部完成后，使用进程内锁和临时文件替换原子合并核心、Raw Pack和官方验证Artifact。
- **预防规则**：并行任务不得各自覆盖共享清单；必须由编排层执行最终一致性合并。

## GIT-002 通过稳定转发入口消除并行PR同路径冲突

- **现象**：PR #21开始同时修改`app_with_raw_pack.py`和`test.yml`，本功能分支原本也修改这两个共享文件。
- **根因**：不同功能直接改动高频共享入口，虽然逻辑不冲突，Git层面仍会产生同路径合并风险。
- **修复**：恢复共享文件到main，使用规范`visual_execution.py`转发到V2实现；定向测试留在独立Workflow。
- **预防规则**：并行开发优先使用扩展模块和稳定转发层，尽量不修改对方正在变更的聚合入口。

## GHA-006 网络不可达错误未进入有限重试

- **现象**：Post-merge全历史验证访问上交所时出现`NewConnectionError`、`Max retries exceeded`和`[Errno 101] Network is unreachable`，但有限重试器把它判为不可重试并在第一次失败后停止。
- **根因**：重试正则只覆盖HTTP状态、timeout、connection reset和DNS等常见文案，没有覆盖urllib3/操作系统产生的“建立新连接失败”和“网络不可达”表达。
- **修复**：将`Network is unreachable`、`Failed to establish a new connection`、`Max retries exceeded`、`NewConnectionError`以及errno 101/110/111/113加入重试分类，并使用实际SSE错误文本增加回归测试。
- **预防规则**：重试分类必须包含HTTP、DNS、TLS、socket errno及主流HTTP库包装异常的代表性fixture；非网络类`OfficialSourceError`仍应立即停止。

## GHA-007 Post-merge验证必须能够阻断收尾

- **现象**：合并前全部门禁通过，但合并后独立验证暴露了网络重试分类缺口。
- **根因**：真实网络故障组合只有在新的独立运行中才出现，单纯复用合并前结果无法覆盖运行环境变化。
- **修复**：关闭未合并的临时验证PR，独立创建并合并热修复PR，再从最新`main`重新触发五项完整门禁。
- **预防规则**：重要功能必须保留“合并后临时PR复验—失败则热修复—重新全门禁—关闭并重置临时分支”的闭环，未通过时不得写100%完成。

## GHA-008 合并后Canonical State仍指向已合并功能分支

- **现象**：PR-A合并后，`Devflow State Consistency`在`main`上报告`working_branch mismatch`。
- **根因**：合并前状态中的活动分支是真实事实，但合并后没有先执行状态迁移就触发了精确主分支校验。
- **修复**：将`working_branch`、`ACTIVE_TASKS`、`STATUS`和`HANDOFF`统一迁移到`main`，并记录合并SHA后重新执行精确主分支校验。
- **预防规则**：合并动作必须包含显式的`MERGED → POST_MERGE`状态迁移；分支一致性校验不能假设合并前后的工作分支相同。

## GHA-009 并发Incident Workflow创建重复控制Issue

- **现象**：两个几乎同时结束的失败Workflow分别创建了相同标题的任务控制Issue。
- **根因**：两个通知Workflow并行执行，且使用有索引延迟的Issue Search作为“先查后建”判断，存在竞态窗口。
- **修复**：所有任务通知共享同一个仓库级concurrency group，改用Issues REST列表进行精确标题匹配，并按`run_id + type`检查已有评论。
- **预防规则**：有副作用的通知创建必须串行化、使用强一致性更高的资源列表，并以稳定事件键实现幂等。

## GHA-010 Secret安全要求导致Forwarder启动失败不可诊断

- **现象**：Codex任务在本地Responses Forwarder启动阶段失败，Codex未实际调用，但原Workflow只显示健康检查超时。
- **根因**：Forwarder在模块导入时解析私有Endpoint，异常输出又被全部丢弃；安全隐藏与可观测性之间缺少结构化中间层。
- **修复**：增加只输出布尔检查和错误分类的Secret-safe预检；Forwarder改为运行期初始化、写入不含私密值的状态文件；诊断Artifact保存在工作区外并经过Secret扫描。
- **预防规则**：敏感运行时可以隐藏值，但不能隐藏状态；所有Secret依赖步骤必须先产生安全的presence/shape检查和稳定failure class。

## GHA-011 Scope Guard被自身诊断Artifact污染

- **现象**：Codex修改完成后，路径范围检查可能把Workflow自己创建的`artifact/`目录识别为越界修改。
- **根因**：诊断文件在运行路径范围检查前写入仓库工作区，而Scope Guard按`git status`检查全部未跟踪文件。
- **修复**：Codex结果、Scope结果、Gate结果和Patch统一写入`/tmp/codex-artifact`，Publish Job也在工作区外下载Handoff。
- **预防规则**：范围检查前后所有执行器元数据必须位于仓库工作区外；仓库工作区只允许出现任务声明允许的产品变更。

## GHA-012 原始Workflow失败直接升级为用户中断

- **现象**：状态校验、Forwarder或Codex首次失败后，任务控制Issue立即出现`[TASK][INTERRUPTED]`，用户必须回到ChatGPT Web输入“继续”。
- **根因**：Incident Workflow直接监听`workflow_run`的非成功终态，没有在通知前执行错误分类、有限重试或受限代码修复。
- **修复**：新增`Devflow Auto Recovery`，先读取Job/Step元数据和安全摘要，自动执行失败Job重跑或一个Codex Recovery Generation；只有人工门槛、安全阻断、无法分类或预算耗尽才发送`devflow_notify`。
- **预防规则**：原始失败事件不得直接面向用户；通知必须是自动恢复控制器的最终决策输出。

## GHA-013 `/ack`文案让用户误以为会触发修复

- **现象**：控制Issue要求回复`/ack`，用户合理地理解为“确认后继续”，但实际没有任何Workflow监听该命令。
- **根因**：确认送达和恢复执行两种语义混在同一提示中。
- **修复**：通知明确说明`/ack`只确认已看到，不触发修复、重试、Codex、resume或状态更新；自动恢复必须在通知前完成。
- **预防规则**：ACK、retry和resume必须是不同命令和不同状态迁移；没有实现监听器时不得暗示命令会执行动作。

## GHA-014 依赖`GITHUB_TOKEN` Push隐式触发后续Gate

- **现象**：Codex Publish成功Push产品分支，但后续CI或Gate可能没有自动启动。
- **根因**：GitHub会抑制由仓库`GITHUB_TOKEN`产生的大多数递归事件，不能把普通Push当作可靠编排器。
- **修复**：Codex Publish显式发送`devflow_product_gate`，Product Gate合并后显式发送`devflow_post_merge`，最终通过`devflow_notify`完成通知。
- **预防规则**：多阶段Actions使用`workflow_dispatch`或`repository_dispatch`显式接力，并保留task-specific concurrency和幂等键。

## GHA-015 自动修复必须以Task Generation为预算单位

- **现象**：完全禁止第二次Codex会导致明确局部Gate失败仍需人工，而无限重试又会造成额度失控和错误循环。
- **根因**：没有区分“同一Agent会话无限循环”和“基于新失败证据创建一个新的受限修复代次”。
- **修复**：每个Task Generation保持一次Codex Session和零自动第二Session；Full/Post-Merge失败时最多创建一个继承原范围、Gate和风险政策的Recovery Generation。
- **预防规则**：预算必须同时限制Session、Generation、Root Cause和基础设施重试；任何自动恢复都不得扩大允许路径。

## GHA-016 Reusable Workflow边界未取得Environment Secrets

- **现象**：正式仓库`agent-runtime`中三个Secret名称和值均已配置；普通Job的安全presence探针全部为true，但本地`workflow_call`中的Secret-bearing Job连续报告Endpoint、Key和Model全部缺失，Forwarder和Codex均被跳过。
- **根因**：当前仓库运行环境下，Environment Secret在本地reusable workflow调用边界中的实际可见性与普通Job不同；继续重跑同一Workflow不会改变该边界。
- **修复**：把`environment: agent-runtime`直接绑定到入口`codex-task.yml`的普通只读Job；将可复用单元改为本地composite action，只通过显式inputs接收Key和Model；删除旧reusable workflow，并只通过显式`workflow_dispatch`运行默认分支的入口Workflow。
- **预防规则**：涉及Environment Secrets时必须先运行普通Job presence薄切片；Secret-bearing执行Job不得间接隐藏在未经真实验证的`workflow_call`边界中，复用优先使用composite action或已验证的直接Job模式。

## GHA-017 仓库Bot触发Codex未显式授权且绝对输出路径不稳定

- **现象**：Environment Preflight和localhost Forwarder已通过，官方Codex Action仍返回失败，未生成结构化结果，Scope Guard与Targeted Gate被跳过。
- **根因**：无人值守链由`github-actions[bot]`显式派发，而官方Action默认不允许Bot绕过写权限校验；同时流程把绝对`/tmp`路径作为`output-file` input，偏离官方相对路径与`final-message`输出模式。
- **修复**：仅授权`github-actions[bot]`，不开放任意用户或Bot；通过Output Schema约束`final-message`，Caller Job用环境变量和Python解析后写入工作区外的`/tmp/codex-result.json`。
- **预防规则**：Agent Action的触发者校验必须纳入薄切片；自动派发时显式列出可信Bot。模型输出先作为结构化Action output处理，不把绝对临时路径直接交给第三方Action。

## GHA-018 移动的main被误算为候选分支越界修改

- **现象**：Codex、Scope Guard、Targeted Gate和Publish全部通过，产品分支只修改获准的两个文件；Product Gate却在Full Gate前报告Scope失败。
- **根因**：初始产品范围使用`git diff origin/main HEAD`。候选生成后`main`新增了观察/编排提交，双点Diff把`main`独有变化也算入候选差异。
- **修复**：先验证`expected_base_sha`是候选祖先，再以`git merge-base origin/main HEAD`作为初始范围基线；合并前rebase到最新main后，再以`origin/main..HEAD`重跑范围和Full Gate。
- **预防规则**：异步候选分支的初始差异必须相对共同祖先或固定批准基线计算，不能直接与移动主分支做双点Diff；真实Scope失败仍须Fail Closed。

## GHA-019 Product Gate未配置Git提交身份导致假人工门槛

- **现象**：Scope和Full Gate均通过，低风险候选进入自动合并后出现`Committer identity unknown`，系统错误发送`AUTO_MERGE_BLOCKED`人工通知。
- **根因**：Runner执行`git rebase`/`git merge --no-ff`前没有固定`user.name`和`user.email`；同时Product Gate直接通知，没有先交给统一恢复分类。
- **修复**：合并步骤固定使用`github-actions[bot]`提交身份；失败时Fail Closed并交给Auto Recovery。只有真实冲突、branch protection或权限拒绝才分类为`HUMAN_REQUIRED`。
- **预防规则**：任何在Runner创建Commit的步骤都必须显式配置Git身份；机械配置缺失不得升级为用户决策。

## GHA-020 Codex推理强度策略与历史Descriptor兼容

- **现象**：正式Thin Worker长期硬编码`effort: low`，与后续任务要求的最高推理强度不一致；直接收紧Schema又会使已发布历史控制分支无法继续Gate。
- **根因**：运行时策略、任务模板和历史元数据没有分层。
- **修复**：正式Action固定`effort: xhigh`，新模板和Recovery Generation写入`reasoning_effort: xhigh`；Schema v1只读兼容历史`low`，但历史值不能降低实际运行强度。
- **预防规则**：模型运行强度由版本化执行器强制；元数据迁移必须避免无意义重跑已经通过G1的历史候选。


## GHA-021 State Consistency 合成错误范围导致 XHigh Codex 循环

- **现象**：多个 State Consistency 失败被自动转换为 XHigh Codex Recovery；模型反复返回 `BLOCKED`、零变更，但仍被重跑或再次派发。
- **根因**：Auto Recovery 在没有不可变失败 Task Descriptor 时从 `main` 合成固定五文件范围；真实失败位于活动功能分支的新文件和测试中，范围无法覆盖。恢复策略也没有把结构化 `BLOCKED` 视为终态。
- **修复**：删除合成 State Consistency Descriptor；State Consistency 默认交给 ChatGPT Web；读取 `codex-result.json`，`BLOCKED` 立即熔断且禁止重试；根因修复期间关闭生产模型入口。
- **预防规则**：Codex Repair 必须同时具备不可变任务上下文、可复现失败、正确基线和覆盖真实失败路径的允许范围；`BLOCKED` 永远不能自动重试同一 Generation。
