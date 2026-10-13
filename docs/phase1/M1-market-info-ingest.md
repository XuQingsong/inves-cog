# M1 行情与信息采集

| 项 | 内容 |
|---|---|
| 文档版本 | v1 |
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
| 分钟线 | 59 只 + 14 只 ETF，美东 04:00–20:00 | 每日 08:00（北京）补齐前一交易日；20:00（北京）补当日盘前 |
| 日线 | 59 + 14；广域集合 | 每日 |
| 广域集合成员 | 市值 ≥ 20 亿美元且 20 日均成交额 ≥ 2,000 万美元的普通股 | 成员每月第一个交易日重算；成交额条件每日检查 |
| 新闻 | Alpaca News 全市场；首次上线回补 90 天 | 每日 + 盘前复核前 |
| SEC | 8-K Atom 流（全市场）；59 只的 submissions（含 8-K items、acceptanceDateTime）；59 只的 Form 4 | 每日 |
| `earnings_events` | 59 只 | 每日（由 submissions 生成） |
| App Store 榜单 | 美国免费榜、畅销榜前 100 | 每小时 |
| Google Trends | 监控实体 | 每日 |
| 官网变化 | 监控实体的官网 URL 清单 | 每日 |
| 空头、期权统计 | FINRA 空头（每月两次）、CBOE 每日期权统计 | 按发布频率 |
| 宏观 | FRED（沿用 stock-pm 现有任务，只需接入全量库） | 每日 |
| 全量库 | 以上所有信息统一入 `ingest.info_items`，带实体、信源等级、向量 | 随采集 |
| 数据源健康 | 每个数据源的状态 | 每次任务 |

**不做**：说法抽取（M8）、异常判断（M7）、任何对信息的过滤或丢弃（全量库只存不删，90 天后只是转为"摘要 + 向量"）、社交数据、财报数字（M2）。

**边界澄清**：

- 分钟线窗口从 **04:00** 开始（盘前复核需要盘前价格），到 **20:00** 结束（I22）。规格只写了结束时间，开始时间以本文为准。
- "盘后收盘价"= 美东 20:00 前最后一根有成交的分钟线收盘价；当天盘后没有成交则为 `NULL`，不得用常规收盘价代替。
- 广域集合的市值 = SEC frames 接口最近一期 `dei/EntityCommonStockSharesOutstanding` × 最近收盘价；取不到股本的股票不进集合，记入"未入选原因"统计。ETF、ADR 以外的特殊证券（优先股、权证、单位）不进集合。
- 全量库里"首次取得时间" `first_seen_at` 是系统第一次拿到这条信息的时间；"发布时间" `published_at` 来自信源。两者都必须存，归因的时间对齐用 `published_at`，鉴伪用两者之差。

## 3. 输入

| 输入 | 来源 |
|---|---|
| 59 只标的、14 只 ETF | `config/universe.yaml`（规格第 3.3 节） |
| 监控实体清单 | M6 的 `graph.monitored_entities`；M6 完成前用 `config/monitored_entities.yaml` |
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

**`ingest.earnings_events`**：规格第 4.2 节的字段，加 `session` 的取值 `closed`（休市日发布）。

**`ingest.form4_events`**：`ticker, filed_at, insider_name, is_officer, transaction_code, shares, price, accession`

**`ingest.app_rank_snapshots`**：`ts_utc, chart(free/grossing), rank, app_id, app_name, developer`

