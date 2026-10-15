# M1 行情与信息采集

| 项 | 内容 |
|---|---|
| 文档版本 | v7（按时调度拆为非阻塞的 AC-M1-02b） |
| 规格章节 | 3.2、4.1、4.2、4.3、4.7、5.5（数据部分） |
| 依赖 | M0；监控实体清单来自 M6（M6 完成前用 `config/monitored_entities.yaml` 的人工初版） |
| 关闭的不变量 | I22、I28（数据部分） |
| 规模 | 中 |

## 1. 目标

把感知需要的"快信息"按时、完整、带准确时间地收进来，并且让任何一个数据源断了都能被看见。

对应需求：信息从哪来、全不全、拿到之后怎么处理；"能感知股价异常，允许有延迟，以天为单位"；源头事件"有没有被抓到、会不会被当成普通信息过滤掉"（本模块保证"抓到并留存"，不过滤）。

## 2. 范围

**做**：

| 数据 | 覆盖 | 频率 |
|---|---|---|
| 分钟线 | 59 只 + 14 只 ETF，美东 04:00–20:00 | 美东 20:20 起采集当日全天（含盘后），20:45 前完成（北京 08:45；冬令时 09:45，见 README §3.1）；美东 08:00（北京 20:00；冬令时 21:00）补当日盘前 |
| 日线 | 59 + 14；广域集合 | 每日 |
| 广域集合成员 | 市值 ≥ 20 亿美元且 20 日均成交额 ≥ 2,000 万美元的普通股 | 成员每月第一个交易日重算；成交额条件每日检查 |
| 新闻 | Alpaca News 全市场；首次上线回补 90 天 | 每日 + 盘前复核前 |
| SEC | 8-K Atom 流（全市场）；59 只的 submissions（含 8-K items、acceptanceDateTime）；59 只的 Form 4 | 每日 |
| `earnings_events` | 59 只 | 每日（由 submissions 生成） |
| App Store 榜单 | 美国免费榜、畅销榜前 100 | 每小时 |
| Google Trends | 监控实体 | 每日 |
| 官网变化 | 监控实体的官网 URL 清单 | 每日 |
| 空头、期权统计 | FINRA 空头（每月两次）、CBOE 每日期权统计 | 按发布频率 |
| 宏观 | FRED：CPI、非农、2 年期美债、VIX、WTI、广义美元（本项目内实现采集，并接入全量库） | 每日 |
| 全量库 | 以上所有信息统一入 `ingest.info_items`，带实体、信源等级、向量 | 随采集 |
| 数据源健康 | 每个数据源的状态 | 每次任务 |

**不做**：说法抽取（M8）、异常判断（M7）、任何对信息的过滤或丢弃（全量库只存不删，90 天后只是转为"摘要 + 向量"）、社交数据、财报数字（M2）。

**边界澄清**：

- 分钟线窗口从 **04:00** 开始（盘前复核需要盘前价格），到 **20:00** 结束（I22）。规格只写了结束时间，开始时间以本文为准。
- "盘后收盘价"= 美东 20:00 前最后一根有成交的分钟线收盘价；当天盘后没有成交则为 `NULL`，不得用常规收盘价代替。
- 广域集合的市值 = SEC frames 接口最近一期 `dei/EntityCommonStockSharesOutstanding` × 最近收盘价；取不到股本的股票不进集合，记入"未入选原因"统计。**v2 澄清**：只收普通股（含同一发行人的多个普通股类别）；ETF、ETN、基金、ADR / ADS、优先股、权证、单位、权利**都不进**集合（`non_common`）。ADR 排除，是因为免费数据拿不到存托比率，算不准市值。
- 全量库里"首次取得时间" `first_seen_at` 是系统第一次拿到这条信息的时间；"发布时间" `published_at` 来自信源。两者都必须存，归因的时间对齐用 `published_at`，鉴伪用两者之差。

## 3. 输入

| 输入 | 来源 |
|---|---|
| 59 只标的、14 只 ETF | `config/universe.yaml`（规格第 3.3 节） |
| 监控实体清单 | M6 的 `graph.monitored_entities`（`role_ingest` 只读，README §3.6 v1.4）；M6 完成前用 `config/monitored_entities.yaml`，由本模块按第 9 节 Q-M1-12 起草，需求方在 PR 里审核 |
| 信源等级映射 | `config/source_levels.yaml`（第 5 节 FR-M1-09） |
| 密钥 | 环境变量 |

## 4. 输出

**`ingest.bars_minute`**：`ticker, ts_utc, open, high, low, close, volume, session(pre/intraday/post), source`

