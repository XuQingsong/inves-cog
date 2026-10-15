# M2 财报与基本面档案

| 项 | 内容 |
|---|---|
| 文档版本 | v9（合理性门禁先与申报原件核对：一致则 `extreme_value_verified`、不阻止打分） |
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
- 两套提取器：`legacy`（与 Muse 一致，用于 v18 复现）和 `fixed`（打开 D1–D5 和 D8）；
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
| Muse 历史数据 | 由开发向 Muse 方申请导出文件（README §8 R7）：`estimates_trend`、`estimates_revisions`、`price_targets`、`earnings_history`；`legacy` 对照用的原始 companyfacts 和 Muse 输出（Q-M2-7） |
| 一致预期每日数据 | yfinance（非官方接口） |
| 图谱节点 | M6 的 `graph.entities`；M6 完成前映射表可以先起草，状态为"待审核" |
| 行业代码 | submissions 的 SIC |

## 4. 输出

**`fundamentals.fin_state`**（每次新申报一行，按 `filed` 生效）：

`ticker, extractor(legacy/fixed), accession, form, filed, period_end, fiscal_period` + 规格第 9.2 节全部财报字段（`rev_ttm`、`ni_ttm`、`rev_growth`、`rev_q_yoy`、`rev_accel_pp`、`eps_ttm`、`eps_growth`、`gross_margin`、`gross_margin_change_pp`、`fcf_ttm`、`fcf_margin`、`fcf_conversion`、`roe`、`cash`、`debt`、`net_debt`、`net_debt_fcf`、`current_ratio`、`shares`（流通股本，Muse `pit_shares` 口径，规格 v1.4））+ `fcf_margin_change_pp`（F-02 用）+ `op_margin_ttm`（TTM `OperatingIncomeLoss` ÷ TTM 营收，M8 隐含幅度用）+ `health_codes text[]` + `field_sources jsonb`（每个字段来自哪个标签、是否推算）。

**接口** `state_asof(ticker, as_of_date, extractor) -> FinState | None`：返回 `filed ≤ as_of_date` 的最新一行；没有则 `None`。这是 M3、M5 读取财报的唯一入口。

**`fundamentals.segments`**：`ticker, accession, filed, period_end, period_len(Q/FY), segment_raw, segment_std(图谱节点 id，可空), revenue, segment_profit, profit_basis, margin_pct, yoy_pct, share_pct, recast_group, health_code`

**`fundamentals.segment_mapping`**：`ticker, segment_raw, graph_node_ids, drafted_by(glm-5.3), draft_reason, status(待审核/已确认/驳回), reviewed_at`

**`fundamentals.consensus_snapshot`**：`as_of, ticker, eps_cq, eps_nq, eps_cy, eps_ny, rev_cy, rev_ny, up_7d, down_7d, up_30d, down_30d, coverage, eps_high_cy, eps_low_cy, pt_mean, pt_median, source(yfinance/muse_import)`；v2 追加 `captured_at`（UTC，Muse 导入行未知时为 `NULL`）、`fy_cy`、`fy_ny`（目标财年的年末日期）、`raw jsonb`（原始响应，包括供应商给的 7 / 30 / 60 / 90 天回望值；F2 **不得使用**这些回望值）

**`fundamentals.consensus_derived`**：`as_of, ticker, chg_7d_pct / chg_30d_pct / chg_90d_pct（EPS 当年、次年，营收当年）, breadth_7d, breadth_30d, dispersion, surprise_last4, window_status jsonb`

**`fundamentals.profile`**（F3，每日每只一份 JSON）：主营业务、季度财报趋势、一致预期、基本面变化记录。

