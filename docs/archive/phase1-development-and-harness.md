> **已归档**：本文已被 [`../system-spec.md`](../system-spec.md)（统一规格 v1.0）替代，只作历史记录，不得作为实现依据。

# 第一阶段开发需求与 Harness

> 状态：开工合同。实现时以本文的范围、顺序和测试为准；计算公式仍以被引用的文档为准，本文不重写公式。
> 代码落点：`XuQingsong/stock-pm`。本文档仓库只放需求，不放实现。
> 纸面研究，不下单，不构成投资建议。

---

## 0. 先读什么，冲突时听谁的

实现者只需要按这个顺序读。不要从更早的文档里重新发明规则。

| 顺序 | 文档 | 只用这些部分 |
|---|---|---|
| 1 | 本文 | 范围、顺序、Harness、完成定义 |
| 2 | [`universe-muse-spec-and-valuation-v1.md`](universe-muse-spec-and-valuation-v1.md) | 第 2 节池子、第 3 节规则 A（M-01 至 M-63）、第 4 节估值 v1 |
| 3 | [`trading-rules-a-plus-and-growth-stocks.md`](trading-rules-a-plus-and-growth-stocks.md) | 第 4–7 节。A+ 可以写进代码，**默认关闭** |
| 4 | [`phase1-daily-perception-and-learning-loop.md`](phase1-daily-perception-and-learning-loop.md) | 日级范围、三轨、复盘、先兆快照 |
| 5 | [`integrated-overview-and-feasibility.md`](integrated-overview-and-feasibility.md) | 第 3.1 节信息源（已定稿） |

| 主题 | 采用 | 不要实现 |
|---|---|---|
| 交易 | 规则 A，次日开盘成交 | `paper_tracker.py` 的固定止损止盈；文件头注释里的 15/12/5%、60/40/25% |
| A+ | 代码可存在，旗标默认 `false` | 旗标打开前不得影响纸面订单 |
| 估值 v1 | 只展示 | 第二部分第 19 节的仓位公式；V1/V2/V3 改仓位 |
| 池子 | 59 只股票 + 14 只基准 ETF；可交易最多 54 只 | 扩到 150 只 |
| 异常 | 每个交易日一次，含盘后收盘 | 盘中 5 分钟异常 |
| 下单 | 纸面 | 券商实盘 |

已确认、开工不必再问：信息源方案、规则 A、外国申报人只观察、估值 v1 的参数和展示方式、网络安全四只、BE 放入数据中心电力板块。v0.10 的 P1–P4 只影响 A+ 是否启用，不阻塞规则 A 开工。

---

## 1. 第一阶段交付

### 1.1 要交付

| # | 交付 | 用户能看到什么 |
|---|---|---|
| 1 | 行情、新闻、公告、财报、一致预期、榜单、搜索趋势入库 | 数据健康页：每只股票最新财报期、缺口原因、能不能打分 |
| 2 | 规则 A 的打分、红线、分层、纸面组合 | 盘前计划：每笔买、卖、不买都有规则编号 |
| 3 | 估值 v1 | 价值总表和个股卡，标题固定为「估值参考 v1，不参与仓位」 |
| 4 | 日级异常、回捞、规则打分的解释、三轨跟踪 | 异常清单和解释报告；没有信息 id 的候选不出现 |
| 5 | 复盘 | T+1 / T+5 / T+20 案例、每周漏检报告、先兆快照 |
| 6 | 覆盖层 | 只会暂停新买、加仓和撤未成交单 |
| 7 | 本文第 3 节的 Harness | 没过测试的改动不能合并 |

数据修复（v0.10 的 D1–D6：营收标签、第四季还原、companyfacts 滞后、毛利推算、净利润标签、健康页）属于本阶段，因为没有它们 LITE、BE、COHR 会静默没有分数。它们**不是**交易规则变更。v18 对账必须用「与 Muse 相同的旧提取器」；修复后的提取器单独出一份差异报告，不能拿去改 v18 的标准答案。

### 1.2 本阶段不交付

盘中 5 分钟异常、实盘下单、社交数据、融券费率、产业价格、A+ 启用、用估值或 p 改仓位、C3/C4 预警影响仓位、研究模块目标价进入交易。