**`ingest.bars_daily`**：`ticker, trade_date, open, high, low, close, volume, post_close(盘后收盘，可空), adj_factor, source`

**`ingest.wide_universe`**：`trade_date, ticker, mktcap, adv20, included(bool), exclude_reason`

**`ingest.info_items`**（全量库）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `info_id` | text | 全局唯一，格式 `{kind}:{source}:{source_native_id}` |
| `kind` | enum | `news` / `sec_8k` / `form4` / `app_rank` / `trend` / `site_change` / `macro` / `short_interest` / `options_stats` |
| `published_at` | timestamptz | 信源给出的发布时间；无则 `NULL` 并标 `published_at_missing` |
| `first_seen_at` | timestamptz | 系统首次取得 |
| `source` | text | 原始来源（媒体名、`SEC`、`AppStore`） |
| `source_root` | text | 去重转载用的来源根（例如同一篇通讯社稿件的所有转载共用一个根） |
| `source_level` | int 1–4 | 信源等级 |
| `headline`、`body`、`url` | text | `body` 90 天后可清空，保留 `summary` |
| `tickers` | text[] | 原文或接口给出的代码 |
| `entities` | text[] | 实体标注结果（图谱实体 id） |
| `embedding` | vector | 嵌入失败时 `NULL` 并标 `embedding_failed` |
| `extraction_status` | enum | `ok` / `failed` / `pending` |

**`ingest.info_items` v2 追加字段**：`summary`（正文前 500 个字符，按规则截取，不调用 LLM；正文清空前必须已经有值）、`flags text[]`（`published_at_missing`、`published_at_extracted`、`embedding_failed`、`entity_tagging_failed` 等）、`payload jsonb`（结构化来源的原始数值，例如榜单名次、趋势值、宏观观测）、`is_guidance bool`、`guidance_direction`（`up` / `down` / `maintain`，可空）、`is_rating_change bool`、`extraction_source jsonb`（每个抽取字段来自规则、接口还是 LLM）。同一 `info_id` 的上游更新稿写入 **`ingest.info_item_versions`**（`info_id, version_seen_at, headline, body, raw`，只追加）；主行保留首次的 `published_at` 和 `first_seen_at`，正文更新为最新版本。

**`ingest.sec_filings`**（v2 新增，submissions 原始记录，供 M2 使用）：`ticker, cik, accession, form, filing_date, report_date, accepted_at(UTC), items text[], primary_document, is_xbrl, is_inline_xbrl, fetched_at, raw jsonb`。覆盖 59 只、2015-01-01 起的全部申报。

**`ingest.short_interest`**（v2 新增）：`ticker, settlement_date, publish_date, short_interest, avg_daily_volume, days_to_cover, source`。

**`ingest.options_stats`**（v2 新增）：`trade_date, category(total/equity/index/etf…，按 CBOE 原分类), call_volume, put_volume, put_call_ratio, open_interest(可空), source`。只存市场级数据，单股期权数据不存在于本表。

**`ingest.macro_observations`**（v2 新增）：`series_id, observation_date, value, units, realtime_start, fetched_at`；`value` 为 FRED 的 `.` 时存 `NULL`。

**`ingest.earnings_events`**：规格第 4.2 节的字段，加 `session` 的取值 `closed`（休市日发布）。兜底行另有 `fallback bool`；只有日期、没有时段的兜底行，`session` 和 `reaction_day` 为 `NULL`。

**`ingest.form4_events`**：`ticker, filed_at, insider_name, is_officer, transaction_code, shares, price, accession`

**`ingest.app_rank_snapshots`**：`ts_utc, chart(free/grossing), rank, app_id, app_name, developer`

