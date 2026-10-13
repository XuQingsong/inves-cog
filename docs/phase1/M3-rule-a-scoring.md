# M3 规则 A 打分

| 项 | 内容 |
|---|---|
| 文档版本 | v1 |
| 规格章节 | 9.1–9.8、9.13 |
| 依赖 | M1（日线）、M2（`state_asof`） |
| 关闭的不变量 | I02、I03、I04、I08、I09、I13 |
| 规模 | 中 |

## 1. 目标

把规则 A（Muse v18）的打分部分重写成纯函数：每只股票每天一份打分快照，回答"按现价，这只股票能不能买、为什么"。

对应需求："交易是从现价出发打分，分数够了就可以买"；"买卖先按现有回测里那套规则走"；"每只标的都要经过评分"。

## 2. 范围

**做**：技术字段（9.2）、价格派生字段、四本账（9.4）、综合排名分（M-12）、红线（9.5）、分层（9.6）、成长确定性、持有资格分、`fund_bad`、现金跑道（9.7）、入场门槛与 M-31 / M-32 / M-33、`consec_pass`（9.8 前半部分），以及规则集锁定和 v18 常量。

**不做**：候选排序与选股（M-34）、首笔比例（M-35 至 M-37）、加仓、卖出、波段、组合风控（这些都在 M4，因为需要持仓状态）；A+ 的任何规则；估值区间。

**边界澄清**：

- 本模块的输出是"打分快照"，**不产生订单**，也不知道持仓。
- M-20 分层只在新财报生效那天（以及股票首次出现时）重估；平时沿用上一次的层级。分层的"上一次"存在快照里。
- 外国申报人（ASML、ARM、TSM、SKHY、NOK）照常计算技术字段，财报字段按年度口径能算多少算多少，但 `tradable = false`，候选扫描结果里永远没有它们（I13）。
- 规格没写明的计算细节以 Muse `aacea04` 源码为准（README §3.9），开工复述时必须逐条列出。

## 3. 输入

| 输入 | 来源 |
|---|---|
| 日线、SPY、VIX | M1 `ingest.bars_daily`、FRED |
| 财报状态 | M2 `state_asof(ticker, signal_date, extractor)`；v18 复现用 `legacy`，纸面运行用 `fixed` |
| 健康码 | M2 `fundamentals.health` |
| 规则 A 常量 | `config/params/rule_a_v18.yaml` |

## 4. 输出

**`trading.daily_scores`**（每只每个信号日一行）：

`signal_date, ticker, extractor, rule_set('A'), params_version,`
`tech(jsonb：9.2 全部技术字段), derived(pe, peg, mktcap, ps, fcf_yield),`
`quality, growth, valuation, timing, timing_subitems(jsonb), rank_score,`
`red_lines text[], tier, tier_changed_on, certainty, certainty_points, hold_score, hold_ok, fund_bad, runway_ok,`
`m31_adjusted_valuation, m32_ok, gate_pass, entry_pass, consec_pass, tradable, null_reason`

- 三本账为空时 `quality / growth / valuation = NULL`，`null_reason` = 健康码；`entry_pass = false`。
- 页面和 API 不得把 `NULL` 显示成 0（I09）。

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M3-01 | 技术字段按规格第 9.2 节；200 日均线不足的日子 `entry_pass = false` 且 `null_reason = insufficient_history` |
| FR-M3-02 | 分段线性插值（M-10）、缺项重配权（M-11）；`requirements/m3_interp_points.json` 的全部曲线和用例必须命中 |
| FR-M3-03 | 四本账、综合排名分；`requirements/m3_books_synthetic.json` 三只合成股票的全部字段必须命中 |
| FR-M3-04 | M-07 财报过期 → 三本账为空；M-08 拆股疑似 → 估值账为空 |
| FR-M3-05 | 红线 M-13 至 M-18；"排除"类（M-13、M-14、M-15）阻止入场；"不追高"（M-18）记录供 M4 阻止新开和加仓；"只观察"（M-16）和"等价格"（M-17）只是标签 |
| FR-M3-06 | 分层 M-20 至 M-23；质量或成长为空时 `tier = NULL`（不能交易） |
| FR-M3-07 | 成长确定性 M-25；持有资格分 M-26；`fund_bad`；现金跑道 M-27 |
| FR-M3-08 | 入场门槛 M-30、M-31、M-32、M-33；`consec_pass` 每天累计，不过线归零 |
| FR-M3-09 | 规则集锁定：打分函数只接受 `rule_set='A'`；传入其他值抛错（I02） |
| FR-M3-10 | 常量：`rule_a_v18.yaml` 中单票上限 12 / 12 / 8、首笔 50 / 40 / 30、层预算 30 / 30 / 40（I03）；源码和配置中不出现 −8 / −12 / −18、+15 / +20 / +25 这组固定止损止盈（I04） |
| FR-M3-11 | PIT：只通过 `state_asof` 取财报，不得直接查表（I08） |
| FR-M3-12 | 每天北京 10:30 后、财报和一致预期同步完成后运行；写 `job_runs` |

