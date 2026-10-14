# M2 v2 开发中新问题（等待答复）

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