**`ingest.source_health`**：`source, last_success_at, last_attempt_at, status(ok/degraded/unavailable/未接通), latency_sec, items_last_run, note`

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M1-01 | 分钟线采集窗口美东 04:00–20:00；每根 bar 标 `session`；半日市的盘后从 13:00 起 |
| FR-M1-02 | 日线与 `post_close`；拆股复权因子单独存，原始价格不改写 |
| FR-M1-03 | 广域集合按第 2 节边界规则生成；每次重算保存全部候选及 `exclude_reason`（`no_shares`、`below_mktcap`、`below_adv`、`non_common`；v2 增加 `no_price`、`insufficient_history`、`no_cik`） |
| FR-M1-04 | 新闻：按 `info_id` 去重；同一稿件不同 URL 用 `source_root` 归并；保存 `published_at`、`first_seen_at`；首次上线回补 90 天 |
| FR-M1-05 | SEC：8-K Atom 全市场入全量库（`kind=sec_8k`，`source_level=1`）；59 只的 submissions 每日拉取 |
| FR-M1-06 | `earnings_events`：由 submissions 中 `form=8-K` 且 `items` 含 `2.02` 的记录生成；`session` 和 `reaction_day` 按 README §3.1 和规格第 4.2 节；`ref_close` = 反应日之前最后一个常规收盘价；`fiscal_period` 在对应 10-Q / 10-K 申报后回填；submissions 缺失时用 Alpha Vantage 财报日历补并标 `earnings_event_fallback` |
| FR-M1-07 | Form 4：解析非衍生交易表，保留交易代码（`P` 为公开市场买入）、是否高管（officer 标记）；按 `filed_at` 可见 |
| FR-M1-08 | App Store：每小时存快照；每次快照后对监控实体计算名次变化，名次跳升 > 20 写一条 `info_items`（`kind=app_rank`） |
| FR-M1-09 | 信源等级：`config/source_levels.yaml` 映射来源 → 等级。一级：SEC、公司官网和 IR、政府和央行；二级：Reuters、Bloomberg、WSJ、FT、CNBC、AP 等一线媒体；三级：卖方和专业财经媒体；四级：聚合、转载、匿名信源、无法识别的来源（默认） |
| FR-M1-10 | Google Trends：监控实体每日热度；接口失败时 `source_health.status = 未接通`，不写模拟值；热度 > 自身 90 日均值 3 倍写一条 `info_items`（`kind=trend`） |
| FR-M1-11 | 官网变化：监控 URL 每日抓取，正文哈希变化时写 `info_items`（`kind=site_change`），`body` 存差异片段 |
| FR-M1-12 | 实体标注：`deepseek-v4.1-flash` 的 `entity_tagging` 任务，输入标题和正文前 2,000 字，输出图谱实体 id 列表；规则先用代码 / 公司名词表匹配，LLM 只补充；失败重试 2 次后 `extraction_status=failed`，信息照常入库。**v6：不是每条都调用 LLM，按 FR-M1-18 分级处理** |
| FR-M1-12b | 字段抽取：`info_fields_extraction`（`deepseek-v4.1-flash`）为 8-K 和新闻补充三个字段：`is_guidance`（是否含业绩指引及方向：上调 / 下调 / 维持）、`is_rating_change`（是否为分析师评级或目标价变动）、`published_at`（信源未给出时从正文抽取，并标 `published_at_extracted`）；抽取失败时字段为 `NULL` |
| FR-M1-13 | 嵌入：DashScope 嵌入；失败时 `embedding=NULL` 并在健康页计数，不阻塞入库 |
| FR-M1-14 | 数据源健康：每个数据源每次运行更新 `source_health`；连续 2 次失败为 `degraded`，连续 1 天失败为 `unavailable` |
| FR-M1-15 | FINRA 空头、CBOE 期权统计入库并进全量库（`kind=short_interest` / `options_stats`） |
| FR-M1-16 | 所有任务写 `ingest.job_runs`（README §3.11） |
| FR-M1-17 | **LLM 用量记录**（v6）：每次 LLM 调用写一行 `ingest.llm_calls`：`call_id, task, model, purpose(分级层次或调用方模块), input_tokens, output_tokens, latency_ms, status, info_ids text[], created_at`。token 数取接口返回的 `usage`；接口没给时为 `NULL`，并标 `usage_missing`。`job_runs` 汇总每个任务的当日 token 总数。共享 LLM 客户端负责写这张表，M2、M6、M8 的调用都会自动记录 |
| FR-M1-18 | **新闻分级送 LLM**（v6），目标是省 token、同时不漏重要新闻。**第 0 层，规则，全部条目，不调用 LLM**：接口给的代码、代码 / 公司名 / 别名 / 监控实体 / 产品词表匹配、信源等级、关键词标签（指引、评级、目标价、并购、产能、出口管制、关税、召回、诉讼、监管等）。**第 1 层，批量标题初筛**：第 0 层没有命中标的池（59 只）和监控实体的条目，每 25 条打包成一次 `entity_tagging` 调用，只送标题和正文前 200 字，输出每条的实体 id 和 `material`（是否涉及标的池、监控实体、篮子所在行业或宏观政策）。**第 2 层，完整处理**（实体标注 + 字段抽取，输入同 FR-M1-12）：满足任一条件——命中标的池或监控实体；8-K；信源等级 1；第 1 层判为 `material`。**第 3 层，按需处理**：其余条目不调用 LLM，但照常入库、照常做嵌入、可以被检索；M8 回捞命中时再按需处理（用同一个接口）。同一 `source_root` 只处理一次。**积压**：最近 30 天的条目按上述规则补处理；更早的只做第 0 层和嵌入，按需处理。**预算**：参数 `llm_daily_token_budget`（初始 150 万 token，按 `deepseek-v4.1-flash` 计），超出后第 2 层只处理命中标的池的条目，其余排队到次日，健康页显示 |

