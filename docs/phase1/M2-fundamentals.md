# M2 财报与基本面档案

| 项 | 内容 |
|---|---|
| 文档版本 | v1 |
| 规格章节 | 4.4、4.5、4.6、4.8、9.2（财报字段） |
| 依赖 | M0；SEC submissions 来自 M1 |
| 关闭的不变量 | I10、I11、I12、I33、I34 |
| 规模 | 中到大（设中期检查点） |

## 1. 目标

把"慢的基本面"按当时可见的口径建出来：季度财报（规则 A 用）、主营业务分部盈利、分析师一致预期，并合成每只股票一份基本面档案。数据有缺口时必须看得见、说得出原因，不能静默变成 0 分。

对应需求："公司基本面从主营业务的盈利、分析师一致预期、季度财报来建"；"基本面那里需要第一阶段做"；LITE、BE、COHR 现在因为采集缺陷没有分数。

## 2. 范围

**做**：

- companyfacts 和 XBRL 实例的采集（59 只，约 2009 年起）；
- 规格第 9.2 节全部财报字段的 PIT 季度状态序列；
- 两套提取器：`legacy`（与 Muse 一致，用于 v18 复现）和 `fixed`（打开 D1–D5）；
- 数据修复 D1–D7 和健康码；
- 一致预期每日快照的采集，Muse 历史快照的一次性导入；
- F1 分部盈利、F2 一致预期衍生指标、F3 基本面档案；
- 分部名称 → 图谱节点映射表的起草（`glm-5.3`）与审核队列；
- 数据健康页的 JSON。

**不做**：四本账打分（M3）；估值（M5）；基本面轨道的判断（M8）；页面渲染（M10，只提供 JSON）；分部加总估值。

**边界澄清**：

- 交易用哪套提取器：**v18 复现用 `legacy`；纸面组合日常运行用 `fixed`**。两套结果都保存，按 `extractor` 字段区分。
- "财报过期"（M-07）的判断在本模块产生健康码 `stale_fundamentals`；"三本账为空"的执行在 M3。
- 分部数据只来自申报原件的 XBRL 实例；不从新闻或电话会文字里抽分部数字。
- 一致预期快照没有历史，**不回补、不外推**；窗口不足的指标标"不足 N 天"。

## 3. 输入

| 输入 | 来源 |
|---|---|
| SEC companyfacts、submissions、XBRL 实例 | SEC 接口（M1 已拉取 submissions） |
| Muse 历史数据 | Muse `quant` 库导出：`estimates_trend`、`estimates_revisions`、`price_targets`、`earnings_history`；companyfacts 原始文件（可选，省时间） |
| 一致预期每日数据 | yfinance（非官方接口） |
| 图谱节点 | M6 的 `graph.entities`；M6 完成前映射表可以先起草，状态为"待审核" |
| 行业代码 | submissions 的 SIC |

## 4. 输出

**`fundamentals.fin_state`**（每次新申报一行，按 `filed` 生效）：

`ticker, extractor(legacy/fixed), accession, form, filed, period_end, fiscal_period` + 规格第 9.2 节全部财报字段（`rev_ttm`、`ni_ttm`、`rev_growth`、`rev_q_yoy`、`rev_accel_pp`、`eps_ttm`、`eps_growth`、`gross_margin`、`gross_margin_change_pp`、`fcf_ttm`、`fcf_margin`、`fcf_conversion`、`roe`、`cash`、`debt`、`net_debt`、`net_debt_fcf`、`current_ratio`、`shares`）+ `fcf_margin_change_pp`（F-02 用）+ `op_margin_ttm`（TTM `OperatingIncomeLoss` ÷ TTM 营收，M8 隐含幅度用）+ `health_codes text[]` + `field_sources jsonb`（每个字段来自哪个标签、是否推算）。

**接口** `state_asof(ticker, as_of_date, extractor) -> FinState | None`：返回 `filed ≤ as_of_date` 的最新一行；没有则 `None`。这是 M3、M5 读取财报的唯一入口。

**`fundamentals.segments`**：`ticker, accession, filed, period_end, period_len(Q/FY), segment_raw, segment_std(图谱节点 id，可空), revenue, segment_profit, profit_basis, margin_pct, yoy_pct, share_pct, recast_group, health_code`

**`fundamentals.segment_mapping`**：`ticker, segment_raw, graph_node_ids, drafted_by(glm-5.3), draft_reason, status(待审核/已确认/驳回), reviewed_at`

**`fundamentals.consensus_snapshot`**：`as_of, ticker, eps_cq, eps_nq, eps_cy, eps_ny, rev_cy, rev_ny, up_7d, down_7d, up_30d, down_30d, coverage, eps_high_cy, eps_low_cy, pt_mean, pt_median, source(yfinance/muse_import)`

