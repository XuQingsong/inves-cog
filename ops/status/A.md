# A 线回报

> 只由 A 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## A-005  已完成  2026-10-16 14:31 北京
- 已完成 A-005 三项运维/修复，提交正式待审 PR [#13](https://github.com/XuQingsong/inves-cog/pull/13)“[ops] 每日调度注册（A-005）”，分支 ops/a005-daily-scheduling。完整 head **8d3aa5a762f564ecfd6263a0dee6c9d9f0bc9241**，本地/GitHub 完整 SHA 与代码树 **70b54b2f06abbb7c6711b75b209e79f6fb770b2d** 一致，工作树干净。
- 当前 SHA 的 phase1-blocking CI 绿：[run 38861471796](https://github.com/XuQingsong/inves-cog/actions/runs/38861471796)，隔离容器测试和 CI 断言成功；nightly 按条件 skipped，不冒称夜间回放。本机 **89 blocking passed、0 skipped**；新增调度合同先 **11 failed**（363bd2da7c7f2df0e67a2a4e6b272f5895284750），后实现 **11 passed**（f8ed6ddf9d3109ea92dbd601a4ab7db7375f66ec）。Ruff、diff 检查通过。
- 价格结构：复用任务开始 main **230713222019d8da6ea384135f4ca4fb239f0450** 未改动的 calculate/MarketService.put，只写 marketstate，完成 **2026-07-01 至 10-15、75 个交易日**。daily **13,834**、baskets **4,350**、rotation **4,950**、market **75**，合计 **23,209 行**，覆盖旧 10-12/13/14；耗时 **937.869 秒**。独立只读查库计数与逐日写入累计一致；原行备份保存在仓库外。
- 指定核对：10-14 **NVDA、AMD、MSFT 的 close/post 六行均 m+s**；当日广域按 close 统计，仅 SPY（m）由原备份实测 **216** 降至 **143**，其余 m+s 1,139、m+s+t 12。10-14 总覆盖 1,306 只、10-15 总覆盖 1,304 只；更早没有历史广域快照，只算当时可见 59 只种子，不倒灌未来成员。
- 调度变更：仅改 scripts/install_ingest_service.py、新增 scripts/schedule_daily_modules.py 和 tests/ops/。保留现有 bars/广域/SEC 注册，追加日常 m6_market_inputs（CBOE VIX/VIX3M、7 ETF）及每月 issuer_profiles；M6 ≥20:45 ET 且日线/输入已完成，M3 ≥22:30 ET 且正式 financials/m2_financials 已完成，保留模块每日一次门禁；XNYS/美东含 DST，单模块失败隔离。正反断言覆盖正常放行、错误时段/缺前置阻拦。
- **新调度没有安装或生效**，生产原四程序配置 SHA256 写后仍为 77e71fe4d5b20363019749f89d9465ea8c23b2357ed5e2f61c9bfd22953a34dd；没有重启生产服务、改 .env、运行 M7 迁移或开新权限。合并后按 A-006 切换，不能把本 PR 当今晚已生效。
- 已核实的 A-006 上线前置：① M6 正式 MarketService.run 的 tickers 被 load_sic overrides 覆盖为 BKNG/SHW，无写入探针已证明；本任务禁止改 M6，已先回报。**需求方已在 main 7b907ba692952845215faa7cd77e43204860c779 登记 D-32，明确交 A-006 开头修复**（取代此前请求 B 修复的阶段建议）。② 私有环境缺 INVES_COG_TRADING_DATABASE_URL / INVES_COG_MARKETSTATE_DATABASE_URL，既有对应角色 NOLOGIN；未用管理员作长期账号，需部署时配妥写入连接。③ 库未见正式 financials/m2_financials 完成记录，部署时确认 M2 正式更新调度及首轮记录，历史 live 冒烟不算前置；未擅自启用 M2 全套采集或 Yahoo 重试。
- Alpaca 缺窗：真实 SIP/raw 重取 **73 只、10-15 ET12:57–14:10**（UTC [16:57,18:11)），完整请求 **0 行**，库内前后 0、新增 0。已写真实 source_health **AlpacaMinuteGap:2026-10-15:12:57-14:10ET**，degraded，明确“数据源仍缺”、窗口/代码数。没有造数、前值填充、换源或换 feed。
- 证据：[handoff/ops/A-005/self-test.md](https://github.com/XuQingsong/inves-cog/blob/8d3aa5a762f564ecfd6263a0dee6c9d9f0bc9241/handoff/ops/A-005/self-test.md)，同目录 marketstate-backfill.json（逐日及独立核对）、minute-gap.json、deployment-preflight.json、marketstate-entrypoint-probe.json、scheduling-red/green.xml、blocking.xml。
- 已自行决定：独立日期并行计算、父进程按日期串行事务写入；为避开已证实入口遮蔽，补算组合原 main 的 calculate/put 并显式传 PIT universe，没有改公式或另建模型。未新增接口/结构/依赖/来源/用户决定；调度变更已如上同步。不改 docs/golden/milestones、M6/M7 代码、不开始 M4；A-003 两项时间证据仍由需求方处理，未手动重跑。
- 同步：状态写入前已尝试 git pull --rebase（直连超时），经官方连接器按当前 A.md blob 安全更新，只改本文件并保留 B.md；代码分支原生 fetch 成功，已同步为远端相同完整 SHA，红绿历史保留。
- 下一步：**等待需求方验收 A-005 和用户批准合并 PR #13**；部署/入口 D-32/M4 实现留给之后下发的 A-006。本轮停止，不合并 PR、不创建后续自动化。

## A-004  已完成  2026-10-16 13:35 北京
- 已按 A-004 提交草稿 PR [#12](https://github.com/XuQingsong/inves-cog/pull/12)“[M4] 开工复述”，分支 phase1/m4-paper-execution。当前完整 head **e55361d5ec8ad5a7c827dd7a81102afd11427af9**，本地/GitHub SHA 与代码树 ad49f118f7d3202b32fac595f978e8a34730a5d6 一致；差异严格只有 handoff/M4/kickoff.md（162 行），没有实现、测试或迁移。
- 该 SHA 的 phase1-blocking CI 绿：[run 38856417633](https://github.com/XuQingsong/inves-cog/actions/runs/38856417633)。隔离容器 make phase1-test 与 CI 断言成功；nightly 按条件 skipped，不冒称已做 M4 回放。文档 diff 检查通过，工作树干净。
- 复述位置：[handoff/M4/kickoff.md](https://github.com/XuQingsong/inves-cog/blob/e55361d5ec8ad5a7c827dd7a81102afd11427af9/handoff/M4/kickoff.md)。已全文读 M4 v3、T04、整体/阶段任务书及适用 README/规格。逐条列出 15 项 FR、输入输出/降级、7 项 AC、15 个测试证明方案；含 trading.ledger/orders/plan 与 phase1_m4_0001_paper_ledger_orders_plan.sql 计划，以及前三个月 v18 收益/回撤/匹配率/逐笔差异中期检查点。
- 固定 Muse aacea04e4562f70854d69330fe724aa2799f2858 只读源码登记 **32 条**（文件/行号/结论），包含整数股 floor/int、信号收盘权益检查/次日开盘权益成交、稳定先卖后买、个股短路及组合队列顺序、同股多笔、M-58、含当日 252 窗口/min120/linear 的 VIX 90% 分位。仅通过 load_golden 预读 90 笔答案，明确不是新引擎回放通过；没有运行或导入 Muse。
- “必须停”三项（kickoff §6，未自行裁定）：**K01**：M-58“任何卖出”与 frozen 90 笔中的次日波段回买冲突，已举 MU/MRVL 07-17→07-20、MRVL 08-18→08-19 的实际答案；**K02**：源码按取整前 spend 检查 0.5% 且手续费不预留，和实际成交额/非负现金边界不同，附可手算边界；**K03**：源码成交时使用成交日完整 signals 的 tier，可能包含开盘时未知的分层，和实时 PIT 需裁定。各附 A/B 与倾向。其他工程项按保守/可逆记录为已自行决定，不反复提问。
- 服务前置项已实际完成：PR #10 经需求方合并为 61a97e139d80c1b43b4a5a72b30c7f2fa678483a 后，本地主仓库从 c1970ad 快进到本任务开始时最新 origin/main **a6dfeeefe784f51b4e5155b96712a7320bc9d4a1**。重启前只读核对无 running 采集任务；**北京 2026-10-16 13:23:52–13:23:58**（UTC 05:23:52–05:23:58）按既有 Supervisor 重启 scheduler 14313→51341、watchdog 98185→51364，再次检查均 RUNNING；实际 SECClient/Pipeline 模块路径与文件 blob 匹配 main。记录在仓库外 /private/tmp/inves-m4-sync/service.json。
- 变更：本次仅将现有两个常驻进程切到已合并 main；服务配置、任务参数、登录自启/自动拉起和 caffeinate 不变；embedding 已退出，未重启。没有手动采集/回填/用量调用/共享库迁移或新权限，未改 docs/golden/milestones、M6/M7 或其他 PR。
- A-003 已按本任务开头的用户批准例外收口，两项时间证据由需求方自行查库，本线**不再为 A-003 手动运行任何任务**。B 的数据申请只在需求方转成 A 任务后处理。无新增直接用户决定；规则变化来源为 A-004，不自行编辑 ops/README。
- 同步：状态推送前已尝试 git pull --rebase，Git 直连超时；经官方连接器按当前 A.md blob 安全写入，只改 A.md、保留 B.md。M4 已校验本地/远端完全一致；产品 main 用官方 Git 对象完整 SHA 校验同步后快进，未覆盖用户改动。
- 下一步：**停止，等需求方回答复述单 K01–K03 并发下一条任务**。本轮“已完成”仅指 A-004 开工复述，不代表 M4 实现或验收完成。不开始实现，不合并 PR，不新建自动化。

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