## 6. 异常与降级

| 情况 | 行为 |
|---|---|
| Alpaca 行情某只缺失 | 该只当日无 bar，`source_health` 记录；不得用前一日价格填补 |
| Alpaca News 不可用 | `source_health.status = unavailable`；其他源照常；系统日志显示 |
| submissions 不可用 | `earnings_events` 用 Alpha Vantage 兜底并标注；都不可用时不生成该行 |
| LLM 抽取失败 | 信息照常入库，`extraction_status=failed`，可被规则检索 |
| 嵌入失败 | 同上，只是不能被向量检索 |

## 7. Harness 与自测

| 测试名 | 标记 | 断言 | 夹具 |
|---|---|---|---|
| `test_bar_window_to_20et` | blocking | I22：任务配置结束时间为美东 20:00 | 配置 |
| `test_bar_window_from_04et` | blocking | 开始时间为美东 04:00；半日市盘后从 13:00 起 | 配置 + 日历 |
| `test_post_close_null_when_no_trade` | blocking | 盘后无成交时 `post_close` 为 `NULL` | 合成分钟线 |
| `test_wide_universe_rules` | blocking | 四种 `exclude_reason` 都能产生；ETF 被排除 | 合成候选表 |
| `test_news_dedupe_and_times` | blocking | 同 `info_id` 只存一次；转载共用 `source_root`；时间存 UTC | 合成新闻 |
| `test_earnings_reaction_day` | blocking | I28（数据部分）：`golden/m1_earnings_sessions.json` 全部用例；10-Q 申报日不出现在 `reaction_day` 计算的输入里 | 需求方标准答案 |
| `test_earnings_fallback_flag` | blocking | submissions 缺失时用兜底源并标注 | 合成 |
| `test_form4_parse_code_p` | blocking | 解析出交易代码、高管标记、`filed_at` | 真实 Form 4 XML 样例（冻结） |
| `test_app_rank_jump` | blocking | 名次跳升 21 → 产生 info_item；跳升 20 → 不产生 | 合成快照 |
| `test_trends_unavailable_marked` | blocking | 接口异常时状态为"未接通"，无数值写入 | 模拟异常 |
| `test_source_level_mapping` | blocking | 映射表覆盖 FR-M1-09 的例子；未知来源为 4 | 配置 |
| `test_info_item_contract` | blocking | 必填字段非空；`published_at` 缺失时有标记 | 合成 |
| `test_info_fields_extraction` | blocking | 录音：指引、评级变动、抽取的发布时间三个字段；失败为 `NULL` | 录音 |
| `test_llm_extraction_failure_degrades` | blocking | 录音模拟失败 → 入库且 `failed` | 录音 |
| `test_ingest_live_smoke` | live | 真实跑一次：73 个代码有日线；新闻条数 > 0；健康表每个源都有记录 | 真实 |