## 6. 异常与降级

| 情况 | 行为 |
|---|---|
| 某只行情缺失 | 该只当日不出快照行；健康页 `no_bar` |
| 财报健康码不是 `ok` 类 | 三本账为空，`entry_pass = false` |
| VIX 或 SPY 缺失 | 打分照常（打分不用它们）；M4 的闸门按 M4 文档处理 |

## 7. Harness 与自测

| 测试名 | 标记 | 断言 | 夹具 |
|---|---|---|---|
| `test_interp_points` | blocking | 全部曲线用例命中（容差 1e-6） | `requirements/m3_interp_points.json` |
| `test_books_synthetic` | blocking | 三只合成股票的派生字段、四本账、子项、排名分、红线、层级、确定性、资格分、`fund_bad`、跑道、M-31、`entry_pass` 全部命中 | `requirements/m3_books_synthetic.json` |
| `test_red_line_boundaries` | blocking | `rsi = 80`、`dev50 = 15` 不触发 M-18；`rsi = 80.01` 且 `dev50 = 15.01` 触发；M-13 三个条件缺一不触发 | 合成 |
| `test_tier_reassess_only_on_filing` | blocking | 无新财报时 `vol60` 变化不改层级；新财报生效当日重估 | 合成序列 |
| `test_m31_m32` | blocking | M-31 只对进攻层且成长 ≥ 70 生效、上限 65；M-32 烧钱保护 | 合成 |
| `test_stale_books_are_null` | blocking | I09 | 合成 |
| `test_split_suspect_valuation_null` | blocking | M-08 | 合成 |
| `test_pit_filed_date` | blocking | I08 | 合成 |
| `test_foreign_filers_not_tradable` | blocking | I13 | 配置 + 合成 |
| `test_rule_set_a_locked` | blocking | I02 | —— |
| `test_v18_constants` | blocking | I03 | 配置 |
| `test_no_tracker_stops_in_rule_a` | blocking | I04 | 源码扫描 |
| `test_scores_match_muse` | replay | 30 只、v18 区间内随机 20 个信号日：四本账、红线、层级、`entry_pass` 与 Muse 冻结输出一致 | 冻结输入（与 M2 共用 Muse 产出） |

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应需求 | 阻塞 |
|---|---|---|---|---|
| AC-M3-01 | 第 7 节 blocking 测试全绿 | H | FR-M3-01–12 | 是 |
| AC-M3-02 | `test_scores_match_muse` 全绿；不一致的逐条解释，并且每条都能对应到开工复述里登记的 Muse 源码细节 | H + E | "先按现有回测规则走" | 是 |
| AC-M3-03 | 开工复述中列出的全部"以 Muse 源码为准"的细节已写入本文 Q&A，并在代码里有对应注释或常量 | E | 防止口径漂移 | 是 |
| AC-M3-04 | 用真实数据跑 2026-10-09：AMD、ANET、VRT、GEV、ETN、CEG 的四本账与规格第 10.1 节"现算"表一致（容差 0.5 分；LITE、BE、COHR 用 `fixed` 提取器另出一份） | E | 诊断可复现 | 是 |
| AC-M3-05 | 59 只每天都有快照行或明确的 `null_reason`；页面 JSON 中空账本为 `null` | E | "每只标的都要经过评分" | 是 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M3-1 | 进攻层和防守层条件同时满足时谁优先？ | 以 Muse 源码为准（需求方标准答案按"进攻优先"计算，三只合成股票都不触发这种冲突）；开工复述时确认 |
| Q-M3-2 | 需求方标准答案与 Muse 源码不一致怎么办？ | 开发提出，需求方核对后修正标准答案或在本文写明例外；开发不得自行改标准答案 |
| Q-M3-3 | `fcf_conversion` 在 `ni_ttm ≤ 0` 时怎么算？ | 以 Muse 源码为准，开工复述时确认 |
