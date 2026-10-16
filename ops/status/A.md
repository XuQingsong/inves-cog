# A 线回报

> 只由 A 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## A-004  已收到  2026-10-16 13:20 北京
- 已读 main 的 A-004（blob 43ede3bf55f4f7cb3b89ccbe44fe029dd450ab23），G1 已由用户批准。仅做 M4 开工复述，提交草稿 PR 后停下，不写实现。
- PR #10 已确认 merged=true，合并 sha 61a97e139d80c1b43b4a5a72b30c7f2fa678483a；接下来先核对并按本任务明确授权将 Mac 定时服务切到最新 main，记录实际提交与重启时间。
- 将完整阅读 T04、M4 v3、适用任务书/规格，登记固定 Muse aacea04 的只读源码文件和行号，包含中期 v18 回放检查点、trading 表及迁移名、分级疑问。
- 规则变化：仅剩等时间的证据可按需求方转交先收口；B 线真实数据申请由需求方转成 A 线任务后导出，不自行处理 B 线申请。无新用户待答，未改产品代码或服务。
- 下一步：完成服务核验与 handoff/M4/kickoff.md，分支 phase1/m4-paper-execution，开草稿 PR；不合并、不修改 docs/golden/milestones。

## A-003  已完成  2026-10-16 13:20 北京
- 按 main A-004 开头的需求方验证及用户批准例外收口：代码部分通过；PR #10 已由需求方合并，merge commit 61a97e139d80c1b43b4a5a72b30c7f2fa678483a。以下保留上一阶段代码/离线证据记录。
- 两项剩余证据已转交需求方查库：10-17 08:45 SEC 正式运行、10-16 全天 LLM 用量；A 不再为 A-003 手动运行任务。后文“待补/下一步”是转交前记录，以本条为准。
- 草稿 PR [#10](https://github.com/XuQingsong/inves-cog/pull/10)，分支 phase1/m1m2-fixes-a003。当前完整 head **481e0248944f5791cabdc111d681afed619e51bc**，本地/GitHub SHA 一致，代码树 2ef1e23e72bfb5c44a9dc5556619d6f07432d5b1。当前 SHA 的 phase1-blocking CI 绿：[run 38852874067](https://github.com/XuQingsong/inves-cog/actions/runs/38852874067)，隔离容器测试及 CI 断言均成功；nightly 按条件 skipped，不冒称本次云端回放。
- D-27 已修：UNH 原件 0000731766-26-000197 把医疗赔付与产品成本分列，旧 D4 漏扣医疗赔付。fixed 毛利率 88.571276% → **19.514184%**；医疗成本缺失/期间不匹配时 NULL 并记录 gross_margin_costs_incomplete，披露毛利、其他发行人、legacy 不误伤。先红 3 failed/3 passed（e6f3250a3532fbcd0cac7dfe4e76d7e195a229aa），再实现 a8b02437f19a399df7a1527476f5a6daf490755e；联合 M2 回归 21 passed。19 只审计已完成：17 只数字对照，GE/ORCL 原有 NULL 的具体原件成本口径缺口已说明，不编造数字。证据 handoff/M2/a003-gross-margin.json。
- D-27 实际写库：按 A-003 明确授权，以既有 role_ingest / role_trading 重算 **47** 份 UNH fixed 状态；其余核心字段一致。PR #7 已由需求方合并 9bbf15156a7a1a5beeba0ca692b986a4d9312025，因此用 main 未改动的 M3 重算 **198** 条 UNH fixed 分数（2026-01-02 至 2026-10-15），剩余 split_suspect **0 日**。证据 handoff/M2/a003-unh-rebuild.json，原状态备份留仓库外。
- D-26 原因已于 12:30、状态提交 0073c74f820c0e30d229e8e94e21b39ce44494ae 先登记再修：旧 collect_submissions 之外的正文/Form 4 请求没有公司级异常隔离，也没有完成游标，一次源故障终止全任务并从头重跑。历史最后成功正文为 NVDA 2015-000131，后两份 2015-000087/000013 未入库；旧泛化日志无法还原当时底层 transport 类型。本次基础端点与具体缺失正文探针成功，无 429/403 证据，不把“请求过快”当已证实原因。
- D-26 代码已提交：共享 SEC 客户端仍 ≤5 次/秒（含重试），复用连接；既有 source_cursors 存已完成/失败公司和去 query 的端点、HTTP 状态、异常类型链；未完成周期跨日恢复，完整周期次日刷新。单公司正文/解析失败隔离，权限/数据库错误仍抛出。先红 3 failed/2 passed（838fb6a576a1054bad042e03ddd8a5cd04fac7ad），跨日再先红 1 failed/6 passed（a045bf5ec69edecc13a4d7140a3fb6dac888efe1），最终 **7 passed**。证据 handoff/M1/a003-sec-diagnosis.json、a003-d26-*.xml。
- D-22 已完成核验：CompanyIR 不存在；EntitySites 无效演示行不存在；DashScope=ok 且有真实 embedding 成功记账。无需重复写库，证据 handoff/M1/a003-health-cleanup.json。以后演示只在测试库做。
- LLM：按美东预算日拆分，10-15 DeepSeek 已知 **6,902,548 token**；其中 3,206,900 来自更早发布条目，另 3,507,594 来自更早入库但缺发布时间的条目，两种历史处理依据分别登记；当天发布条目 188,054。缺 token 的调用仍单列为未知，GLM/embedding 分开统计。FR-M1-18 超 150 万后非池条目排队、池内继续是明确例外；现有正反回归通过，真实库约 1.3 万 daily_budget 排队条目。当前 10-16 只有部分日数据，**不冒称完整一天或稳态成本**。证据 handoff/M1/a003-llm-usage.json，oct16_complete=false。
- 全仓离线：**64 blocking + 2 replay passed、0 skipped**，Ruff 通过，包含 600 行/16,200 字段规则 A 回放。首轮因新增夹具缺 CHANGELOG 登记失败，输出保留；补登记后同一集合全绿，未改断言。阶段报告 handoff/M1/a003-self-test.md。
- 尚待两项真实证据：①美东 **10-16 20:45–21:15**（北京 **10-17 08:45–09:15**）完整 SEC job_runs；只读探针不算完整任务。验证前先查原服务任务结束，避免双进程并发，使用真实 SystemClock/Runtime 窗口，不改生产定时服务。②美东 10-16 预算日北京时间 **10-17 12:00** 结束后补全全天用量。输入未到窗口时不重复执行或打扰，不把 A-003 标已完成。
- 变更/自行决定：SEC 内部持久游标复用现有表、连接池复用现有传输；无新接口/表/迁移/依赖/数据源/权限/定时任务。按明确授权重算 UNH，不触碰其他模块。未改 PR #7/#8、docs、golden、milestones，未运行 Muse/stock-pm。无新用户决定或待答口径。
- 同步：推送前已成功 git pull --rebase 更新 agent-status；只改本文件、保留 B.md。代码通过官方连接器保留红绿提交历史发布，随后 Git fetch 成功，本地同步到相同完整 SHA。
- 下一步：复用既有自动化在真实窗口继续本任务，补齐 SEC 全跑和完整预算日后再提交验收。保持草稿，不合并，不开始 M4。

## A-002  已完成  2026-10-16 11:35 北京
- PR [#7](https://github.com/XuQingsong/inves-cog/pull/7)，新 head `2c93b5af2630e0d49ad3703a0239c63cff091735`；本地与 GitHub 完整 SHA 及代码树 `0cc283b5e3b480f4b8bdf993edc26052b94afe3b` 一致。
- 当前 head 的 phase1-blocking CI 绿：[run 38845929760](https://github.com/XuQingsong/inves-cog/actions/runs/38845929760)。隔离环境 blocking、M0 CI 断言与破坏性自测步骤均成功。
- 已为 kickoff §7 全部 21 条按原顺序补齐固定 Muse `aacea04e4562f70854d69330fe724aa2799f2858` 的文件/行号注释，分散的实现位置分别注明。原有注释全部保留；8 个 Python 文件仅新增 82 行注释，非注释 token、AST 与验收提交 `73a25d0` 完全一致。证据：`handoff/M3/a002-comment-only.json`。
- 对照表位置：[handoff/M3/self-test.md §4，AC-M3-03 后第 33 行起](https://github.com/XuQingsong/inves-cog/blob/2c93b5af2630e0d49ad3703a0239c63cff091735/handoff/M3/self-test.md#L33)，21 条完整映射到本项目文件/函数。
- 本机 blocking：51 passed、0 skipped（11.51 秒），`handoff/M3/a002-blocking.xml`；replay：2 passed、0 skipped（14.38 秒），`handoff/M3/a002-replay.xml`。`test_scores_match_muse` 及独立差异报告均为 **600 行、16,200 字段、零差异**，`handoff/M3/a002-replay-diff.json`。Ruff 通过。
- 首轮 blocking 唯一失败是执行沙箱禁止 AF_UNIX 本地通信探针，原输出保留在 `handoff/M3/a002-blocking-sandbox.xml`；用正常本机权限重跑同一离线测试集通过，没有改测试或门禁。
- 改动仅为 M3 注释、自测映射及回归证据。没有改计算、常量、断言、夹具、docs、golden、milestones 或 pending；没有处理 D-27/D-22/D-26，没有运行/导入 Muse，没有改 PR #8 或合并 PR。
- 已自行决定：M2 的 FCF/NI、EPS 提取与 M4 的 VIX 项仅在 M3 消费入口/边界注明归属；Git 直连不稳定时经官方 GitHub 连接器发布，并对公开提交完整 SHA 校验后同步本地，保留原历史。无新规则、接口、数据库、调度、来源或依赖变更；无新用户决策，流程疑问无。
- 状态推送前已尝试 git pull --rebase，遇直连超时；本回报经官方连接器按 A.md 当前 blob SHA 更新，只写 A.md，保留 B.md。
- 下一步：等待需求方复核 A-002。按一条线一个任务规则结束本轮；是否合并由需求方取得用户批准后执行。

## A-001  已完成  2026-10-16 11:13 北京
- PR [#7](https://github.com/XuQingsong/inves-cog/pull/7)（[M3] 提交验收）已合入最新 main `273be4a966909145aa1be8dc293887d85562805a`；当前完整 head `73a25d03505513c1ce28c703d5abb9cf067a77b2`，本地 M3 分支与 GitHub 一致。
- 当前 head 的 phase1-blocking CI 绿：[run 38844008192](https://github.com/XuQingsong/inves-cog/actions/runs/38844008192)。隔离环境 make phase1-test、M0 CI 断言及破坏性自测步骤全部成功；nightly 按触发条件未运行，不冒称本次回放重跑。
- 证据：上述 CI 运行及 `handoff/M3/self-test.md`（原 600 行、16200 字段回放零差异证据保留）。docs、golden、milestones 与 main 一致，没有自行修改；pending 相对 main 只删除已通过的 13 项 M3 测试。
- PR #8 保持不动，后续交 B 线。PR #5 已由需求方按用户批准合并，M1/M2 已关闭。agent 未合并任何 PR。
- 已读 ops/README.md（含 §4.1 用户决策同步）、ops/control.md；A 当前为“运行”。A 线只取 `ops/inbox/A/` 的最小未完成编号，一次做一条，范围 M3 → M4 → M5。
- 用户决策 UD-A-01：用户要求以后从 GitHub 信箱取任务，并提出“每次做完任务之后，就开启一个定时任务，监控你的 ops/inbox/A/ 里还没完成的任务，如果有，就直接开始开发”。执行方式：复用一个本线程自动化，每 10 分钟检查一次；有任务按协议接单、执行、回报，无任务或 A 暂停时结束本轮。影响：本线程自动接单及 `ops/status/A.md`，无产品接口或数据库变化。该决策已先在 11:08 进行中回报登记，再创建自动化。
- 变更：已启用本线程自动化 `a-github`（A 线 GitHub 信箱自动接单），ACTIVE，每 10 分钟一次；不重复创建，原 M1/M2 一次性跟进保持暂停。电脑需开机且 Codex 运行。
- 已自行决定：检查间隔先取 10 分钟；pending 合并保留 main 的 M1 删除及 M3 的 13 项删除；不重复执行已完成编号。流程疑问：无。
- 同步备注：本次推送前 git pull --rebase 遇 GitHub 直连超时；已通过官方 GitHub 连接器核对 A.md 当前 blob SHA，按文件 SHA 安全更新，只写 A.md，保留 B.md。产品 main/M3 已同步，本地状态分支将在直连恢复后同步。
- 下一步：等待需求方验收 M3；需求方取得用户批准后负责合并。下一次唤醒再取新信箱任务。