**自测要附的证据**：连续 5 个交易日真实运行的 `job_runs` 和 `source_health` 导出；每日分钟线覆盖率；广域集合的入选数和各排除原因计数；随机 10 条新闻的 `published_at` 与原文核对表。

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应需求 | 阻塞 |
|---|---|---|---|---|
| AC-M1-01 | 第 7 节 blocking 测试全绿 | H | FR-M1-01–16 | 是 |
| AC-M1-02 | **覆盖**（v3 改为历史回放）：用正式采集任务回补验收日之前最近 5 个交易日，73 个代码日线覆盖 100%（Alpaca 不提供的代码按 Q-M1-5 单列，不计入分母）；**常规时段**分钟线覆盖率合计 ≥ 99%，单个代码 ≥ 95%（定义见 Q-M1-5）；盘前、盘后的采集任务全部分页取完、状态为 `ok`。**时效**：5 个回放日每天的采集耗时都不超过 25 分钟（20:20 开始可以在 20:45 前完成） | E | 感知异常（以天为单位） | 是 |
| AC-M1-02b | 至少 1 次由调度器按时触发的真实运行，在美东 20:45 前完成（v7 拆出：耗时已由回放证明，迟到原因已修复并有测试；剩下的是运维确认，不挡合并）。**期限**：2026-10-15 美东晚间那次运行（北京 10-16 08:45 前）；未通过则作为 M1 的修复项，不影响 M2 | E | 感知异常（以天为单位） | 否 |
| AC-M1-03 | 广域集合入选数在 800–2,000 之间，排除原因有统计 | E | 发现池外异常 | 是 |
| AC-M1-04 | 需求方抽 10 条新闻，`published_at` 与原文误差 ≤ 1 分钟。`source_root`：生产库里**全部**同根组逐组核对归并正确；再加 5 组冻结的真实转载身份审计样例（不同 URL、同一原稿），按 Q-M1-10 的规则归并正确（v5：Alpaca News 只有 Benzinga 一个来源，库里几乎没有跨媒体转载，原条款要求抽 5 条生产库转载与数据源不符） | E | 源头时间准确 | 是 |
| AC-M1-05 | 需求方抽 10 次 59 只标的的历史财报发布，`earnings_events.reaction_day` 与 SEC 原始接收时间推算一致 | E | 财报反应日 | 是 |
| AC-M1-06 | 断开一个数据源（例如改错 Trends 地址），健康页在下一次运行后显示"未接通"或"degraded"，其他源不受影响 | D | 数据断了能看见 | 是 |
| AC-M1-07 | 全量库没有因为"不重要"而被丢弃的信息：采集计数 = 入库计数 + 去重计数 | E | 源头不被过滤 | 是 |
| AC-M1-08 | 实体标注失败率 < 5%；嵌入失败率 < 2% | E | 回捞可用 | 否 |
| AC-M1-09 | **分级效果**（v6）：用最近 7 个交易日的真实新闻跑一遍分级。（1）报告各层条数、每层 token 数和每日总 token 数，日均不超过预算；（2）需求方从第 3 层（未送 LLM）随机抽 30 条，其中不应有本应进入第 2 层的重要新闻；（3）冻结用例：东芝扩产（2026-10-02，东芝不在标的池里）和 OpenAI ARR（2026-10-08）的相关新闻必须进入第 2 层 | E | 不漏重要新闻、控制成本 | 是 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M1-1 | 分钟线从几点开始？ | 美东 04:00 |
| Q-M1-2 | 盘后没有成交时盘后收盘价怎么填？ | `NULL` |
| Q-M1-3 | 广域集合的市值从哪来？ | SEC frames 的 `EntityCommonStockSharesOutstanding` × 收盘价 |
| Q-M1-4 | 全量库会不会按重要性删信息？ | 不会。只存不删；90 天后正文可以清空，摘要和向量保留 |
| Q-M1-5（K01） | 分钟线覆盖率怎么算？用哪个 feed？Alpaca 取不到的代码怎么办？ | **分母只算常规时段**：每个代码每天的常规时段分钟数（390；半日市 210）。分子是实际存下的常规时段分钟 bar 数。盘前、盘后没有成交的分钟本来就不会有 bar，所以不计覆盖率，只要求任务把 04:00–20:00 的分页全部取完（`next_page_token` 为空），状态为 `ok`。**不得补造空 bar**。feed 必须是 `sip`；如果 R5 只给 IEX，健康页显示 `degraded: feed=iex`，AC-M1-02 判不通过，由用户决定是否升级套餐，不得静默改用 IEX。Basic 套餐的历史 SIP 不含最近 15 分钟，所以当日任务从美东 20:20 开始，20:45 前完成。Alpaca 取不到的代码（例如 SKHY）留在标的池里，标 `no_bar`；自测报告单列，不换数据源，是否从标的池删除由需求方决定 |
| Q-M1-6（K02） | 普通股怎么识别？多类别股、ADR、股本新鲜度？ | 候选 = Alpaca `active` 的 `us_equity`，交易所为 NYSE、NASDAQ、NYSE American、NYSE Arca、Cboe BZX。CIK 用 SEC `company_tickers_exchange.json` 映射，映射不到记 `no_cik`。**证券类型**用三类证据按顺序判定，并把命中的证据写进 `exclude_reason` 的备注：（1）Alpaca 资产属性；（2）代码后缀（如 `.WS`、`.U`、`.R`、`-P` / `.PR`）；（3）名称关键词（ETF、Fund、Trust、Notes、Preferred、Depositary、ADR、ADS 等）。命中任一类即 `non_common`。同一发行人的多个普通股类别（如 GOOGL / GOOG）都可以入选，市值 = 发行人总股本 × 本类别价格，并标 `multi_class_approx`。股本取最近两个季度的 frames（`CY{年}Q{季}I`）；两期都没有这家公司，记 `no_shares`，不改用其他标签或数据源 |
| Q-M1-7（K03） | ADV20 窗口不足、缺价格、每日检查和恢复、复权因子方向？ | ADV20 必须有完整的 20 个交易日、每天都有价格和成交量，否则记 `insufficient_history`；当日没有价格记 `no_price`；缺的值不补。**市值只在每月第一个交易日判定**，用当天收盘价。**成交额每日检查**：当月成员某天 ADV20 跌破门槛，当天剔除（`below_adv`）；被剔除的股票只在下一个月度重算时重新判定是否恢复。`adj_factor` 只反映拆股，不含分红：拆股调整价 = 原始价 × `adj_factor`；最新一天的因子为 1，发生新拆股后重算历史各日 |
| Q-M1-8（K04） | Atom 只有最新 100 条，怎么保证全市场？submissions 原始表？ | Atom 每 10 分钟轮询一次，作为增量来源；次日用 EDGAR 每日索引（`Archives/edgar/daily-index/` 的 `form.idx`）补齐前一天全部 8-K。补进来的条目 `first_seen_at` 记补齐的时间，`published_at` 记索引里的申报日，并标 `published_at_date_only`。submissions 原始记录写进 `ingest.sec_filings`（第 4 节），覆盖 59 只、2015-01-01 起的全部申报。**接收时间的权威来源（v3 更正）**：以申报索引页（`…-index.html`）上的 "Accepted" 为准，它是美东当地时间，按 `America/New_York` 转换成 UTC 后存入 `accepted_at`。submissions JSON 里的 `acceptanceDateTime` 只作为证据原样保存，**不得**用来生成 `accepted_at`。v2 曾写"`acceptanceDateTime` 实际是美东时间"，这是需求方的错误：三个真实样例与索引页相差 8 或 10 小时，见 Q-M1-20。索引页取不到或格式异常时，保留原始申报记录，并记下 URL、错误类别、HTTP 状态和待重试状态；**不生成**未经核实的 `reaction_day` |
| Q-M1-9（K05） | Alpha Vantage 兜底没有精确时间；golden 的 `closed_day` 和文档的 `closed` 不一致？ | 兜底源有"盘前 / 盘后"字段时，按该字段确定 `session` 和 `reaction_day`。只有日期时，`session` 和 `reaction_day` 都为 `NULL`，标 `earnings_event_fallback` 和 `earnings_time_unknown`，依赖反应日的规则当期不触发。兜底只用于未来的预定发布；历史缺口记 `earnings_event_missing`。之后 submissions 出现对应的 8-K 时，用 SEC 数据替换兜底行，旧行保留在历史里。**枚举统一为 `closed`**，需求方已修正 golden（`m1_earnings_sessions.json` 和 MANIFEST 已更新） |
| Q-M1-10（K06） | `source_root` 的算法？更新稿怎么处理？ | 采用复述单第 3 节的 B 方案。格式：有上游原生 id 时为 `{提供方}:{原生id}`，否则为 `sha256:{规范化正文的哈希}`。规范化只做 HTML 去标签、Unicode NFKC、空白合并；**不删**数字、标点、否定词和引语。不按标题相似、同股票、同主题或 LLM 判断合并。同一 `info_id` 的更新稿写进 `ingest.info_item_versions`，不算新条目、不算新根 |
| Q-M1-11（K07） | FINRA 和 CBOE 的接口和粒度？要不要专表？ | FINRA 用复述单里的 `consolidatedShortInterest` 数据集。开发先用真实响应核对它是否覆盖 NYSE / Nasdaq 上市的标的；覆盖的才用，不覆盖就把该源标 `未接通`。不得用日度做空成交量顶替空头持仓。空头占比的分母用 frames 的流通股本，字段名写明 `si_pct_shares_outstanding`（不是自由流通股）。CBOE 只存市场级统计。两者都进专表（第 4 节），同时写 `info_items`。单股期权数据第一阶段为 `NULL` |
| Q-M1-12（K08） | 畅销榜源、监控清单、Trends 窗口、榜单跳升的基准？ | 畅销榜用复述单里 Apple 旧 RSS 的 `topgrossingapplications`；取不到就标 `未接通`，**不用付费榜替代**。监控清单 `config/monitored_entities.yaml` 由开发按规格第 4.1 节起草（OpenAI / ChatGPT、Anthropic / Claude、Google Gemini、DeepSeek、Meta AI / Muse 等），每个实体写明 `entity_id, name, aliases, tickers, app_ids, trends_keywords, urls`，需求方在 PR 里审核。Trends：美国范围，每个关键词单独查 `today 3-m`；均值 = 同一次请求里当天之前 90 个完整日的平均值，不含当天；有效天数不足 60 天不判定（标 `trend_window_short`）；全为 0 时不判定。榜单跳升和上一次小时快照比较；上次不在前 100 的，按第 101 名计算 |
| Q-M1-13（K09） | FRED key、版本和发布时间？美联储 / EIA 新闻稿？ | FRED key 加入 R5 清单（README §8）。6 个 series 按复述单：CPIAUCSL、PAYEMS、DGS2、VIXCLS、DCOILWTICO、DTWEXBGS，保存原始单位。用 FRED 的 `realtime_start` 作为可见日期：`published_at` = `realtime_start`，并标 `published_at_date_only`。不用最新修订值改写历史，修订值另存新行。~~美联储和 EIA 新闻稿第一阶段不做~~（**v6 撤销**：这是需求方 v2 时为了缩小范围做的决定，没有实际障碍。两者都有公开 RSS，不需要 key，见 Q-M1-26） |
| Q-M1-14（K10） | `info_items` 缺字段；摘要谁做；嵌入模型和维度？ | 字段按第 4 节 v2 补齐。`summary` 用规则截取，不是 M10 的 `summary_oneliner`。90 天后清空正文的前提是 `summary` 已有值。嵌入用 DashScope `text-embedding-v3`，1024 维（R5 给出其他模型时由需求方改文档），输入为标题加正文前 2,000 字，不切分。**共享 LLM 客户端由本模块建**：`inves_cog/llm/client.py` 提供 `call(task: str, payload: dict) -> dict`，内部经 `registry` 选模型。录音按 `tests/fixtures/phase1/recordings/{task}/{payload 规范 JSON 的 sha256}.json` 存取。M2、M6、M8 用同一个接口，不另写客户端 |
| Q-M1-15（K11） | 读图谱的权限？`job_runs` / `source_health` 谁建？ | 采用 B 方案。需求方已在 README §3.6（v1.4）给 `role_ingest` 加上 `graph` 只读权限。**授权本模块**在自己的 PR 里同步修改 `migrations/phase1_m0_0001_schemas_roles.sql` 中这一处授权，并修改 `tests/harness/tools/permissions.py` 的 `READS`，这是第一阶段唯一允许改 M0 文件的例外，其他内容不动。M6 建成后，从 `graph.monitored_entities` 读取监控实体，读取方式只用 SQL，不导入 M6 的代码。`ingest.job_runs` 和 `ingest.source_health` 的建表放在本模块的第一个迁移 `phase1_m1_0001_*`，字段按 README §3.12 和本文第 4 节；M2 只往里写自己的行。**SEC 共享客户端也由本模块建**（`inves_cog/ingest/sec_client.py`）：进程内限频 5 次/秒，`User-Agent` 读环境变量 `SEC_USER_AGENT`（R5）；M1 和 M2 的 SEC 任务排程不重叠，合计不超过 5 次/秒 |
| Q-M1-16（K12） | 健康状态的优先级、"一天"的口径、重试和超时参数？ | 状态优先级：`未接通` > `unavailable` > `degraded` > `ok`。`未接通` = 没有配置（缺 key 或环境变量），或该源已确认不可用（例如 pytrends 被封）。`degraded` = 连续 2 次运行失败。`unavailable` = 最近一次成功距今超过 24 个自然小时，且最近 2 次运行都失败。News 也按这条规则判定，不单独处理。运行成功 1 次即恢复为 `ok`。每个 HTTP 请求遇到 429、5xx 或超时最多重试 3 次，指数退避，单次等待不超过 60 秒；401、403 和格式错误不重试。单个任务超时 30 分钟。复述单里的限频参数（Alpaca ≤ 120 次/分、SEC 5 次/秒共享、Trends 请求间隔 ≥ 10 秒、官网同域间隔 ≥ 2 秒、FINRA 60 次/分、FRED ≤ 30 次/分）全部批准，写进 `config/params/p-2026.10/m1.yaml` |
| Q-M1-17（K13、K14） | M0 的两处测试与后续模块冲突：里程碑负例依赖 M1 尚未开发；干净环境断言写死迁移只有一个 | **用户答复**：授权在 M1 PR 里修这两处。`test_milestones_consistency` 的"模块关闭但测试缺失"负例改用临时仓库副本；`test_m0_ci.py` 改为断言迁移清单与 `migrations/` 下实际的 SQL 文件一致，且包含 M0 迁移。测试名、门禁逻辑和真实 milestones 不变 |
| Q-M1-18（K15） | `test_pending_registry` 的棘轮探针读的是真实 pending | **用户答复**：授权只改该探针的输入，改用临时 pending 和只含 M0 的临时 milestones；棘轮实现不变 |
| Q-M1-19（K16） | 模型名扫描把官网域名 `deepseek.com` 误判为模型名 | **用户答复**：授权修改 `tests/harness/tools/checks.py` 的识别逻辑：HTTP(S) 主机名里只由字母组成的品牌域名不算模型名；URL 路径、查询参数里的模型名，以及带版本号的 token 仍然拦截。原 `test_llm_models_allowed` 里同时补充正例和负例；白名单不变 |
| Q-M1-20（K17） | 三个真实样例显示 `acceptanceDateTime` 并不是美东时间，与 v2 的 Q-M1-8 冲突 | **用户答复**：采用索引页 Accepted。已写入 Q-M1-8（v3）。三个冻结样例：`tests/fixtures/phase1/m1/sec_acceptance_conflict.json` |
| Q-M1-21 | R4 怎么接？ | **已解决（用户提供）**：两个对话模型都通过阿里云 Token Plan 的 OpenAI 兼容接口（`token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`）接入，模型名仍只有 `glm-5.3` 和 `deepseek-v4.1-flash`，经 `registry` 选择 |
| Q-M1-22 | 嵌入接口不通（Token Plan 返回 404，`DASHSCOPE_API_KEY` 返回 401） | 嵌入只影响 AC-M1-08（**非阻塞**），不挡 M1 验收；未接通期间 `embedding = NULL`，健康页显示"未接通"。排查办法见 M1 验收报告 |
| Q-M1-23（K18） | 首次上线不在月初，广域集合怎么建？ | **用户答复**：首次上线当天收盘后建一次 `startup_baseline`，按月度规则完整判定（市值和成交额两个条件都判定）；此后每月第一个交易日重算，其余交易日只做成交额剔除（Q-M1-7）。不得伪造"月初快照" |

