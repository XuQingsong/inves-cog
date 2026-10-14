# M2 需求答复与实源核对

基线已合入 main e7db5a9（M2 v3）。K13、K14 已写入 Q-M2-16/17 并实施；下列旧段落是历史记录，不代表仍缺 key 或仍未实现。当前待决定项只有文末 K15。


基线 main：4e217a0。已先提交失败测试：633d141a0e450c058b843c2d517b0821a50a19a9；17 个测试全部存在，15 个 blocking 首次全部失败；尚未提交实现。replay 保留“等待 R7（Muse 导出）”，live 保留“等待 R4/R5/R7”。

## K13：M0 干净环境断言排斥任何后续迁移

`tests/harness/test_m0_ci.py:13` 写死 `record['migrations']` 只能为 M0 一项，而 `scripts/phase1.py` 正确执行并记录全部迁移。加入 M2 必需迁移后，干净环境 CI 会必然失败。

详细证据、建议与授权边界见 [M1 questions.md](https://github.com/XuQingsong/inves-cog/blob/phase1/m1-market-info-ingest/handoff/M1/questions.md) K14：建议对完整迁移清单作动态一致性断言，并保留 M0 必需项与其他环境断言。请求需求方 main 修正基线，或给 M1 明确例外；M2 随后合入修正，不独立改 M0、不自建共享客户端或共享表。

按任务书 §4.1 第③步，此问题发布后暂停实现，等待答复。中期 checkpoint 尚未达到，不把合成数据或未取得的 oracle 声称为真实结果。

## K14：非美元财报如何满足“金额一律美元”？

README §3.3 写“金额一律美元”，M2 v2 Q-M2-13 要支持外国申报人的年度字段及 IFRS 标签。但文档没有指定外汇来源、可见时点、期间流量用平均汇率还是期末汇率、即时余额/每股值如何换算。ASML 的官方 2025 财报以欧元披露：

- [官方年度财务摘要](https://www.asml.com/investors/annual-report/2025/financials)；
- [IFRS 原文](https://ourbrand.asml.com/m/6ea363f69344ebd4/original/asml-2025-annual-report-based-on-ifrs.pdf)。

不能把 EUR 当 USD，也不能自行增加外汇数据源、借当前汇率换历史，或把所有原币值静默丢掉。请明确以下二选一或另给合同：

A. 第一阶段遇到非 USD 时，目标金额字段为 NULL，保存原币原始值/单位证据和 `fx_missing` 的字段来源理由；同币种比率可计算，核心字段缺失仍按已有 `core_field_missing` 阻止评分，外国申报人继续不可交易。不引入新源。

B. 增加经批准的外汇输入；指定来源和列名、汇率方向、流量/余额/EPS 的日期或平均规则，以及 PIT 可见性；R5 未到位时冻结汇率夹具，缺汇率仍 NULL。

此问题影响 foreign annual/IFRS 和分部美元金额。按任务书 §4.1 第③步暂停 M2 实现，等待答复。Muse 的 30 份原始 companyfacts 和 90 组独立 oracle 已下载并验证哈希对应关系，R7 文件不会被自行改写；未执行、导入或复制 Muse 源码。

## K14 汇率接口调研（2026-10-14，换算合同仍待答复）

用户要求先调查可用的汇率接口，未授权自行确定财报换算规则。本次只读官方资料，不接真实账户、不改变原币夹具，不实现换算。

### 推荐：沿用已有数据源 FRED / ALFRED

官方 HTTP 接口：`https://api.stlouisfed.org/fred/series/observations`；参数包含 `series_id`、`observation_start/end`、`file_type=json`、`realtime_start/end` 或 `vintage_dates`。需要 FRED API key（已有 R5，尚未到位）。版本参数可取得指定历史日期当时可见的数据；默认参数返回今天已修订的历史，不能用默认值替代 PIT。

| 原币 | 序列 | 官方方向 | 换成美元 |
|---|---|---|---|
| EUR | DEXUSEU | USD / 1 EUR，日频 | 原币金额 × 汇率 |
| TWD | DEXTAUS | TWD / 1 USD，日频 | 原币金额 ÷ 汇率 |
| KRW | DEXKOUS | KRW / 1 USD，日频 | 原币金额 ÷ 汇率 |

这些序列来自美联储 H.10，观察频率是日频，发布有延迟；不能将汇率观察日期误当成系统当天已取得它的时点。保留观察日期、FRED 可见版本、实际采集 UTC、序列/方向、原值/原币和换算公式。

官方依据：

- [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)
- [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
- [API key](https://fred.stlouisfed.org/docs/api/api_key.html)
- [EUR](https://fred.stlouisfed.org/series/DEXUSEU)、[TWD](https://fred.stlouisfed.org/series/DEXTAUS)、[KRW](https://fred.stlouisfed.org/series/DEXKOUS)

### 可选官方接口：ECB

ECB Data API 使用 `https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A`，以欧元为基准，支持起止日期和结构化响应；官网另有公开 XML 历史序列下载。当前官方参考汇率列表涵盖 USD、KRW 等，列表未列 TWD，不能据此承诺三个币种都能从同一参考系列取得。其参考汇率通常工作日约 16:00 CET 发布。它是新增来源，需要需求方确认，不用它绕过已有 FRED key 前置条件；也不自动与 FRED 混用。

- [ECB API 官方说明](https://data.ecb.europa.eu/help/api/data)
- [ECB 参考汇率与下载](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)

### 必须明确的业务口径

建议流量（营收、利润、现金流）和 EPS 使用其披露期间的日均 USD/原币参考汇率；先把每日方向统一，再求均值。余额（现金、债务、权益）使用期末汇率；TTM 由已换算的四个单季相加，不能拿当前汇率换整个历史 TTM。股数不换算，同币种比率使用原币计算。原币证据保留，缺失/非正汇率一律 NULL。

这仍是方案，以下细节不自行决定：采用哪个来源；流量平均是否只用期间有效观察及缺数覆盖要求；余额期末休市是否保持 NULL，还是明确允许最近已发布参考汇率并记录实际日期；新增 FX 输入的存储位置/字段及责任模块。现有“不能用前一天代替”规则下，不自动回填期末汇率。需求方确认后先提交失败测试和汇率夹具，再实现。

R7 原始 30 份 companyfacts 和 90 份独立 legacy oracle 已在 `41814bc` 提交；数据收到不等于实现完成，legacy replay 仍 pending，理由已从等待 R7 改为等待 M2 实现。真实 live 仍登记“等待 R4/R5/R7”。

## K14 需求方补充答复与实际缺口（2026-10-14）

用户采用 FRED 方案，并明确要求“缺的话，不要写 null，具体哪个缺，为什么缺，搞清楚问题”“不要用 null，我要解决这个问题”。据此，FX 取数/换算异常必须定位到币种、series、目标字段、期间、历史可见日和失败原因；不能用空值把未解决问题当成正常结果。未核实的换算停止写入，原币原始证据保留。此要求只处理本问题的 FX 缺口，不改变其他财报字段在文档中明确允许的 NULL。

已确认的事实与处理方向：

1. 当前开发进程未配置 FRED_API_KEY，项目没有本地 `.env`。这是接入配置缺失，尚未发出有鉴权的 FRED 请求，不能声称 FRED 缺 EUR/TWD/KRW 的历史数据。需求方表示拥有全部 key，已提供 `.env.example` 清单供本地配置。
2. 已收到的 30 只 legacy companyfacts 清单均为此次 Muse 对照集，未包含 ASML、ARM、TSM、NOK、SKHY。检查指定营收/EPS/现金标签，未发现该对照集的非 USD 核心单位。它不能证明外国申报人或外币转换已通过；外国申报人的实际缺口必须在取到其原始申报后逐项核对。
3. 官方美联储 EUR 原始序列有 `2025-12-31 = 1.1736 USD/EUR`，也有 `2026-07-03 = ND`、前一观察日 `2026-07-02 = 1.1448`。休市无报价与接口请求失败是两种问题，不能混为“汇率不存在”。这些是当前官网原始观察核对，不是当时 PIT vintage 已取得的证明。
4. FRED 官方说明其 `end-of-period` 聚合使用期内最后有效观察；节假日无报价不要求创造当日报价。可将期末金额使用的实际报价日及汇率单独记录，并注明期末聚合口径。原先提出“缺期末当天就 NULL”不再作为默认开发方案。最大回溯/异常停报的边界尚未获具体答复；不擅自设置天数，也不将很久以前的报价静默当作期末报价。
5. H.10 每周一 16:15 发布前一营业周的日数据，联邦假日则顺延。数据源提供日观察不代表每天实时发布；PIT 必须同时核对版本可见日和原始发布证据。发布未到时应标明等待哪次发布并停止该次换算，不借未来公布值算历史。

官方依据：

- [美联储 EUR 原始历史](https://www.federalreserve.gov/releases/h10/hist/dat00_eu.htm)
- [FRED 缺失观察的聚合规则](https://fred.stlouisfed.org/help/data/understanding-the-data/how-are-missing-values-treated-in-average-sum-and-end-of-period-aggregation-methods-2)
- [H.10 发布规则](https://www.federalreserve.gov/releases/h10/)

需要配置的是接口接入身份；不是请需求方手工提供汇率数值。接通后由本项目拉取并登记可核对的原始观察与版本，输出逐字段缺口清单。未把普通财报缺失数补成 0，也未改写任何 Muse 输入/oracle。

## K14 实现与真实核对完成

FRED key 已配置，EUR/TWD/KRW 历史版本均实测成功，证据见 self-test.md 和 fx-real-verification.json。2026-07-04 的期末聚合记录实际报价日 2026-07-02，不生成当日报价。真实接口 output_type=3 是带 series/vintage 列的宽表，已测试先行改用 output_type=1，逐行保留 realtime_start。无可见有效报价时抛包含币种/字段/期间/版本日/原因的 FXGap，停止金额写入。原币原始事实保留；此探针不替代 ASML/TSM/SKHY 的真实完整财报转换验收。

## K15：真实经营分部辅助轴与 Q-M2-11 单维度约束冲突

已验证的原件：NVDA 10-Q，accession `0001045810-26-000075`，官方目录 https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/ 。原 XBRL 实例已下载到忽略缓存，没有修改原件、docs 或 golden。

该实例 context `c-242`、`c-243` 只带以下两个明确维度：

- `us-gaap:StatementBusinessSegmentsAxis`：分别为 `nvda:ComputeAndNetworkingSegmentMember`、`nvda:GraphicsSegmentMember`；
- `srt:ConsolidationItemsAxis = us-gaap:OperatingSegmentsMember`（经营分部汇总层级，不是地域或产品轴）。

原 `us-gaap:Revenues` 分别为 41,331,000,000 和 5,412,000,000，合计 46,743,000,000，与该期间经营分部汇总 context `c-244` 的营收一致。原 `OperatingIncomeLoss` 分别为 28,363,000,000、2,242,000,000。当前实现按“只带这一个维度”拒绝这两个 context，因此分部数字缺失，不能声称 AC-M2-04/05 已通过。这个问题与 key、模型或行情来源无关。

需要需求方决定：是否仅将 `srt:ConsolidationItemsAxis = us-gaap:OperatingSegmentsMember` 加为业务分部 context 的辅助维度白名单？建议允许它与主业务分部轴共存，汇总 context 不作为额外分部相加；地域、产品、情景等其他附加维度仍拒绝。答复前不扩大维度规则。下一步按原测试名扩充“合法辅助维度放行、地域/产品混合仍拒绝”的失败断言再实现。