**`fundamentals.consensus_derived`**：`as_of, ticker, chg_7d_pct / chg_30d_pct / chg_90d_pct（EPS 当年、次年，营收当年）, breadth_7d, breadth_30d, dispersion, surprise_last4, window_status jsonb`

**`fundamentals.profile`**（F3，每日每只一份 JSON）：主营业务、季度财报趋势、一致预期、定性锚（Brain 有基线时为链接，不复制内容）、基本面变化记录。

**`fundamentals.health`**（数据健康页 JSON 的来源）：`ticker, latest_period_end, latest_filed, latest_8k_202, health_codes, can_score(bool), can_trade(bool), reason`

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M2-01 | `legacy` 提取器逐行移植 Muse `screen_asof_2026_01_01.py:pit_fundamentals` 与 `paper_trade_2026.py:compute_books` 的取数部分；同一输入下与 Muse 输出逐字段一致 |
| FR-M2-02 | `fixed` 提取器 = `legacy` + D1（营收标签清单加入 `RevenueFromContractWithCustomerIncludingAssessedTax`，同一期间多标签取最新申报）+ D2（流量类字段第四季 = 全年 − 前三季）+ D3（submissions 已有、facts 3 天内仍无该期 → 解析该申报的 XBRL 实例）+ D4（毛利 = 营收 − 营业成本，标 `gross_margin_derived`）+ D5（净利润兜底标签 `NetIncomeLossAvailableToCommonStockholdersBasic`、`ProfitLoss`，标 `ni_tag_fallback`）；每项可单独开关 |
| FR-M2-03 | D2 的任一季缺失 → 第四季为 `NULL`，健康码 `q4_missing` |
| FR-M2-04 | 健康码按规格第 4.6 节；`stale_fundamentals` = 最新营收期间结束日距 `as_of` 超过 180 天；`revenue_tag_gap` = 修复关闭时只存在新营收标签；`companyfacts_lag` = submissions 有新 10-Q / 10-K、facts 没有 |
| FR-M2-05 | D7：SIC 4911、4931、4991（发电、电力公用事业）标 `industry_basis_na`，正常打分 |
| FR-M2-06 | `fcf_margin_change_pp` = 本期 TTM 自由现金流率 − 一年前 TTM 自由现金流率 |
| FR-M2-06b | `op_margin_ttm` = TTM 营业利润 ÷ TTM 营收（营业利润同样适用 D2 的第四季推算）；缺标签时为 `NULL` |
| FR-M2-07 | `can_score` = 健康码只含 `ok` 类（`ok`、`gross_margin_derived`、`ni_tag_fallback`、`industry_basis_na`、`single_segment`、`segment_*`）；`can_trade` = `can_score` 且不是外国申报人 |
| FR-M2-08 | 一致预期：每日北京 10:30 前完成 59 只快照；Muse 历史一次性导入，重复导入不产生重复行（按 `as_of, ticker, source` 唯一） |
| FR-M2-09 | F2：N 日变化 = 当日值 ÷（恰好 N 个自然日前或更早的最近一个快照值）− 1；该快照距目标日超过 3 天视为缺失；首个快照之前的窗口标"不足 N 天"；广度 = (上修 − 下修) ÷ 覆盖家数；分歧度 = (最高 − 最低) ÷ 均值 |
| FR-M2-10 | F1：从 XBRL 实例取 `StatementBusinessSegmentsAxis` 上的分部收入和分部利润；分部收入之和加抵销项与合并营收相差 ≤ 1%，否则健康码 `segment_sum_mismatch`；单一分部标 `single_segment` |
| FR-M2-11 | 重分部：分部名称或数量变化、且新旧口径同期收入差 > 1% → 新的 `recast_group`，健康码 `segment_recast`；同比只在同一 `recast_group` 内计算 |
| FR-M2-12 | 分部映射：每个新出现的 `segment_raw` 触发一次 `segment_mapping_draft`（`glm-5.3`），输出图谱节点 id 和理由，状态"待审核"；未确认的映射 `segment_std = NULL`，健康码 `segment_unmapped` |
| FR-M2-13 | F3 档案每日生成；"基本面变化记录"在三种情况下各写一条：新财报生效、`eps_cy` 较上次记录变化超过 3%、8-K 指引类条目（Item 2.02 / 7.01 中含 guidance 关键词，由 M1 的抽取字段提供） |
| FR-M2-14 | 所有任务写 `job_runs` |

## 6. 异常与降级

| 情况 | 行为 |
|---|---|
| companyfacts 不可用 | 沿用已有 `fin_state`；新申报标 `companyfacts_lag`，按 D3 解析实例 |
| XBRL 实例解析失败 | 该期分部为空，健康码 `segment_missing`；财报字段若依赖它则同 `companyfacts_lag` |
| yfinance 失效 | `source_health` 显示；F2 当日不更新，窗口状态写明；估值按规格退回 TTM 口径（M5） |
| 外国申报人 | 只有年度数据时字段按年度口径，置信度标低；`can_trade = false` |