---

## 2. 代码放在哪里

都在 stock-pm 里新增，不新建仓库，不把 Muse 源码拷进来。

| 包 | 职责 | 允许依赖 |
|---|---|---|
| `stock_pm.ingest` | 行情、新闻、SEC、预期、榜单、健康码 | 现有 `external`、数据库 |
| `stock_pm.trading` | 规则 A、纸面账本、订单理由 | `ingest` 的只读行情和财报；**禁止** `valuation_v1`、`brain`、`perception` |
| `stock_pm.valuation_v1` | 估值区间、变化分解、影子对照 | 财报只读；可读 `trading` 的只读快照，**禁止**写订单、禁止被 `trading` 引用 |
| `stock_pm.perception` | 异常、回捞、归因、三轨、案例 | 全量库、LLM 客户端；**禁止**写订单 |
| `stock_pm.overlay` | 冷静期、撤单 | 只产出「禁止买」标记，供 `trading` 读取 |

Brain 现有的 `FORBIDDEN_VALUATION_KEYS` 和 `tests/test_main_path_copy_gate.py` 保持不变。新 Harness 是加一层，不是替换。

A+ 若实现，放在 `stock_pm.trading.rules_a_plus`，只能由回测入口以参数 `rule_set="A+"` 调用。纸面任务写死 `rule_set="A"`。

---

## 3. Harness

Harness 要拦住的是已经发生过的问题：注释和常量不一致、两套卖出规则混用、财报缺口被当成 0 分、估值渗进订单、回测用了当时还不存在的股票、测试被改成跟着错误结果走。

### 3.1 层

| 层 | 标记 | 跑什么 | 每次提交 | 允许网络 | 允许 LLM |
|---|---|---|---|---|---|
| H0 静态门禁 | `phase1_blocking` | 导入关系、禁用词、常量、时钟、未登记的 skip | 是 | 否 | 否 |
| H1 纯函数 | `phase1_blocking` | 插值、红线、门槛、估值公式、健康码，输入是仓库里的小 JSON | 是 | 否 | 否 |
| H2 回放 | `phase1_replay` | 用冻结的日线和财报状态重跑 v18 | 每晚；改 `trading` 时也要跑 | 否 | 否 |
| H3 案例 | `phase1_cases` | 东芝、OpenAI、Meta Muse、DeepSeek 的冻结新闻 | 改 `perception` 时 | 否 | 只用录音 |

`phase1_blocking` 必须在 3 分钟内跑完。任何测试访问套接字即失败。时间只能从注入的时钟来：`trading`、`valuation_v1`、`perception`、`overlay` 里出现 `datetime.now(` 或 `date.today(` 即失败。

### 3.2 目录（stock-pm）

```
tests/harness/conftest.py          断网、注入时钟
tests/harness/pending.txt          尚未实现的测试，一行一个：测试名、所属工作包、原因
tests/harness/milestones.txt       已关闭的工作包编号
tests/harness/CHANGELOG.md         只有改标准答案时才写
tests/fixtures/phase1/             冻结输入和标准答案
```

`pending.txt` 的规则：

- 测试被 skip 或 xfail，但不在这个文件里 → 失败。
- 工作包编号已经写进 `milestones.txt`，这个文件里却还有它的测试 → 失败。
- 不允许用新增 skip 让红灯变绿。

### 3.3 改标准答案

标准答案一旦提交，就不能为了让新代码通过而改它。允许改的唯一情况：输入数据本身被证明错了，或规格文档先改了。PR 里要改 `tests/harness/CHANGELOG.md`，写明旧值、新值、原因、对应的规格编号。没有这条记录，golden 文件的 diff 直接失败。

### 3.4 不变量

每一行是一个永久测试。工作包列表示「这一包合并时，该测试必须从 pending 里删掉并转绿」。