> 编号对照：开发的 `handoff/M1/questions.md` 里 K13–K18 对应本文 Q-M1-17、Q-M1-18、Q-M1-19（K16）、Q-M1-20（K17）、Q-M1-23（K18）。以本文编号为准。
| Q-M1-24 | 生产库凑不出 5 条真实转载 | 需求方更正 AC-M1-04（v5）：全部现有同根组逐组核对，加 5 组冻结的真实转载审计样例。不得用合成稿件冒充真实转载 |
| Q-M1-25 | 官网监控 403 | **需求方核实（2026-10-15）**：5 个监控站点里只有 OpenAI 的新闻页返回 403，原因是 Cloudflare 的 JS 人机验证，换 UA 也没用；它的 RSS `https://openai.com/news/rss.xml` 返回 200。Google AI 博客已改地址（301 跳转到 `blog.google/innovation-and-ai/technology/ai/`），Anthropic、DeepSeek、Meta 都正常。**规则**：（1）站点提供 RSS 的优先用 RSS，OpenAI 改用上述 RSS；（2）跟随重定向；（3）每个 URL 单独记录健康状态，一个站点失败不影响其他站点，也不把整个源判为失败（任务书 §4.6 第 6 条）；（4）`source_health` 里的源名从 `CompanyIR` 改为 `EntitySites` |
| Q-M1-26 | 美联储 / EIA 新闻稿 | **加回第一阶段**：美联储 `https://www.federalreserve.gov/feeds/press_all.xml`；EIA `https://www.eia.gov/rss/press_rss.xml` 和 `https://www.eia.gov/rss/todayinenergy.xml`。需求方已核实三者都返回 200。入 `info_items`（`kind=news`，`source_level=1`），按 FR-M1-18 直接进入第 2 层 |
| Q-M1-27 | 嵌入返回 401 | **需求方核实**：证据显示 `DASHSCOPE_API_KEY` 填的是 Token Plan 的 key，而且没有配置 `DASHSCOPE_BASE_URL`。这是配置错误，不是缺 key。改用用户提供的 DashScope key 和对应地址，先用 `GET {base}/models` 验证，再对全部条目做嵌入（嵌入不按 FR-M1-18 分级） |
| Q-M1-28 | 生产库唯一的同根组是两篇不同的文章（Benzinga "Earnings Scheduled For October 5 / October 12"），正文都是同一段 163 字的模板，被正文哈希归成一根 | 需求方更正 Q-M1-10：没有上游原生 id 时，**规范化正文少于 300 个字符**的，哈希改用"规范化标题 + 规范化正文"；不少于 300 字符的，规则不变。这个误合并在 AC-M1-04 里算作归并错误 |