## 7. Harness 与自测

| 测试名 | 标记 | 断言 | 夹具 |
|---|---|---|---|
| `test_revenue_tag_gap` | blocking | I10 | `health/lite_tag.json`（开发构造，登记冻结） |
| `test_q4_derived_from_annual` | blocking | I11；`requirements/m2_fundamentals.json` 的 `q4_derivation` | 需求方标准答案 |
| `test_companyfacts_lag` | blocking | I12 | `health/be_lag.json` |
| `test_stale_fundamentals_code` | blocking | 181 天 → `stale_fundamentals`；180 天 → 不标 | 合成 |
| `test_gross_margin_derived` | blocking | D4 推算与标注 | 合成 |
| `test_ni_tag_fallback` | blocking | D5 兜底与标注 | 合成 |
| `test_industry_basis_na` | blocking | SIC 4911 标注且 `can_score = true` | 合成 |
| `test_fin_state_pit` | blocking | `state_asof` 不返回 `filed > as_of` 的行 | 合成 |
| `test_legacy_matches_muse_state` | replay | 30 只 × 3 个日期（2026-01-12、2026-05-01、2026-10-07），`legacy` 输出与 Muse 冻结输出逐字段一致（容差 1e-9） | 冻结输入（开发用 Muse 代码生成，写 CHANGELOG） |
| `test_extractor_fixed_toggles` | blocking | D1–D5 每个开关单独打开时只影响对应字段 | 合成 |
| `test_segment_extraction` | blocking | I33；`requirements/m2_fundamentals.json` 的 `segment_sum_tolerance` | 需求方标准答案 + XBRL 片段 |
| `test_segment_recast` | blocking | 重分部不跨口径算同比 | 合成 |
| `test_segment_mapping_pending` | blocking | 未审核映射 → `segment_std` 为空且标 `segment_unmapped` | 录音 |
| `test_consensus_derived_pit` | blocking | I34；`requirements/m2_fundamentals.json` 的 `consensus_derived` | 需求方标准答案 |
| `test_consensus_import_idempotent` | blocking | 导入两次行数不变 | 合成 |
| `test_health_contract` | blocking | 健康 JSON 字段齐全；`can_score = false` 时 `reason` 非空 | 合成 |
| `test_fundamentals_live_smoke` | live | 59 只都有 `health` 行；LITE、BE、COHR 在 `fixed` 下不是 `stale_fundamentals` | 真实 |

**中期检查点**：交 LITE、BE、AMD、CEG、ASML 五只在 `legacy` 和 `fixed` 下的 `fin_state` 最新一行，以及 AMD、WDC 的分部表样例。

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应需求 | 阻塞 |
|---|---|---|---|---|
| AC-M2-01 | 第 7 节 blocking 测试全绿；`test_legacy_matches_muse_state` 全绿 | H | FR-M2-01–14 | 是 |
| AC-M2-02 | 修复差异报告：59 只在 `legacy` 和 `fixed` 下的字段差异和健康码差异；LITE、BE、COHR 在 `fixed` 下可打分 | E | "数据缺口不能静默" | 是 |
| AC-M2-03 | 健康页 59 行全部有健康码；`can_score = false` 的都有原因；不存在"可交易但财报字段为空"的行 | E | D6 | 是 |
| AC-M2-04 | 54 只可交易标的里，≥ 90% 有分部数据或标为 `single_segment`；有分部的分部收入之和与合并营收相差 ≤ 1% | E | 主营业务盈利 | 是 |
| AC-M2-05 | 需求方抽 5 只（含 AMD、WDC），分部收入、分部利润与 10-Q 原文一致 | E | 主营业务盈利 | 是 |
| AC-M2-06 | 一致预期连续 5 个交易日覆盖 59 只；Muse 历史已导入；F2 的窗口状态正确 | E | 分析师一致预期 | 是 |
| AC-M2-07 | 59 份 F3 档案生成，三个区块都有数据或写明缺失原因 | E | 基本面档案 | 是 |
| AC-M2-08 | 分部映射草稿已生成并进入审核队列，用户可以按板块批量确认 | D | Q7 | 否 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M2-1 | 日常纸面运行用哪套提取器？ | `fixed`。`legacy` 只用于 v18 复现 |
| Q-M2-2 | 一致预期快照缺历史，要不要从别的源回补？ | 不回补，不外推 |
| Q-M2-3 | 分部利润口径不统一（营业利润、调整后利润）怎么办？ | 按公司披露的分部利润口径存，`profit_basis` 写明；不做口径转换 |
