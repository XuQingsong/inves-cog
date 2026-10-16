# A-005 运维与修复

任务：main `230713222019d8da6ea384135f4ca4fb239f0450` 的 ops/inbox/A/A-005.md。三项工作完成，交付 PR #13 待需求方验收；未开始 M4 实现。需求方后续 main `7b907ba692952845215faa7cd77e43204860c779` 已登记 D-32，安排 A-006 开头修复入口遮蔽。

## 1. 价格结构补算

只读探针确认 main 的 MarketService.run 把传入 universe 覆盖为 SIC ticker overrides（BKNG、SHW），见 marketstate-entrypoint-probe.json。已先在 agent-status 告知需求方；需求方将其登记为 D-32，交 A-006 修复，本 PR 不修改 M6/M7 文件。

本次数据补算直接复用同一 main 的 calculate 和 MarketService.put，显式传入各日可见成员；不是另写模型或修改公式。只以 role_marketstate 写 marketstate.daily/baskets/rotation/market，原 10-12 至 10-14 行已在仓库外备份，按日期事务覆盖。无共享库迁移。7 月至 10-13 没有历史广域快照，只使用种子集合；10-14/15 使用当日已存在快照，不倒灌未来成员。

marketstate-backfill.json：2026-07-01 至 2026-10-15 的 **75 个交易日**全部完成，耗时 937.869 秒。daily 13,834 行、baskets 4,350 行、rotation 4,950 行、market 75 行，共 **23,209 行**；写后独立只读查库与各日事务累计数一致。

10-14 NVDA、AMD、MSFT 的 close/post 六行均为 **m+s**；广域 1,294 只按 close 统计，SPY 单因子由原备份实际 **216** 只降为 **143** 只（m+s 1,139、m+s+t 12）。10-14 总覆盖 1,306 只、10-15 总覆盖 1,304 只；更早各日覆盖当时可见的 59 只种子，不冒称已有历史广域成员快照。计算复用未改动 main 模块；独立日期并行计算，父进程按日期串行事务写入。

## 2. 每日调度注册 PR

修改仅为 scripts/install_ingest_service.py、scripts/schedule_daily_modules.py 及 tests/ops/：

- 原 bars_prefill/bars_full/wide_universe 和 SEC submissions/index/atom 均保留，追加 m6_market_inputs 与 issuer_profiles。前者复用既有 VIX_CBOE/VIX3M_CBOE/7 ETF 采集；后者按现有每月首个交易周且当月未运行的规则调度。
- 新 daily_modules 常驻轮询器只调用既有模块 schedule 入口：M6 美东 20:45 起，且 bars_full、m6_market_inputs 均有当日已结束的 ok/degraded 记录；M3 美东 22:30 起，且有当日已结束的正式 financials/m2_financials 记录。模块原有 once-per-day 与等待条件保留。
- 时钟注入、XNYS 交易日、America/New_York 时区，涵盖 DST；一个模块失败不抑制另一个就绪模块。不调用真实源的测试验证了错误时段/缺前置应拦、正常时段/前置完整应放行。
- 首次实际运行须在用户批准合并、A-006 部署后发生；本轮 **没有安装/启用** 新注册，不宣称今晚已生效。日常输入首个可用时段 20:20 ET、价格结构 20:45 ET 且前置完成、打分 22:30 ET 且 M2 完成；当月 profiles 已有 10-15 记录，下一月首个正常交易日为 11-02。

先红：11 failed，scheduling-red.xml；再实现：11 passed，scheduling-green.xml；全仓 blocking：89 passed、0 skipped，blocking.xml；Ruff 与 diff 检查通过。没有修改现有 M6/M7 测试或其他模块 pending。

### A-006 上线前置（实际核对，未擅自处理）

1. 需求方已将上述 M6 正式入口参数遮蔽登记 D-32，并明确在 A-006 开头修正；注册代码复用正式入口，不把只算两只的结果当健康成功。
2. 当前私有环境缺 INVES_COG_TRADING_DATABASE_URL、INVES_COG_MARKETSTATE_DATABASE_URL，既有 role_trading/role_marketstate 为 NOLOGIN。未新建账号、授权或用管理员登录替代长期服务账号；需需求方安排安全的写入连接配置。这是内部数据库连接，不是向用户再索取模型 key。
3. 当前库未见 financials/m2_financials 正式任务记录，仅见历史 m2_live_financials 等验收任务。上线时需确认 M2 的正式财报更新调度，不能把 live 冒烟冒充 M3 的前置日常任务。本 PR 不擅自开启 M2 全套采集，尤其不启用被禁止重试的 Yahoo 一致预期。

私有服务配置哈希及变量存在性（不含值）见 deployment-preflight.json。生产服务保持原四个程序；未改配置、未重启程序。

## 3. Alpaca 指定分钟缺窗

minute-gap.json：真实 SIP/raw 请求 73 只，UTC [2026-10-15 16:57,18:11)（ET 12:57–14:10，含最后一分钟），完整翻页后仍 **0 行**。库内前后均 0，新增 0。

已写真实健康记录 AlpacaMinuteGap:2026-10-15:12:57-14:10ET，status=degraded，说明“数据源仍缺”及请求时窗/代码数。没有补零、前值填充、换 feed、换源或造分钟线。

## 边界

不修改 docs、golden、milestones；不修改 M6/M7 代码、不执行 M7 迁移、不开始 M4。不合并任何 PR。A-003 剩余时间证据仍由需求方查库，本轮未为它手动运行任务。
