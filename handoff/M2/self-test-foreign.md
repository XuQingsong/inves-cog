# M2 外国申报人补充自测（AC-M2-09）

基线：M2 round3 871f625，已合 main c52fcc0；独立分支 phase1/m2-foreign-interims。先提交失败测试 ae6cd9d、7e45525、eea4313，再实现。此补充 PR 不影响 PR #4 的阻塞修复复核，不自行合并。

## 逐项结果

| 任务 / 条款 | 结果与证据 |
|---|---|
| 第6项 / Q-M2-28 | NOK 的旧 Revenue 标签止于2017，新 RevenueFromContractsWithCustomers 已到2025；fixed 增加 IFRS15 别名并优先原币。TSM 最新 companyfacts 的营收止于2024，但2026-04-16申报的2025年20-F原文含完整 IFRS 数据；使用本项目 Arelle 解析该实例补回。两者年度锚点均为2025-12-31，年度营收、NI、EPS美元值见 foreign-interims.json 的 annual_anchor。 |
| 第7项 / Q-M2-29 | ASML、TSM、NOK、ARM 均已入库连续四季度核心数字。按发行人固定布局读取，无 LLM；interim_results 保留原币金额、普通股EPS、ADS换算比例及精确附件URL。用最新年度锚点后的四季度生成TTM，各季分别按PIT FRED日均换美元。ASML使用公告里的真实财季边界；NOK只取Reported，归母利润取parent而非集团或comparable；ARM只取GAAP。全部保留interim_unaudited，均不可交易。 |
| 第8项 / Q-M2-30 | TSM 最近12个月（2025-10至2026-09）月营收入独立表；优先法定明细NT$千元表，非舍入的NT$百万元摘要。档案中单独展示原币数据，不参与TTM。最新2026-09为TWD511,857,399,000；详见 foreign-interims.json。 |
| 第9项 / Q-M2-31 | SEC实际存在SKHY业绩6-K，不能写no_financial_filings_yet。2026-07-29预告只给营收、OP、归母利润，缺GP/EPS已逐项注明；2026-08-18完整报告已按固定表格解析六项核心数字，并冻结真实回归。可取得2026Q1/Q2及2025Q1/Q2比较数，但不是连续四季度；无年度锚点，不伪造TTM，健康页说明历史窗口缺口并继续禁止打分/交易。普通股EPS为KRW/股，公告未给ADS换算比，不用未知比例换算。 |
| 第13项 | 新迁移为phase1_m2_0004_interim_results.sql，与已有文件不重号；既有迁移不改名。 |

## 实源抽查（金额为原币百万，EPS为原币每普通股）

| 公司 / 季度 | 营收 | 毛利 | 营业利润 | 归母净利润 | 稀释EPS | 普通股与ADS |
|---|---:|---:|---:|---:|---:|---|
| ASML 2026-09-27，EUR | 11,662.0 | 6,699.8 | 5,172.8 | 4,960.4 | 12.93 | NASDAQ登记普通股，1:1；非ADS |
| TSM 2026-06-30，TWD | 1,270,381 | 860,311 | 766,603 | 706,562 | 27.25 | 1 ADS=5普通股 |
| NOK 2026-06-30，EUR | 4,815 | 2,146 | −50 | 2 | 0.00 | 1 ADS=1普通股 |
| ARM 2026-06-30，USD | 1,289 | 1,253 | 91 | 270 | 0.25 | 1 ADS=1普通股 |
| SKHY 2026-06-30，KRW | 79,318,746 | 65,991,356 | 60,542,608 | 93,820,236 | 131,478 | 普通股；本公告未载ADS比 |

各行原始SEC附件与实际filed在foreign-interims.json。测试夹具保存完整原文gzip、MANIFEST哈希与CHANGELOG；sources.json另列补充季度精确URL。NOK净利润2百万不是集团利润5百万，营业利润−50百万不是调整后434百万；ARM 2026Q4 GAAP净利润313百万不是相邻non-GAAP641百万。缺失值不当0写入。

## 测试与运行边界

原M2测试名不变；补充原test_companyfacts_lag内的规则、PIT、月营收隔离和服务集成断言。拒绝无关表格、无法确定列和缺失字段，并验证真实财务表不误伤。模拟旧月度申报日期覆盖季度状态的故障，重建各知识日期快照；未来季度和公告不能进入早期state_asof。legacy不参与新逻辑，90组Muse回放仍须零差异。

正式ForeignCollector使用共享SECClient（5次/秒、SEC_USER_AGENT）和共享job_runs/source_health；每个发行人独立失败，定时器在M2的21:15–21:45 ET槽运行interims。实源回填重用已下载的SEC原文/年度实例，不计作新的59只live smoke，不计作准时调度。外汇缺口抛FXGap并保留具体原因，不写伪造美元值。最终任务开始、结束、状态、四季及12个月清单见foreign-interims.json。

最终离线阻塞测试及回放证据分别为foreign-blocking.xml、foreign-replay.xml；当前完整SHA的CI链接见本PR。未改docs、golden、milestones或模型/Clock/网络门禁，未导入或执行其他项目代码。

股本凭证口径核对：[ASML官方股份说明](https://investor.asml.com/share-information)明确NASDAQ为登记普通股；[TSMC官方换算说明](https://pr.tsmc.com/english/news/1427)为每ADS五股；[ARM官方SEC申报](https://investors.arm.com/node/8216/html)为每ADS一股；[Nokia存托人通知](https://www.nokia.com/sites/default/files/2021-03/03ED1C_Nokia_Notice_03-01-21_clean.pdf)为1:1。上述网页只用于核对凭证口径，不作为季度财务数据替代源。