| 编号 | 断言 | 测试 | 工作包 |
|---|---|---|---|
| I01 | `trading` 不导入 `valuation_v1`、`brain`、`perception`；`perception` 和 `valuation_v1` 不导入订单写入 | `test_import_firewall` | WP0 |
| I02 | 纸面任务的规则集是 `A`；A+ 旗标默认 false；旗标为 false 时，同一夹具的订单与纯规则 A 一致 | `test_rule_set_a_locked` | WP2 |
| I03 | 单票上限 12/12/8，首笔 50/40/30，层预算 30/30/40。不是注释里的 15/12/5 和 60/40/25 | `test_v18_constants` | WP2 |
| I04 | 规则 A 的源码和订单理由里没有 −8/−12/−18、+15/+20/+25 这组固定止损止盈 | `test_no_tracker_stops_in_rule_a` | WP2 |
| I05 | 订单理由只含 `M-` 编号；不含「悲观 / 中性 / 乐观 / 目标价 / p= / 估值区间」 | `test_order_reason_tokens` | WP3 |
| I06 | 订单只能由规则引擎发出。感知报告、LLM 文本、估值行都不能产生订单 | `test_orders_only_from_engine` | WP3 |
| I07 | 信号日收盘生成，成交日是下一交易日开盘；同一天先卖后买；金额低于权益 0.5% 不下单；成本 0.1% | `test_fill_timing_and_cost` | WP3 |
| I08 | 财报 `filed` 晚于信号日的记录不得进入打分 | `test_pit_filed_date` | WP2 |
| I09 | 营收最新期间早于信号日 180 天以上：质量、成长、估值三本账为**空**，健康码 `stale_fundamentals`，页面不能显示 0 分，也不能显示可买 | `test_stale_books_are_null` | WP1 |
| I10 | 只有 `IncludingAssessedTax` 营收标签的夹具，在修复关闭时健康码 `revenue_tag_gap`；修复打开后序列连续 | `test_revenue_tag_gap` | WP1 |
| I11 | 10-K 只有全年数时，修复打开后第四季 = 全年 − 前三季；修复关闭时健康码 `q4_missing` | `test_q4_derived_from_annual` | WP1 |
| I12 | submissions 已有 10-Q、companyfacts 没有该期：健康码 `companyfacts_lag`，不得把上一期标成最新 | `test_companyfacts_lag` | WP1 |
| I13 | ASML、ARM、TSM、SKHY、NOK 的状态是只观察，候选扫描结果为空 | `test_foreign_filers_not_tradable` | WP2 |
| I14 | 回测成员按当天：SNDK、CRWV 上市前不在池里 | `test_membership_asof` | WP3 |
| I15 | v18 冻结回放：区间 2026-01-02 至 2026-10-07，初始 100 万美元，收益 +49.45%（±1 个百分点），最大回撤 −12.64%（±0.5 个百分点），90 笔；交易清单匹配率 ≥ 95% | `test_v18_replay` | WP3 |
| I16 | 2026-01-12 AMD 试仓在回放中存在，成交在次日开盘，理由含进攻层，原始估值分按冻结输入是 22 | `test_amd_entry_2026_01_12` | WP3 |
| I17 | 估值三档不读现价。只改价格时悲观、中性、乐观不变，p 变 | `test_valuation_ignores_price` | WP4 |
| I18 | 悲观 ≤ 中性 ≤ 乐观；同一输入两次结果相同 | `test_valuation_monotone_and_stable` | WP4 |
| I19 | 关掉估值模块后，WP3 的订单夹具字节级不变 | `test_trading_without_valuation` | WP4 |
| I20 | 迁移脚本里，交易库角色对 `valuation_v1` 没有 SELECT | `test_valuation_schema_revoke` | WP4 |
| I21 | 价值总表和处置卡含固定句子「估值参考 v1，不参与仓位」 | `test_valuation_label` | WP4 |
| I22 | 分钟线任务的结束时间是美东 20:00，不是 16:30 | `test_bar_window_to_20et` | WP1 |
| I23 | 每个异常有处置状态；没有信息 id 的候选被丢掉；冲击分解三项之和等于当日剩余涨跌（允许 0.1 个百分点舍入） | `test_anomaly_contract` | WP5 |
| I24 | 覆盖层只能删除买单或减小数量，不能新增买单、不能提高数量 | `test_overlay_only_tightens` | WP6 |
| I25 | 案例在 T+1、T+5、T+20 各有一条记录；缺一条则该案例状态为未完成 | `test_case_cadence` | WP6 |
| I26 | Brain 的 `FORBIDDEN_VALUATION_KEYS` 仍是 `fair_value`、`price_target`、`target_multiple`、`target_pe`、`dcf` | `test_brain_valuation_keys_unchanged` | WP0 |

