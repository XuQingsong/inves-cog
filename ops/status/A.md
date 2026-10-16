# A 线回报

> 只由 A 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## A-006  进行中  2026-10-16 17:18 北京
- 已读 main **47c6e592b7a7ee7cd616fef33ca5f9d055a1bc6a** 的 [ops/answers/A-006.md](https://github.com/XuQingsong/inves-cog/blob/47c6e592b7a7ee7cd616fef33ca5f9d055a1bc6a/ops/answers/A-006.md)，blob **de99ea7da9231af94e0f74fd4c9f70881a6f69bd**。需求方明确批准只给既有 role_trading、role_marketstate 授予 inves_cog 的 CONNECT；此处原权限阻塞已解除，不再等待或索要确认。
- 下一步：快进最新 main，执行这两项 CONNECT 并验证原 schema/table 权限未变，安装已合并 PR13/15 调度、重启并核对新进程；在本任务最终回报列语句/时间、服务 SHA/重启时间和今晚预计时段。
- 变更：仅已批准的数据库 CONNECT 和 A-006 服务切换；不做其他权限变更或生产迁移。M4 已正式提交验收，head459d91e、CI38878686128保持，不重复跑其测试、不开始 M5。状态推送前已尝试 git pull --rebase（超时），只改 A.md、保留 B.md。

## A-006  阻塞  2026-10-16 17:15 北京
- **M4 已完成开发并正式提交验收；A-006 整体仅部署尚未完成**。部署实际连接被数据库拒绝，需要需求方允许或执行给既有 role_trading、role_marketstate 授予 **inves_cog 数据库 CONNECT**。A-006 只授权 LOGIN 且明确不增加别的权限，故未自行授予 CONNECT、用管理员作长期账号或启动已知无法写库的新服务。未自动合并任何 PR。
- **[PR #12「[M4] 提交验收」](https://github.com/XuQingsong/inves-cog/pull/12) 已转正式**，完整 head **459d91ed407e945227e726a84cd3291898afc977**；本地/GitHub 完整 SHA 和代码树 **ca2b0aae3a355461087483bba94f7da64d59f5a4** 一致，工作树干净。[当前 SHA 的 CI 38878686128](https://github.com/XuQingsong/inves-cog/actions/runs/38878686128) **绿**，准确 head_sha 已核对；干净容器 make phase1-test、M0 CI 断言及破坏性自测成功。nightly 按条件未运行，不冒称夜间回放。
- M4 最终全仓离线 **114 passed、0 skipped（45.82 秒，含 4 replay）**，本模块 12 blocking/2 replay/1 live 全部规定名称存在；真实只读 live 已 **1 passed**，不是临时 TCP 服务。15 项 M4 pending 已在实际通过后删除，milestones 未动。最后代码 700bdbbcf264a3294c0a4c7f4f39ff94abe1d47d；完整报告 [handoff/M4/self-test.md](https://github.com/XuQingsong/inves-cog/blob/459d91ed407e945227e726a84cd3291898afc977/handoff/M4/self-test.md)，同目录 blocking-replay-final.xml、live-smoke.xml、database.json、overlay-demo.json。
- AC-M4-02：冻结区间 **90 笔日期/代码/动作/股数全部一致，匹配率 100%**；收益 **49.4527339798%**、最大回撤 **−12.6370184987%**、终值 **1,494,527.339798 美元**。replay.json 保留逐笔/权益，差异为空。前三个月 **36 笔、100% 一致**，收益 −4.4592360022%、回撤 −9.8453132174%，checkpoint.md/json 已交。Q-M4-9 全年负现金 0 天、最低 3377.696828 美元；Q-M4-10 因成交日分层选择不同的笔数/股数变化均 0。没有运行或导入 Muse，golden 只经 load_golden。
- **K04 已按 Q-M4-11 关闭**，不再等待答复：采用需求方选择 B，保留 v18 观察挂单独立名额。真实 10-09 十二核心 + HD 观察仓共十三只保留为合法正例；合成测试同时验证核心第十三名和观察第四名被拦。未自行采用原建议 A，未改 frozen 90 笔或核心计数公式。原容量失败提交 5258363 保留，questions.md 已改为已答复。
- 本轮先红后修两处本模块实现缺陷：北京 20:00–20:30 发布/18:00 覆盖层新鲜度曾用纽约固定小时近似，冬令时错一小时，先 **2 failed**（b04c09b）后 e5818e9 修复；缺账本持仓原本笼统显示 M-59，先 **1 failed**（aa6eb21）后 700bdbb 修正为 N8 缺失字段及已选价格退出理由，不改变交易决策。最终 114 项全绿，Ruff check/format 通过。全仓最初一次格式红灯和本机缺 Docker 的实际限制如实写进自测，没有跳过测试。
- AC-M4-05：five-day-plans.json 是**真实库输入的历史回放**，目标 10-09/12/13/14/15，每天 54/54 可交易美股行情、100% 覆盖；订单 **13/5/4/1/5**、跳过 **10/9/9/12/13**。M2 fixed PIT → 本项目 M3 历史纯函数；模拟北京 20:00，仅用于回放，不冒充准时调度。AC-M4-06 待需求方抽三天复核；1 次准时发布为合并后运维项，不挡 M4 合并。
- 实际 live 的生产源为 trading.daily_scores：10-15 只有 UNH 已发布快照，**53 只缺 M3 快照**明确列在 live-plan.json / upstream_scores_missing；没有用历史重算冒充已发布源。M4 生产迁移 0；持久化/幂等/恢复和 role_web 拒写在新建后已删除的独立测试库完成。没有新账号、没有生产 M4 表写入。
- D-32 [PR #14](https://github.com/XuQingsong/inves-cog/pull/14) 已由需求方合并 **b0c7aeabfb1277c7721fa7e9d35996871679282e**；原 head **0c5e0e8457f0943adc3364182852aec0e68b0a27**，[CI 38863229785](https://github.com/XuQingsong/inves-cog/actions/runs/38863229785) 绿。test_market_service_preserves_requested_tickers 先 1 failed 后 1 passed；仅两行产品修复，真实 requested tickers 不被 SIC 覆盖。
- M2 正式财报调度 [PR #15](https://github.com/XuQingsong/inves-cog/pull/15) 已由需求方合并 **47d0278b94a66af8414b20c8cf7ae7d60dfa7d45**；原 head **73789edbab9d8c82d0db93680ef02b1427f8150e**，[CI 38863699107](https://github.com/XuQingsong/inves-cog/actions/runs/38863699107) 绿。先 8 failed，再 ops 19 passed、全仓 97 blocking passed；只调原 M2 financials，不调用忽略 --tasks 且会启动 Yahoo 的 schedule 循环，不改 M2 源。
- **已完成部署准备、未切换服务**：Mac main 已从 a6dfeeefe784f51b4e5155b96712a7320bc9d4a1 快进到 **89ac6938978bc61eed9c7a86040bacce1d3a362c**，[该 SHA 的 main CI 38875292344](https://github.com/XuQingsong/inves-cog/actions/runs/38875292344) 绿。08:54 UTC 核无运行中 job。按授权仅给原有 role_trading/role_marketstate 开 LOGIN，随机密码只存私有 .env，未打印凭据；未建角色、未授新权限或跑生产迁移。
- **09:13:57 UTC 再次实测**：两个角色 LOGIN=true、database CONNECT=false；原有各自表 INSERT 权限正常。直接连接实际报 permission denied for database inves_cog。脱敏记录本机 .harness/service/a006-writer-setup.json；私有备份不入库。需要的最小补充仅为这两个角色的数据库 CONNECT，不加任何 schema/table 权限，未执行。
- 原服务尚未重启：scheduler **PID 51341**、watchdog **51364**、awake **3392** 仍 RUNNING，embedding 仍原 EXITED；进程启动基线仍为原 a6dfee，由于未切换不能声称新调度已运行。当前配置 hash 不变 **77e71fe4d5b20363019749f89d9465ea8c23b2357ed5e2f61c9bfd22953a34dd**。尚无 A-006 新服务重启时间。
- 条件满足并在窗口前部署后，ET 10-16 预计：bars/m6_market_inputs 20:20（北京 10-17 08:20），M6 ≥20:45 且输入完成（08:45 起），M2 21:15–21:45（09:15–09:45），M3 ≥22:30 且正式 M2 完成（10:30 起）。这些仍是预计时段，不是实际证据；issuer_profiles 本月已有成功，遵守月度门禁。
- 已自行决定：修本模块明确北京时段和持仓解释的实现错误；保留 v18 名额、成交和分层兼容语义，工程项不再重复提问。无新增用户直接决策。变更同步如上：既有角色 LOGIN 与私有写库连接已配置，CONNECT 尚缺；调度尚未安装。docs/golden/milestones 只继承 main，未改 M6 其他代码、M7、其他项目或生产服务。
- 输入指纹：最新 GitHub main **463470dc248b3dc16aad61fba8ddac420b332bd3**（相对部署基线仅 M7 文档/任务与阶段流程更新）；A-006 blob **db1dd29f659f47f902b7b416cda2e58d8d4ddf0e**；M4 含 Q-M4-11 blob **394308433316157932df12449cd124f3766b5a40**；PR #14/#15 均已合并；角色 CONNECT=false。本地与 GitHub 通过完整对象 SHA 校验同步，状态更新前已尝试 git pull --rebase（直连超时），只改 A.md、保留 B.md。
- 下一步：**需求方验收 M4；允许或执行两个既有角色的 CONNECT 后，A 执行剩余上线并补运行 SHA/重启时间**。A-006 未满足服务切换完成标准，保持阻塞；相同输入不重跑测试或反复打扰，不开始 M5、不自动合并或新建定时任务。

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
