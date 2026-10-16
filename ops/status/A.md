# A 线回报

> 只由 A 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## A-003  进行中  2026-10-16 12:30 北京
- 草稿 PR [#10](https://github.com/XuQingsong/inves-cog/pull/10)，分支 phase1/m1m2-fixes-a003，基线 main c1970adcda88305eb8800f1d1c65be6bae59dd78。远端先红提交 e6f3250a3532fbcd0cac7dfe4e76d7e195a229aa：D-27 3 failed、3 passed；后续实现尚未发布，当前红灯属于先测试历史，不冒称 CI 已绿。
- D-27 已查明：UNH 原件 0000731766-26-000197 的 XBRL 计算关系显示 PolicyholderBenefitsAndClaimsIncurredNet（医疗赔付）与 CostOfGoodsAndServicesSold（产品成本）是独立成本项；旧 D4 只扣后者。真实原件夹具复现 88.571276%→应为 19.514184%；本机实现回归 21 passed。19 只曾出现 gross_margin_derived 的标的正在逐只核对。PR #7 已合并 9bbf151，后续按任务重算 UNH fixed 历史分数。
- D-26 诊断事实（先登记再修）：原 job 5309 仅更新 NVDA 的 1559 条申报，最后成功正文为 2015-000131；紧接着尚未入库的正文为 2015-000087 与 2015-000013。旧实现对 collect_submissions 外的正文/Form 4 读取异常没有公司级隔离，也没有公司级续跑游标，单请求失败会终止整任务并下次从头来。原日志只保存泛化 SourceError，无法据此还原当时具体底层 transport 类型；本次三个基础端点及 2015-000087 正文实际复核成功，无 429/403 或请求过快的证据，不将限流猜测当结论。接下来为已证实的异常传播、续跑缺口加失败测试，并保留具体异常链与 URL（去 query）供下一真实时段核对。
- D-22 已只读核验：CompanyIR 不存在；演示 EntitySites 行不存在；DashScope=ok，已有真实 embedding 记账成功证据，因此不制造无意义写操作。将独立提交 handoff/M1/a003-health-cleanup.json。
- LLM 预算日界为 America/New_York。文档 FR-M1-18 的 150 万是非标的池条目的排队阈值，超过后仍允许标的池完整处理；现有 full() 保留这一例外。正在按 purpose、模型和任务核对实际日常/回补贡献，未把超过阈值自动判断为预算失效。
- 待真实证据窗口：M1 SEC 正式运行仍只在美东 20:45–21:15；10-16 完整预算日截至北京时间 10-17 12:00。继续先完成其余代码和离线验收，再用现有定时检查补齐，不改时钟或生产定时服务。
- 变更：D-27 仅 fixed 的 UNH 成本基准与缺医疗成本原因码；D-26 拟用既有 ingest.source_cursors 存公司进度，无新表/迁移/依赖/数据源。无新用户决策，未改 PR #7/#8、docs、golden 或 milestones。
- 下一步：完成 19 只审计、指定 fixed/UNH 数据重算、SEC 回归及隔离续跑实现；四项证据齐备前保持草稿，不合并。

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