I15 的标准答案来自 Muse `aacea04` 的 `paper_trade_v18full_trades.json`（最终权益 1,494,527.34，SPY 同期 +13.98%）。把该文件的摘要和交易清单冻结进 `tests/fixtures/phase1/v18/`。回放吃的是同一目录里已经抽好的日线字段和财报状态，不在测试里访问 Nasdaq 或 SEC。

I16 用来防止「总收益对了、过程全变了」。AMD 是规则 A 买过高 PE 成长股的实证，必须留在回放里。

### 3.5 冻结夹具

| 路径 | 内容 | 谁产生，之后谁也不能随手改 |
|---|---|---|
| `v18/summary.json`、`v18/trades.jsonl` | I15、I16 的标准答案 | 从 Muse `aacea04` 拷贝一次 |
| `v18/inputs/` | 30 只股票在回放区间的技术字段和财报状态，外加 SPY、VIX | 用旧提取器生成一次，写入 CHANGELOG |
| `scores/interp_points.json` | 四本账每条曲线的端点和中点，手算期望分 | 按 v0.9 第 3.4 节 |
| `health/lite_tag.json` | 只含新营收标签的假 companyfacts | 按 I10 |
| `health/fy_10k.json` | 前三季加一份全年数 | 按 I11 |
| `health/be_lag.json` | submissions 有 10-Q，facts 没有 | 按 I12 |
| `valuation/synthetic.json` | 五种类型各一组假输入和手算三档 | 按 v0.9 第 4.4 节，不用真实行情 |
| `cases/*.json` | 四个案例的价格、新闻 id、期望候选名称 | 案例夹具齐了才能做 WP5，不能先写死空测试然后永远 skip |

每月可以另跑一次「夹具是否过期」：用当前提取器重新抽取，只出差异报告，**不自动覆盖** `v18/inputs`。

### 3.6 运行失败时怎么停

测试只覆盖已知夹具。每天真跑时也要有同样的停机条件，否则线上会静默用空数据：

| 情况 | 行为 |
|---|---|
| 某只股票行情缺失 | 这只不打分、不交易，健康页写 `no_bar`；其他股票继续 |
| 财报过期或健康码不是 `ok` | 三本账为空，不产生买入 |
| 当日可交易股票里行情覆盖率低于 95% | 不发布盘前计划，页面写「今日计划未发布」和缺失清单 |
| 估值计算抛错 | 估值页该行写失败；交易照常，因为交易不读估值 |
| LLM 超时 | 该异常标「待分析」，不阻塞其他异常，不产生订单 |
| 覆盖层服务不可用 | 交易按没有额外限制继续，并在计划上写「覆盖层未接通」 |

---

## 4. 工作包

一个 PR 只做一个工作包。该包的测试在同一个 PR 里转绿，并且没有把已绿的测试改红。先写失败的测试和夹具，再写实现。

### WP0 门禁骨架

建立第 3.2 节的目录、断网夹具、I01、I26，以及「未登记 skip 即失败」。此时 I02–I25 都在 `pending.txt` 里，并注明所属工作包。

完成：`pytest -m phase1_blocking` 为绿；pending 清单与本文第 3.4 节一致。

### WP1 数据与健康

按 v0.8 第 3.1 节接入 Alpaca News、盘后至美东 20:00 的分钟线、广域日线、App Store RSS、Google Trends、59 只的 companyfacts 和一致预期。实现 v0.10 第 6 节的修复开关：`extractor=legacy` 与 `extractor=fixed`。健康页使用 I09–I12 的码。Muse 的历史一致预期、Form 4、VIX 只导入数据，不导入连接配置。