**`fundamentals.health`**（数据健康页 JSON 的来源）：`ticker, latest_period_end, latest_filed, latest_8k_202, health_codes, can_score(bool), can_trade(bool), reason`

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M2-01 | `legacy` 提取器：在本项目内重写，逻辑与 Muse `screen_asof_2026_01_01.py:pit_fundamentals`、`paper_trade_2026.py:compute_books` 的取数部分一致（参照源码，不导入、不拷贝）；同一输入下与 Muse 冻结输出逐字段一致 |
| FR-M2-02 | `fixed` 提取器 = `legacy` + D9（营收 / EPS 标签缺口，Q-M2-23）+ D8（现金缺失时 `net_debt`、`net_debt_fcf` 为空，规格 4.5 v1.4）+ D1（营收标签清单加入 `RevenueFromContractWithCustomerIncludingAssessedTax`，同一期间多标签取最新申报）+ D2（流量类字段第四季 = 全年 − 前三季）+ D3（submissions 已有、facts 3 天内仍无该期 → 解析该申报的 XBRL 实例）+ D4（毛利 = 营收 − 营业成本，标 `gross_margin_derived`）+ D5（净利润兜底标签 `NetIncomeLossAvailableToCommonStockholdersBasic`、`ProfitLoss`，标 `ni_tag_fallback`）；每项可单独开关 |
| FR-M2-03 | D2 的任一季缺失 → 第四季为 `NULL`，健康码 `q4_missing` |
| FR-M2-04 | 健康码按规格第 4.6 节；`stale_fundamentals` = 最新营收期间结束日距 `as_of` 超过 180 天；`revenue_tag_gap` = 修复关闭时只存在新营收标签；`companyfacts_lag` = submissions 有新 10-Q / 10-K、facts 没有 |
| FR-M2-05 | D7：SIC 4911、4931、4991（发电、电力公用事业）标 `industry_basis_na`，正常打分 |
| FR-M2-06 | `fcf_margin_change_pp` = 本期 TTM 自由现金流率 − 一年前 TTM 自由现金流率 |
| FR-M2-06b | `op_margin_ttm` = TTM 营业利润 ÷ TTM 营收（营业利润同样适用 D2 的第四季推算）；缺标签时为 `NULL` |
| FR-M2-07 | `can_score` = 健康码里没有"阻止打分"类的码（v2 矩阵见 Q-M2-10）；`can_trade` = `can_score` 且不是外国申报人 |
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
| `test_q4_derived_from_annual` | blocking | I11；`golden/m2_fundamentals.json` 的 `q4_derivation` | 需求方标准答案 |
| `test_companyfacts_lag` | blocking | I12 | `health/be_lag.json` |
| `test_stale_fundamentals_code` | blocking | 181 天 → `stale_fundamentals`；180 天 → 不标 | 合成 |
| `test_gross_margin_derived` | blocking | D4 推算与标注 | 合成 |
| `test_ni_tag_fallback` | blocking | D5 兜底与标注 | 合成 |
| `test_industry_basis_na` | blocking | SIC 4911 标注且 `can_score = true` | 合成 |
| `test_fin_state_pit` | blocking | `state_asof` 不返回 `filed > as_of` 的行 | 合成 |
| `test_legacy_matches_muse_state` | replay | 30 只 × 3 个日期（2026-01-12、2026-05-01、2026-10-07），`legacy` 输出与 Muse 冻结输出逐字段一致（相对容差 1e-9；比较 Muse `pit_fundamentals` 返回的全部字段，不含本项目新增字段） | 冻结输入：由开发向 Muse 方申请原始 companyfacts 和 Muse 输出（Q-M2-7），登记 MANIFEST 和 CHANGELOG |
| `test_extractor_fixed_toggles` | blocking | D1–D5 每个开关单独打开时只影响对应字段 | 合成 |
| `test_segment_extraction` | blocking | I33；`golden/m2_fundamentals.json` 的 `segment_sum_tolerance` | 需求方标准答案 + XBRL 片段 |
| `test_segment_recast` | blocking | 重分部不跨口径算同比 | 合成 |
| `test_segment_mapping_pending` | blocking | 未审核映射 → `segment_std` 为空且标 `segment_unmapped` | 录音 |
| `test_consensus_derived_pit` | blocking | I34；`golden/m2_fundamentals.json` 的 `consensus_derived` | 需求方标准答案 |
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
| AC-M2-06 | Muse 历史已导入（行数、哈希与导出 manifest 一致，重复导入不增行）；F2 在导入的历史上窗口状态正确（需求方抽 5 只、3 个日期复算）；采集失败时健康页如实显示失败原因，不写假快照 | E | 分析师一致预期 | 是 |
| AC-M2-06b | 本项目自己的**每一次**真实采集都覆盖 59 只，至少 2 次（v5 拆出：部署机 IP 被 Yahoo 封禁，见 Q-M2-20）。**期限**：M5 提交验收之前 | E | 分析师一致预期 | 否 |
| AC-M2-07 | 59 份 F3 档案生成，三个区块都有数据或写明缺失原因 | E | 基本面档案 | 是 |
| AC-M2-08 | 分部映射草稿已生成并进入审核队列，用户可以按板块批量确认 | D | Q7 | 否 |
| AC-M2-09 | 外国申报人：TSM、NOK 的年报缺口已补齐（Q-M2-28）；ASML、TSM、NOK、ARM 最近 4 个季度的 6-K 业绩公告核心数字已入库，需求方抽 4 只各 1 个季度与公告原文核对一致（Q-M2-29）；TSM 最近 12 个月的月度营收已入库（Q-M2-30）；SKHY 的状态如实标注（Q-M2-31）。**期限**：M5 提交验收之前 | E | 只观察标的的基本面可用于估值展示 | 否 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M2-1 | 日常纸面运行用哪套提取器？ | `fixed`。`legacy` 只用于 v18 复现 |
| Q-M2-2 | 一致预期快照缺历史，要不要从别的源回补？ | 不回补，不外推 |
| Q-M2-3 | 分部利润口径不统一（营业利润、调整后利润）怎么办？ | 按公司披露的分部利润口径存，`profit_basis` 写明；不做口径转换 |
| Q-M2-4（K01） | Muse 缺现金按 0 算 `net_debt`；`shares` 不是稀释股本 | **`legacy` 照原样复现**，包括缺现金按 0 算，否则无法复现 v18。这是"缺数据就是 NULL"规则唯一的例外，只限 `legacy`，`field_sources` 标 `cash_missing_as_zero`。**`fixed` 新增 D8**：现金缺失时 `net_debt`、`net_debt_fcf` 为 `NULL`，`field_sources` 标 `cash_missing`。D8 和 D1–D5 一样可以单独开关，并写进修复差异报告。债务标签全部缺失时，两套都不产生 `debt` 和 `net_debt`（Muse 本来就是这样）。`shares` 两套都按 Muse `pit_shares` 口径，规格 9.2 的"稀释股本"是笔误，已改为"流通股本"（v1.4）；`field_sources` 记录实际用的是即时股本还是稀释加权股本 |
| Q-M2-5（K02） | 期间长度、同日多标签平手、D4 优先级、Q4 的 EPS、D3 的"三天" | **期间**：单季 = 80–100 天（含两端，与 Muse 相同）；全年 = 350–380 天，且 `fp=FY` 或来自 10-K；累计 6 个月 = 170–200 天，累计 9 个月 = 260–290 天。累计期和全年的起点必须与该财年起点相差不超过 7 天。**D2 的推算范围（v2 明确）**：流量类字段（营收、营业成本、毛利、营业利润、净利润、经营现金流、资本开支）缺单季数时，用累计数相减推出：Q2 = 6 个月 − Q1，Q3 = 9 个月 − 6 个月，Q4 = 全年 − 9 个月（没有 9 个月数时用全年 − Q1 − Q2 − Q3）。`field_sources` 标 `ytd_derived` 或 `q4_derived`。原因：现金流量表在 10-Q 里只报累计数，只补第四季会让 TTM 现金流仍然算错。任一所需期间缺失，该季为 `NULL`，标 `q4_missing`。**EPS** 只推第四季：Q4 = 全年稀释 EPS − 前三季之和，标 `eps_q4_derived`（近似值，不阻止打分）；加权股本不推算。**同一期间多个标签**：`fixed` 下申报日较新的优先；申报日相同时按标签顺序：营收 `ExcludingAssessedTax` > `IncludingAssessedTax` > `Revenues` > `SalesRevenueNet`；营业成本 `CostOfRevenue` > `CostOfGoodsAndServicesSold`。`legacy` 保持 Muse 原行为（先遇到的留下）。**D4** 只在该期间没有 `GrossProfit` 时触发。**D3**：申报日 + 3 个自然日那天（含）起，如果 companyfacts 里还没有任何 `accn` 等于该申报号的 fact，就解析该申报的实例。解析出的数值从申报日起生效（与 M-02 一致），`field_sources` 标 `instance_parsed` |
| Q-M2-6（K03） | 开关会连带影响派生字段 | 采用 B 方案：每个开关只影响它的直接字段，以及由这些字段派生出的字段。开发在 `config/params/p-2026.10/m2.yaml` 里写出影响矩阵（开关 → 直接字段 → 派生字段），需求方在 PR 里审核。`test_extractor_fixed_toggles` 断言矩阵**以外**的字段不变。多个开关同时打开时，按 D3 → D1 → D2 → D4 → D5 → D8 的顺序应用 |
| Q-M2-7（K04） | `legacy` 对照的冻结输出怎么来？ | 采用 B 方案。开发**向 Muse 方申请**两份文件：（1）Muse v18 用过的原始 companyfacts（`pit_cache/{ticker}_facts.json`），30 只以 Muse 方给的清单为准，附 SHA-256；（2）Muse 方在自己的环境里，用 `aacea04` 的 `pit_fundamentals`，对这 30 只、3 个日期跑出的输出 JSON，附生成命令和版本。开发**不运行、不导入** Muse 代码。两份文件以 `.json.gz` 形式放进 `tests/fixtures/phase1/m2/muse/`，登记 MANIFEST 和 CHANGELOG；压缩后合计超过 50 MB 时先停下，写进 `questions.md`。需求方验收时会在自己的隔离环境里，用 Muse 源码对同一份输入抽查输出。文件到之前，这个 replay 测试留在 pending，原因写"等待 R7（Muse 导出）"，**不得用本项目自己的输出反推期望值** |
| Q-M2-8（K05） | 历史导入格式、`as_of` 的定义、来源冲突、跨财年 | 复述单第 7 节的 CSV.gz + manifest 格式批准。如果 Muse 方给的是 pg_dump，只允许离线解析其中的 COPY 数据块，不得还原成数据库。**`as_of` 统一为北京日期**：本项目的每日快照在北京 10:30 前采集，`as_of` = 当天北京日期；Muse 的 `snapshot_date` 本来就是北京日期，原样使用。两个来源同一天都有时，F2 用 `yfinance`。来源本身没有的字段（营收共识、`coverage`、EPS 高低值等）为 `NULL`，`window_status` 写"来源无此字段"。`fy_cy` 和 `fy_ny` 按 `fin_state` 最近一份 10-K 的期末日推算：`fy_cy` = 之后第一个财年末。窗口只比较同一个目标财年；跨财年的为 `NULL`，标"财年切换" |
| Q-M2-9（K06） | 每次申报一行，还是按 Muse 的 RELEVANT_TAGS 生效日？同日多份申报、修订稿？ | **`fixed`**：每个有效申报日一行，有效申报为 10-Q、10-K、20-F、40-F、6-K 及其 `/A`。同一天有多份申报时合成一行（截止到当天全部申报），`accession` 取当天最晚接收的那份。从 2015-01-01 起建。**`legacy`**：生效日完全按 Muse 规则（初始状态 2025-12-31，之后只取 RELEVANT_TAGS 的 2026 年申报日），只需要覆盖 v18 区间和 3 个对照日期，可以按需计算。D3 解析的旧实例从该申报的申报日起可见。M1 的原始申报记录用 `ingest.sec_filings`（M1 v2 第 4 节） |
| Q-M2-10（K07） | 健康码的严重级别；"可交易但财报字段为空"指哪些字段？ | **阻止打分**（`can_score = false`）：`no_bar`、`stale_fundamentals`、`revenue_tag_gap`、`q4_missing`、`companyfacts_lag`（D3 也失败时）、`core_field_missing`（v2 新增）。**不阻止打分**（页面标注）：`ok`、`gross_margin_derived`、`ni_tag_fallback`、`industry_basis_na`、`single_segment`、`segment_missing`、`segment_sum_mismatch`、`segment_recast`、`segment_unmapped`、`annual_basis`（v2 新增）、`earnings_event_missing`。分部类码不影响打分，因为分部数据不是规则 A 的输入。**核心字段** = `rev_ttm`、`eps_ttm`、`shares`，任一为 `NULL` 即 `core_field_missing`。其他字段为空是允许的（例如 EPS ≤ 0 时 `eps_growth` 为空，FCF ≤ 0 时 `net_debt_fcf` 为空，银行没有毛利），但必须在 `field_sources` 里写原因。AC-M2-03 的"财报字段为空"就是指这三个核心字段 |
| Q-M2-11（K08） | 分部 axis、利润标签、抵销项、单一分部、重分部条件 | 主 axis = `us-gaap:StatementBusinessSegmentsAxis`，只取只带这一个维度的 context。抵销项取 `ConsolidationItemsAxis` 上的 `IntersegmentEliminationMember`、`CorporateNonSegmentMember` 等成员，单独存一行，参与合计核对。`ProductOrServiceAxis` 单独存（`axis = product`），**不参与**分部合计。分部收入标签顺序与 Q-M2-5 的营收顺序相同。分部利润优先 `OperatingIncomeLoss`；没有时，用公司在分部附注里披露的利润元素，`profit_basis` 写元素的 QName。**单一分部**需要证据：分部 axis 上没有成员，并且 `NumberOfReportableSegments` 或 `NumberOfOperatingSegments` 等于 1；否则标 `segment_missing`。**重分部**：新申报里带有以前期间的比较数时，如果同一期间的分部名称集合与已存的不同，或者同名分部的收入相差超过 1%，就建新的 `recast_group`；没有比较数、但名称集合变了，也建新组。同比只在同一组内计算，跨组为 `NULL`。合并营收 ≤ 0 时不做合计核对，在健康备注里写明 |
| Q-M2-12（K09） | `coverage`、修订期、分歧度、`surprise_last4`、3% 触发的基数 | `coverage` = 当年（`0y`）EPS 的分析师人数。广度用当年的上修、下修家数：(上修 − 下修) ÷ `coverage`，`coverage` 为 0 或空时为 `NULL`。分歧度 = (`eps_high_cy` − `eps_low_cy`) ÷ \|`eps_cy`\|，\|`eps_cy`\| < 0.01 时为 `NULL`。N 日变化的基数 ≤ 0 时为 `NULL`，状态写"基数 ≤ 0"。`surprise_last4` 存为列表（jsonb，最新在前，最多 4 项，每项含 `quarter_date, eps_actual, eps_est, surprise_pct`），不足 4 项照存，不求平均。可见时点：Muse 导入的行用 `first_seen`，本项目自己采集的用 `captured_at`。单位：变化率、超预期幅度存百分数（2.5 表示 2.5%）；广度、分歧度存比值。F3 的"共识变化超过 3%"：与上一次记录时的 `eps_cy` 比较，严格大于 3%，且是同一目标财年；基数 ≤ 0 时只在正负号变化时记录；财年切换时记一条"财年切换"并重置基数 |
| Q-M2-13（K10） | 外国申报人的年度口径、IFRS 标签、历史起点、新增字段 | 外国申报人在 `fixed` 下按年度口径：`rev_ttm` = 最近一个财年，`rev_growth` = 财年同比，`eps_ttm` = 财年 EPS；只有季度才有意义的字段（`rev_q_yoy`、`rev_accel_pp`）为 `NULL`；健康码 `annual_basis`。`fixed` 支持的 IFRS 标签：`ifrs-full:Revenue`；净利润 `ProfitLossAttributableToOwnersOfParent` > `ProfitLoss`；`GrossProfit`；`CashFlowsFromUsedInOperatingActivities`；`PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities`；`DilutedEarningsLossPerShare`；`EquityAttributableToOwnersOfParent`；`CashAndCashEquivalents`。`legacy` 保持 Muse 原行为。`fin_state` 从 2015-01-01 起建。新增字段 `op_margin_ttm`、`fcf_margin_change_pp` 两套提取器都要算，不参与 Muse 对照，各有单独的测试用例 |
| Q-M2-14（K11） | 读图谱的权限；共享的运行表、LLM 客户端、SEC 客户端由谁建？审核队列的合同？ | 见 M1 v2 的 Q-M1-14 和 Q-M1-15：`role_ingest` 可以只读 `graph`；`job_runs` / `source_health` 的建表、`inves_cog/llm/client.py`、`inves_cog/ingest/sec_client.py` 都由 M1 建，本模块只按接口使用。T01 还没合并时，本模块用实现同一接口的测试替身开发，**不得**自建同名表或第二个客户端。审核：本模块提供 `list_pending_mappings(sector)` 和 `confirm_mappings(ids, reviewer, decision)` 两个函数，以及对应的 JSON；板块取自 `config/universe.yaml`。页面和批量确认按钮在 M10 |
| Q-M2-15（K12） | XBRL 解析库、taxonomy 离线包、检查点合同 | 批准 **Arelle**（`arelle-release`），版本锁进 `uv.lock`。测试用手写的小实例和本地桩 schema，**不下载** taxonomy；生产环境允许 Arelle 从 SEC / FASB 下载 taxonomy，存进本地缓存目录。中期检查点按复述单第 5 节的合同，夹具数据和真实数据要分别标明 |
| Q-M2-16（K13） | M0 干净环境断言写死迁移只有一个 | 已由 M1 的 PR 修正（M1 Q-M1-17）。M2 在 M1 合并后基于 main 重跑 CI |
| Q-M2-17（K14） | 非美元财报怎么换成美元？ | **用户答复**：用 FRED，缺汇率时**不得写 `NULL` 了事**，必须查清是哪一项、为什么缺。**合同**：（1）序列：EUR = `DEXUSEU`（每欧元多少美元），TWD = `DEXTAUS`、KRW = `DEXKOUS`（每美元多少本币），统一换成"每单位本币多少美元"再相乘。（2）可见性：只用 `realtime_start ≤ as_of` 的观测，按 FRED / ALFRED 的版本取，不用当前修订值改写历史；期间里有已存在但当时还没发布的观测（H.10 每周发布一次），整笔换算暂停。（3）流量（营收、利润、现金流）和 EPS：用该期间内有报价日的日均汇率；TTM 由换算后的单季相加。（4）余额（现金、债务、权益）：用期末汇率，取期末日当天或之前**最近一个有效报价，最多往前 7 个自然日**（需求方定），实际用的报价日要记录下来。（5）股数不换算；同币种的比率用原币计算。（6）缺口：抛出 `FXGap`，写明币种、序列、目标字段、期间、版本日和原因；该字段**不写入**换算值，原币原始值和证据保留；缺口清单写进健康 JSON，原因要能区分"未配置 key""尚未发布""区间内无报价""报价无效""不支持的币种"。（7）其他财报字段中文档明确允许的 `NULL` 不受本条影响 |
| Q-M2-18（K15） | 分部收入 context 除主 axis 外还带 `srt:ConsolidationItemsAxis` | **用户答复**：只允许 `srt:ConsolidationItemsAxis = us-gaap:OperatingSegmentsMember` 这一种附加维度，其他混合维度仍然拒绝 |
| Q-M2-19（K16） | 利润专用的抵销行、同轴汇总成员、GEV 的辅助成员 | **用户答复**：按申报原件判定。（1）原件里只有利润、没有营收元素的行（例如 NVDA 的 `CorporateNonSegmentMember`）不参与营收加总；该行保留，营收为 `NULL` 并写明原因，不填 0。（2）同一 axis 上的汇总成员（例如 UNH 的 TotalOptum、CAT 的 `ReportableSegmentAggregationBeforeOtherOperatingSegmentMember`）按同一申报的 calculation / definition 关系和分部表识别为汇总项或抵销项，按原件的权重计算；**不得**按名称猜测，也不得试组合凑 1%。（3）GEV 的 `srt:ConsolidationItemsAxis = gev:OperatingSegmentsExcludingIntersegmentEliminationMember` 单独放行，限定 ticker、namespace 和成员三者都匹配；带 `SubsegmentsAxis` 的三维 context 仍然拒绝。原件审计：`handoff/M2/k16-original-audit.json.gz` |
| Q-M2-20 | Yahoo 返回 crumb 403、quoteSummary 429 | **需求方诊断（2026-10-15）**：部署机出口 IP 为腾讯云首尔（AS132203），对 Yahoo 的第一个请求就返回 429，包括通常不限流的 chart 接口。这是 IP 被封，不是频率问题，重试无效。M2 的代码不存在问题，所以把真实采集拆成非阻塞的 AC-M2-06b，期限为 M5 提交验收之前（M5 估值依赖一致预期）。解决途径由用户选择：（A）只给 Yahoo 请求配一个 Yahoo 不封的出口代理，代码只加 `YFINANCE_PROXY` 配置；（B）改用 Alpha Vantage 的 `EARNINGS_ESTIMATES` 接口（已有 key，需先实测字段和额度；每天 59 次调用会超出免费额度）。选定之前不换源，不伪造快照 |
| Q-M2-21 | COST、LRCX 在旧版能打分，修复版反而不能（`q4_missing`） | **需求方核实（2026-10-15）**：`repair_flow` 会遍历 2009 年以来的每个财年、每个流量字段（包括营业成本这类辅助字段），只要任何一处推不出第四季，就给整只标 `q4_missing`。**规则**：`q4_missing` 只看**当前状态实际用到的季度**（最近 8 个季度），而且只看**打分用到的字段**：营收、净利润、经营现金流、资本开支、稀释 EPS，以及毛利（D4 推算时才看营业成本）。其他字段或更早的季度推不出时，只在 `field_sources` 里记录，不加健康码、不阻止打分 |
| Q-M2-22 | 单季长度 80–100 天太窄 | COST 的第四财季是 16 周（约 112 天）。`fixed` 下单季长度放宽为 **80–120 天**；`legacy` 保持 80–100 天，与 Muse 一致 |
| Q-M2-23 | JPM、V、XOM 两套提取器都取不到核心字段 | 新增 **D9**（只在 `fixed`，可单独开关，写进差异报告）。已知原因：JPM 的 `Revenues` 停在 2014 年，银行用的是 `RevenuesNetOfInterestExpense`，把它加进营收标签清单（排在现有标签之后）；V 的 EPS 只按股票类别披露（`StatementClassOfStockAxis`），取主要交易类别（V = A 类）的 EPS，类别在 `config/params/p-2026.10/m2.yaml` 里按 ticker 配置。XOM 的营收序列为什么不完整，请开发查申报原件，确定具体规则后同样放进 D9；规则写进 `m2.yaml`，在差异报告里说明，需求方验收时审核（按任务书 §4.6 属于"不停"，不必等答复） |
| Q-M2-24 | 59 只里 49 只 `earnings_event_missing` | M2 分支跑这一轮时，大概率没有连上 M1 的 `ingest.earnings_events`。两边合并后重跑健康页；如果仍然大量缺失，逐只列出原因 |
| Q-M2-25 | Yahoo 怎么采？（更正 Q-M2-20） | **需求方复测（2026-10-15 00:48 北京时间，距开发最后一次请求已 4 小时以上）**：`query1/query2.finance.yahoo.com` 的所有数据接口（chart、search、quoteSummary、getcrumb）第一个请求就返回 429；但网页 `finance.yahoo.com/quote/{T}/analysis/` 返回 200，页面里含 Earnings Estimate、Revenue Estimate、EPS Trend、EPS Revisions、分析师人数，还嵌着 `earningsTrend` 原始 JSON。开发之前每次诊断只发 5 个请求，每轮 59 只，可以基本排除"请求太频繁"；更像是 Yahoo 对这台云服务器 IP 的数据接口做了限制。**规则**：数据接口返回 429 时，改从同一个 Yahoo 分析页取同一套字段（优先解析嵌入的 JSON），两个页面之间间隔至少 5 秒，每天 59 次；`source` 记 `yahoo_page`，F2 把它和 `yfinance` 视为同一个来源。不用代理，不换供应商。AC-M2-06b 仍按原条款判定 |
| Q-M2-26 | V 在 `fixed` 下的 `shares` 只有 A 类股（4.69 亿股），按全部类别折算后约 19 亿股，导致市值、市销率、自由现金流收益率被低估约 4 倍（需求方 2026-10-15 发现；Muse 原来也是这样，属需求缺口） | 纳入 D9：`m2.yaml` 里登记多类别股发行人（先登记 V），`fixed` 下它们的 `shares` 改用最近一个季度的 `WeightedAverageNumberOfDilutedSharesOutstanding`（按全部类别折算的稀释股本），`field_sources` 标 `multi_class_diluted`。`legacy` 不变 |
| Q-M2-27 | 怎样防止明显错误的数值进入打分？（LITE 的 TTM 净利润 −69.4 亿美元，而营收只有 30 亿美元） | 新增健康码 **`implausible_value`**（只在 `fixed` 下检查，属于"阻止打分"类）：（1）\|`ni_ttm` ÷ `rev_ttm`\| > 1；（2）`eps_ttm × shares` 与 `ni_ttm` 之比不在 0.5–2 之间（\|`ni_ttm`\| < 1,000 万美元时不检查）；（3）任一 TTM 金额由某一季度的推算值（`q4_derived` / `ytd_derived`）主导，而该推算值的符号与另外三季都相反、且绝对值超过另外三季绝对值之和。命中时 `reason` 写明是哪条规则、涉及哪些季度。`legacy` 不检查（与 Muse 一致） |
| Q-M2-28 | TSM 的最新年报期末停在 2024-12-31，NOK 停在 2017-12-31（需求方 2026-10-15 发现） | 两者都应当有更新的 20-F。请查明原因（例如 IFRS 标签、`ifrs-full` 与 `us-gaap` 混用、20-F 实例没取到），修复后 `fixed` 下按年度口径给出最近一个财年 |
| Q-M2-29 | 外国申报人不交 10-Q，季度业绩通过 6-K 报备，SEC 结构化数据里没有 | 新增"6-K 业绩公告"取数，只在 `fixed` 下使用：（1）从 M1 的 `ingest.sec_filings` 里找出 ASML、TSM、NOK、ARM（以及以后的 SKHY）的季度业绩 6-K，通常是附件 99.1 的新闻稿；（2）从公告的财务报表里取季度核心数字：营收、毛利、营业利润、归母净利润、稀释 EPS（写明是每股还是每 ADS，以及换算比例）、币种；（3）按发行人写固定的表格解析规则，不调用 LLM，解析不出来的标 `interim_unparsed` 并写明原因；（4）存入新表 `fundamentals.interim_results`（`ticker, accession, filed, period_end, currency, revenue, gross_profit, operating_income, net_income, eps_diluted, eps_basis, source_exhibit, parse_status`）；（5）`fixed` 下外国申报人的营收、净利润、EPS 改为用"最近一份年报 + 之后的季度公告"拼出 TTM；货币按 Q-M2-17 换算；健康码 `interim_unaudited`（不阻止打分）。这些公司仍然不可交易（I13 不变） |
| Q-M2-30 | TSM 每月公布营收 | TSM 的月度营收 6-K 单独存入 `fundamentals.monthly_revenue`（`ticker, month, revenue, currency, filed, accession`），只用于档案展示和 M8 归因引用，不参与 TTM |
| Q-M2-31 | SKHY 在 SEC 没有财务数据 | 上市时间短，还没有年报或季度公告。有 6-K 业绩公告时，按 Q-M2-29 处理；没有时健康码 `no_financial_filings_yet`，`reason` 写明已检查的申报类型和日期。不另找数据源 |
| Q-M2-32 | Q-M2-27 的门禁把真实发生的巨额损失也拦住了（LITE 2026 财年 GAAP 净亏损 69.35 亿美元，来自 77.57 亿美元的可转债清偿损失；SKHY 2026 Q2 归母净利润高于营收，来自 63.3 万亿韩元的投资收益），与 AC-M2-02"LITE 可打分"矛盾 | **需求方更正（2026-10-15）**：门禁本意是拦截提取错误，不是拦截真实数据。命中 Q-M2-27 三条规则中任一条时，先把涉及的数值与申报原件（10-K / 10-Q 实例的无维度主报表 context，或外国申报人的 6-K 附件）核对：**一致**，健康码改为 `extreme_value_verified`（不阻止打分），`reason` 写明原件位置和主要原因（例如"可转债清偿损失 77.57 亿美元，非现金"），页面同样显示；**不一致**，才标 `implausible_value`，阻止打分。`legacy` 不检查 |