**`ingest.source_health`**：`source, last_success_at, last_attempt_at, status(ok/degraded/unavailable/未接通), latency_sec, items_last_run, note`

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M1-01 | 分钟线采集窗口美东 04:00–20:00；每根 bar 标 `session`；半日市的盘后从 13:00 起 |
| FR-M1-02 | 日线与 `post_close`；拆股复权因子单独存，原始价格不改写 |
| FR-M1-03 | 广域集合按第 2 节边界规则生成；每次重算保存全部候选及 `exclude_reason`（`no_shares`、`below_mktcap`、`below_adv`、`non_common`） |
| FR-M1-04 | 新闻：按 `info_id` 去重；同一稿件不同 URL 用 `source_root` 归并；保存 `published_at`、`first_seen_at`；首次上线回补 90 天 |
| FR-M1-05 | SEC：8-K Atom 全市场入全量库（`kind=sec_8k`，`source_level=1`）；59 只的 submissions 每日拉取 |
| FR-M1-06 | `earnings_events`：由 submissions 中 `form=8-K` 且 `items` 含 `2.02` 的记录生成；`session` 和 `reaction_day` 按 README §3.1 和规格第 4.2 节；`ref_close` = 反应日之前最后一个常规收盘价；`fiscal_period` 在对应 10-Q / 10-K 申报后回填；submissions 缺失时用 Alpha Vantage 财报日历补并标 `earnings_event_fallback` |
| FR-M1-07 | Form 4：解析非衍生交易表，保留交易代码（`P` 为公开市场买入）、是否高管（officer 标记）；按 `filed_at` 可见 |
| FR-M1-08 | App Store：每小时存快照；每次快照后对监控实体计算名次变化，名次跳升 > 20 写一条 `info_items`（`kind=app_rank`） |
| FR-M1-09 | 信源等级：`config/source_levels.yaml` 映射来源 → 等级。一级：SEC、公司官网和 IR、政府和央行；二级：Reuters、Bloomberg、WSJ、FT、CNBC、AP 等一线媒体；三级：卖方和专业财经媒体；四级：聚合、转载、匿名信源、无法识别的来源（默认） |
| FR-M1-10 | Google Trends：监控实体每日热度；接口失败时 `source_health.status = 未接通`，不写模拟值；热度 > 自身 90 日均值 3 倍写一条 `info_items`（`kind=trend`） |
| FR-M1-11 | 官网变化：监控 URL 每日抓取，正文哈希变化时写 `info_items`（`kind=site_change`），`body` 存差异片段 |
| FR-M1-12 | 实体标注：`deepseek-v4.1-flash` 的 `entity_tagging` 任务，输入标题和正文前 2,000 字，输出图谱实体 id 列表；规则先用代码 / 公司名词表匹配，LLM 只补充；失败重试 2 次后 `extraction_status=failed`，信息照常入库 |
| FR-M1-12b | 字段抽取：`info_fields_extraction`（`deepseek-v4.1-flash`）为 8-K 和新闻补充三个字段：`is_guidance`（是否含业绩指引及方向：上调 / 下调 / 维持）、`is_rating_change`（是否为分析师评级或目标价变动）、`published_at`（信源未给出时从正文抽取，并标 `published_at_extracted`）；抽取失败时字段为 `NULL` |
| FR-M1-13 | 嵌入：DashScope 嵌入；失败时 `embedding=NULL` 并在健康页计数，不阻塞入库 |
| FR-M1-14 | 数据源健康：每个数据源每次运行更新 `source_health`；连续 2 次失败为 `degraded`，连续 1 天失败为 `unavailable` |
| FR-M1-15 | FINRA 空头、CBOE 期权统计入库并进全量库（`kind=short_interest` / `options_stats`） |
| FR-M1-16 | 所有任务写 `ingest.job_runs`（README §3.11） |

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
| `test_earnings_reaction_day` | blocking | I28（数据部分）：`requirements/m1_earnings_sessions.json` 全部用例；10-Q 申报日不出现在 `reaction_day` 计算的输入里 | 需求方标准答案 |
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
| AC-M1-02 | 连续 5 个交易日：73 个代码日线覆盖 100%；分钟线（04:00–20:00）覆盖率 ≥ 99%；每天北京 08:00 前完成 | E | 感知异常（以天为单位） | 是 |
| AC-M1-03 | 广域集合入选数在 800–2,000 之间，排除原因有统计 | E | 发现池外异常 | 是 |
| AC-M1-04 | 需求方抽 10 条新闻，`published_at` 与原文误差 ≤ 1 分钟；抽 5 条转载，`source_root` 归并正确 | E | 源头时间准确 | 是 |
| AC-M1-05 | 需求方抽 10 次 59 只标的的历史财报发布，`earnings_events.reaction_day` 与 SEC 原始接收时间推算一致 | E | 财报反应日 | 是 |
| AC-M1-06 | 断开一个数据源（例如改错 Trends 地址），健康页在下一次运行后显示"未接通"或"degraded"，其他源不受影响 | D | 数据断了能看见 | 是 |
| AC-M1-07 | 全量库没有因为"不重要"而被丢弃的信息：采集计数 = 入库计数 + 去重计数 | E | 源头不被过滤 | 是 |
| AC-M1-08 | 实体标注失败率 < 5%；嵌入失败率 < 2% | E | 回捞可用 | 否 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M1-1 | 分钟线从几点开始？ | 美东 04:00 |
| Q-M1-2 | 盘后没有成交时盘后收盘价怎么填？ | `NULL` |
| Q-M1-3 | 广域集合的市值从哪来？ | SEC frames 的 `EntityCommonStockSharesOutstanding` × 收盘价 |
| Q-M1-4 | 全量库会不会按重要性删信息？ | 不会。只存不删；90 天后正文可以清空，摘要和向量保留 |