完成：I09、I10、I11、I12、I22 转绿。用 `fixed` 对 LITE、BE、COHR 跑一次，健康页不再是 `stale_fundamentals`，结果写入 PR 说明，不写入 v18 标准答案。

### WP2 规则 A 打分

按 v0.9 第 3.2–3.8 节实现纯函数：插值、四本账、红线、分层、确定性、资格分、入场。不写订单。

完成：I02、I03、I04、I08、I13 转绿。`scores/interp_points.json` 全部命中。

### WP3 纸面执行

按 v0.9 第 3.9–3.12 节实现持仓、加减仓、卖出优先级、波段、黑天鹅、回撤、VIX 闸门。吃 `v18/inputs`，输出订单。

完成：I05、I06、I07、I14、I15、I16 转绿。匹配率不足 95% 的差异逐笔写在 PR 里；不允许改 `trades.jsonl` 来抹平差异，除非符合第 3.3 节。

### WP4 估值 v1

按 v0.9 第 4 节实现五种类型、p、置信度、变化分解。影子记录「假如 V1/V2/V3 生效会怎样」，只写估值 schema。

完成：I17–I21 转绿。价值总表 59 行，不能估值的写明原因。

### WP5 日级感知

按 v0.7：剩余涨跌、异常清单、72 小时回捞、LLM 候选、规则打分、隐含幅度、冲击分解、三轨。LLM 在测试里只回放录音。

完成：I23 转绿。四个案例的正确候选进入前 3。案例夹具没提交之前，WP5 不得宣称完成。

### WP6 复盘、覆盖层、页面

页面至少四块，每块都有可供测试调用的 JSON，而不是只靠截图：

| 页面 | JSON 必须含有 |
|---|---|
| 数据健康 | 代码、最新财报期、健康码、能否打分 |
| 盘前计划 | 动作、规则编号、理由、规则集 `A` |
| 价值总表 | 三档、p、置信度、固定标注句 |
| 异常与案例 | 处置状态、信息 id、T+1/T+5/T+20 |

覆盖层按第 1.1 节第 6 项。先兆快照从第一天起每天存，缺失项写明，不拿去改交易。

完成：I24、I25 转绿。

---

## 5. 每天怎么跑

时间是北京时间、夏令时。任一步失败按第 3.6 节停，不使用空结果继续。

| 时间 | 步骤 | 包 |
|---|---|---|
| 08:00 | 日线、盘后收盘、广域日线、新闻、公告、榜单入库；健康码 | ingest |
| 08:20 | 异常、回捞、解释草稿 | perception |
| 10:30 | 财报和预期；估值重算；规则 A 打分 | ingest、valuation_v1、trading |
| 12:30 | 昨日案例打标 | perception |
| 20:00 | 盘前复核、覆盖层、盘前计划 | overlay、trading |
| 20:55 | 纸面成交（信号来自上一交易日收盘） | trading |

A+ 回测不进这张表。它是手动命令：`rule_set=A+`，输出对照报告，不写纸面账本。

---

## 6. 完成第一阶段的定义

同时满足才算第一阶段完成：

1. `milestones.txt` 含有 WP0 至 WP6，`pending.txt` 为空。
2. `phase1_blocking`、`phase1_replay`、`phase1_cases` 都绿。
3. 纸面计划连续 5 个交易日生成，健康页没有「可买但账本为空」。
4. 估值服务停掉后，第 5 个交易日的计划与前一日同一输入下的计划一致。
5. CHANGELOG 里每一次 golden 改动都有规格编号。

A+ 的启用不在这个定义里。启用需要 v0.10 第 7.3 节的回测报告，并且另一次把 I02 的期望从「旗标 false」改成「已批准」，同时改 CHANGELOG。

---

## 7. 实现时不要做的事

- 不要为了通过 I15 去改交易规则或改 `trades.jsonl`。
- 不要把 `extractor=fixed` 的结果写进 v18 夹具。
- 不要在规则 A 的 PR 里打开 A+，也不要把第 19 节的仓位公式接进下单。
- 不要用真实密钥、数据库连接串或当天的在线行情当测试输入。
- 不要跳过测试。缺夹具就保持红灯，直到夹具按第 3.5 节提交。
