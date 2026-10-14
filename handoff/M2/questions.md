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
