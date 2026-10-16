# A-003 自测与证据（进行中）

任务：`ops/inbox/A/A-003.md`。PR #10：`[M1/M2] 遗留修复 A-003`，保持草稿，未合并。当前完整远端 SHA 和对应 CI 由 `agent-status:ops/status/A.md` 记录。

## D-27：UNH 毛利率与重算

UNH 原件 `0000731766-26-000197` 的计算关系把医疗赔付 `PolicyholderBenefitsAndClaimsIncurredNet` 与产品成本 `CostOfGoodsAndServicesSold` 分列。旧推算漏扣医疗赔付。fixed 修正为两项都扣除，并核对币种、期间一致；缺项或错期时保留 NULL 和 `gross_margin_costs_incomplete` 原因。披露毛利优先，其他发行人和 legacy 口径保持原规则。

- 先红：`handoff/M2/a003-d27-red.xml`，3 failed、3 passed；修复后联合 M2 回归：`a003-d27-green.xml`，21 passed。
- 19 只审计：`handoff/M2/a003-gross-margin.json`。17 只数值对照原始 XBRL；GE、ORCL 原本就缺少支持的可比成本基准，逐项说明 NULL 原因，没有猜测发行人自定义成本加总。
- UNH 最新 TTM 毛利率：88.571276% → **19.514184%**。最近季度原件口径另列，未混淆季度与 TTM。
- 共享库实际重算 47 份 UNH fixed 状态，核心非毛利字段一致；PR #7 已由需求方合并，因此用 main M3 原代码重算 2026-01-02 至 2026-10-15 的 198 条 UNH fixed 打分，`split_suspect` 剩余 **0 日**。
- 写库角色为既有 role_ingest / role_trading，没有改权限或迁移。重算证据：`handoff/M2/a003-unh-rebuild.json`；原始状态备份在仓库外。

## D-26：SEC 失败隔离与断点

诊断已先登记在 agent-status，原始事实、只读探针和具体 URL 见 `handoff/M1/a003-sec-diagnosis.json`。旧日志仅保存泛化 transport 错误，无法还原历史底层网络异常；不能据此断言 SEC 限流。已证实的应用缺陷是正文/Form 4 请求在公司异常边界外、且缺公司续跑游标，导致一次请求失败终止全任务、下次从头开始。

- 一进程共享每秒 5 次预算（含重试），SEC 默认复用 HTTP 连接。
- 公司完成/失败/当前公司写既有 `ingest.source_cursors`；未完成周期跨日继续，完整周期在次日刷新。正文已存信息和 Form 4 身份仍幂等。
- 失败公司记录去 query 的端点、HTTP 状态、底层异常类型链；其他公司继续。数据库权限错误保持抛出。
- 先红 3 failed / 2 passed，另补跨日先红 1 failed / 6 passed；最终 7 passed。输出：`a003-d26-red.xml`、`a003-d26-crossday-red.xml`、`a003-d26-green.xml`。
- **真实完整运行尚待**美东 2026-10-16 20:45–21:15（北京 10-17 08:45–09:15）。当前只读端点诊断不冒充正式任务。验证时先核对原服务任务已结束，避免两个进程并发；不修改生产服务、时钟和采集窗口。

## D-22：健康表

`handoff/M1/a003-health-cleanup.json`：CompanyIR 和无效 EntitySites 演示行已不存在，DashScope 为 ok 且有真实嵌入成功记账。实际无需再写库；未来故障演示只在测试库执行。

## LLM 用量

`handoff/M1/a003-llm-usage.json` 按美东预算日、模型、任务、purpose、状态分开列出，嵌入单列。10-15 DeepSeek 已知用量 6,902,548 token，其中 3,206,900 token 的新闻发布时间早于调用日；另 3,507,594 token 的条目虽缺发布时间，但首次入库早于调用日，分别说明为历史处理依据。当天发布条目 188,054 token。缺用量的调用单列，不填 0。

FR-M1-18 的 150 万阈值限制非标的池排队；标的池完整处理仍允许。既有回归 `test_info_item_contract` 通过，覆盖超额时非池条目排队、池内条目继续。真实库已有约 1.3 万条 daily_budget 待处理记录。此次大头是历史处理，不能据此预测稳态日常成本。

**10-16 完整预算日尚未结束**，截至北京时间 10-17 12:00 才能补全；当前 JSON 明确 `oct16_complete=false`。这项与 SEC 完整运行补齐前，不标 A-003 已完成。

## 全仓验证

- `a003-blocking.xml`：64 passed、0 skipped。
- `a003-replay.xml`：2 passed、0 skipped，包含原 600 行/16,200 字段规则 A 回放。
- Ruff 通过。首轮完整测试因新夹具缺 CHANGELOG 登记而 1 failed / 63 passed，保留 `a003-blocking-first.xml`；补齐登记后同一集合全绿，未改断言或门禁。
- 没有编辑 docs、golden、milestones，未修改 PR #7/#8，未运行 Muse/stock-pm，未新建数据源、依赖、账号、迁移或定时任务。
