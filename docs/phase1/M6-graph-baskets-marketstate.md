# M6 图谱、篮子与价格结构层

| 项 | 内容 |
|---|---|
| 文档版本 | v6（答复开工复述 K01–K02；答复后冻结，见阶段任务书 §4.7） |
| 规格章节 | 3.1、3.5、6.11、11.3 |
| 依赖 | M1（行情、全量库）、M2（10-K 原文、分部） |
| 关闭的不变量 | 无（为 M7、M8、M9 提供基础） |
| 规模 | 中（图谱审核是最大的一次性人工工作量） |

## 1. 目标

建出"市场的结构"：谁和谁有关系、关系有多大（美元暴露）、哪些股票该放在一个篮子里比较；再用纯价格算出每只股票、每个篮子"剔除大盘和板块之后还剩多少涨跌"，以及市场是否处在系统性冲击中。

对应需求："动态的市场从 4 个层级来构建市场主体"；"建出符合逻辑的传导链，以及这条链影响到哪里"；"能感知股价异常"。

## 2. 范围

**做**：

- 图谱：实体、关系（四类连接、机制、方向、强度、状态、美元暴露、证据）；
- 种子起草（`glm-5.3`：`graph_seed_draft`、`exposure_draft`）与按篮子批量审核；
- 篮子：L2 板块篮子、13 个 L3 篮子（规格第 3.5 节）、主篮子指定、生效时间；每周自动聚类的"未命名篮子"建议；
- 监控实体清单（给 M1 的榜单、趋势、官网采集用）；
- 价格结构层 `marketstate`：因子构造、β、剩余涨跌、σ、篮子剩余与广度、`shock_flag`、`l1_state`、`beta_share_5d`。

**不做**：异常判定（M7）；归因（M8）；页面（M10 渲染 `/graph`，本模块提供审核 API 和命令行批量确认）。

**边界澄清**：

- `marketstate` **只用价格**：不读新闻、不读 LLM 结果、不读估值；篮子定义是它唯一读取的非价格数据（I01 已在 M0 门禁）。
- 新边一律从"候选"开始；LLM 起草的关系和美元暴露在用户确认前状态为"候选"，**不进隐含幅度检验**。
- 计算剩余涨跌时，篮子收益**不含本股**（留一法），避免"自己解释自己"。

## 3. 输入

| 输入 | 来源 |
|---|---|
| 日线、盘后收盘 | M1 `ingest.bars_daily`；收益率用拆股调整价（原始价 × `adj_factor`），见 Q-M6-4 |
| VIX | `ingest.macro_observations`：当日用 CBOE 收盘（`VIX_CBOE`），FRED `VIXCLS` 作为备用，见 Q-M6-5 |
| 广域股票的行业代码 | `ingest.issuer_profiles`（v3 新增），见 Q-M6-6 |
| 10-K / 10-Q 原文（业务、客户集中度、RPO 附注） | 按 M1 `ingest.sec_filings` 的 `primary_document`，用共享 SEC 客户端取原文，见 Q-M6-7 |
| 分部收入 | M2 `fundamentals.segments` |
| 初始监控实体 | `config/monitored_entities.yaml`（OpenAI、Anthropic、DeepSeek、Meta Muse、ChatGPT、Gemini、东芝等） |

## 4. 输出

**`graph.entities`**：`entity_id, kind(company/private_company/product/app/model/workload/segment/theme), name, aliases, ticker(可空), app_store_ids, trend_keywords, official_urls`

**`graph.relations`**：规格第 6.11 节全部字段（含 `exposure_usd`、`exposure_basis`、`exposure_asof`、来源信息 id）+ `status`、`drafted_by`、`reviewed_at`

**`graph.baskets`**：`basket_id, level(L1/L2/L3/auto), name, benchmark, members[{ticker, weight, primary(bool), effective_from, effective_to}]`

**`graph.monitored_entities`**：`entity_id, reason(basket upstream/seed), channels(app/trend/site)`

**`marketstate.daily`**（每只股票每个交易日、每个时段一行）：

`trade_date, ticker, session(close/post), ret, resid, resid_z, sigma, beta_m, beta_s, beta_t, primary_basket, resid_5d, resid_5d_z, beta_share_5d`

**`marketstate.baskets`**：`trade_date, basket_id, session, ret_ew, resid, resid_z, same_sign_share, member_resid_std`

**`marketstate.rotation`**（v4 新增，每个交易日、每个时段一组行）：`trade_date, session, group_kind(index/style/sector/l3), group_id, ret, z, ret_5d, z_5d, rank, rank_5d`

**`marketstate.market`**：`trade_date, spy_5d_pct, vix, vix_pctile_252, down_share_5d_pct, shock_flag, l1_state`；v5 追加 `vix3m, vix_term_inverted(bool：vix3m < vix), spy_drawdown_252_pct`（SPY 收盘相对过去 252 个交易日最高收盘的跌幅，含当日）

## 5. 功能需求

**图谱与篮子**

| 编号 | 需求 |
|---|---|
| FR-M6-01 | 实体与关系的表结构按第 4 节；四类连接分开存；机制取值：供给 / 需求 / 竞争 / 客户融资 / 估值倍数 |
| FR-M6-02 | 种子起草：对 59 只逐一调用 `graph_seed_draft`，输入最近一期 10-K 的业务描述、客户集中度、竞争段落；输出关系列表，每条必须引用原文片段位置；无引用的丢弃 |
| FR-M6-03 | 美元暴露起草：`exposure_draft` 从客户集中度、RPO 附注、8-K 合同公告、M2 分部收入中提取金额；每个金额必须带信息 id 或申报编号；`exposure_basis` 取值：收入占比 / RPO / 合同 / 应收 / 预付 / 分部收入 |
| FR-M6-04 | 审核：提供"按篮子列出全部候选关系和暴露 → 批量确认 / 驳回 / 修改"的接口和命令行；确认后状态变为"观察到"，记录审核时间 |
| FR-M6-05 | 篮子：L2 = 规格第 3.3 节的板块；L3 = 规格第 3.5 节的 13 个；每只股票必须指定一个主 L3 篮子（没有合适 L3 的，主篮子为空，只用 L2）；成员变化带生效时间 |
| FR-M6-06 | 自动聚类：每周用最近 60 个交易日的剩余收益相关系数，层次聚类，相关系数 > 0.6、成员 ≥ 3、与任何现有篮子的成员重合度（Jaccard）< 0.5 的组合输出为"未命名篮子"建议，等待人工命名 |
| FR-M6-07 | 监控实体：每个 L3 篮子成员的客户 / 供应商 / 竞争对手中，`kind` 为非上市公司、产品、应用、模型的实体，加上初始清单；输出每个实体的榜单 id、趋势关键词、官网 URL |

**价格结构层**

| 编号 | 需求 |
|---|---|
| FR-M6-08 | 因子：`f_m` = SPY 日收益；`f_s` = 本股所属 L2 板块的等权收益（不含本股）对 `f_m` 回归的残差；`f_t` = 本股主 L3 篮子的等权收益（不含本股）对 (`f_m`, `f_s`) 回归的残差 |
| FR-M6-09 | β：个股日收益对 (`f_m`, `f_s`, `f_t`) 做含截距的 OLS，窗口为信号日之前 120 个交易日（不含当日）；剩余 = 当日收益 − α − β·f；σ = 窗口内残差的标准差（自由度 = 样本数 − 参数个数）；`resid_z = resid ÷ σ`；窗口内有效样本 < 60 时 `resid` 为 `NULL` 并标 `insufficient_history` |
| FR-M6-10 | 广域集合股票没有 L2 / L3 篮子：用 SPY 和按 SIC 映射的行业 ETF 做因子（映射表 `config/sic_to_etf.yaml`） |
| FR-M6-11 | 盘后时段：`ret_post = post_close ÷ close − 1`；因子用 SPY 和篮子成员的同时段收益；β 沿用日收益的估计；`post_close` 为空时该行 `NULL` |
| FR-M6-12 | 5 日剩余：`resid_5d` = 最近 5 个交易日剩余之和；`resid_5d_z = resid_5d ÷ (σ × √5)`；`beta_share_5d = 1 − |resid_5d| ÷ |5 日总收益|`，限制在 [0, 1]；5 日总收益绝对值 < 0.5% 时为 `NULL` |
| FR-M6-13 | 篮子：L2 篮子等权收益对 `f_m` 回归；L3 篮子对 (`f_m`, 所属 L2 的 `f_s`) 回归；同样 120 日窗口；输出 `resid_z`、同号成员比例、成员剩余的标准差 |
| FR-M6-14 | 市场：`vix_pctile_252` = 当日 VIX 在过去 252 个交易日（不含当日）收盘中的百分位秩（≤ 当日值的比例 × 100）；`down_share_5d_pct` = 标的池 + 广域集合中 5 日收益 < 0 的比例；`shock_flag`、`l1_state` 按 `golden/m6_marketstate.json` 的规则（规格第 11.3 节加本文。**v5 警戒**：以下三个条件至少满足两个——SPY 5 日 ≤ −3%、VIX 分位 ≥ 70、5 日下跌比例 ≥ 60%；**或** `vix_term_inverted` 为真；**或** `spy_drawdown_252_pct` ≤ −10%。v4 的"满足任一条件"在平静期也有 15–25% 的天数报警，失去区分度） |
| FR-M6-15 | 每天北京 08:55 完成（美东 20:55；冬令时北京 09:55，见 README §3.1）（M1 之后、M7 之前）；写 `job_runs` |
| FR-M6-16 | **资金流向图**（v4，用户 2026-10-15 提出"要综合来看市场轮动"）：每个交易日把下列分组的当日收益、z 值（收益 ÷ 自身 120 日收益标准差）、5 日累计收益和 5 日 z（σ × √5）算出来并排名，写入 `marketstate.rotation`。分组：**大盘**（SPY、QQQ、IWM）；**风格**（IWM − QQQ 的价差、MTUM − VLUE 的动量与价值价差（v5），以及 RSP − SPY 的等权与市值加权价差）；**行业**（11 只行业 ETF：XLK、XLF、XLV、XLE、XLI、XLU、XLY、XLP、XLB、XLRE、XLC，以及 SMH、IGV、地区银行 KRE（v5））；**L3 篮子**（13 个）。每天另外输出两个汇总值：行业之间最强与最弱的 z 值之差 `sector_spread_z`，以及风格价差的 z 值 `style_spread_z`。只用价格，归 M6 的价格结构层；M7 用它判定轮动，M10 在首页展示，M8 归因时可以引用"当天资金从哪里流向哪里"。**授权 M6 开发**按 Q-M6-5 的方式在 M1 的日线采集里加入 RSP 和第 11 只行业 ETF 之外缺的代码（M1 现有 14 只 ETF 里没有 XLB、XLRE、XLC、RSP；v5 再加 KRE、MTUM、VLUE），并按 Q-M6-5 同样的方式采集 CBOE 的 VIX3M 日线（`https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv`，需求方已验证可访问），写入 `ingest.macro_observations`（`series_id = VIX3M_CBOE`） |

## 6. 异常与降级

| 情况 | 行为 |
|---|---|
| 篮子成员当天行情缺失 | 该成员不计入等权收益；有效成员 < 2 时篮子当日为 `NULL` |
| VIX 缺失 | `vix_pctile_252` 为 `NULL`；`shock_flag` 只按 SPY 和广度判断，并标注 |
| LLM 起草失败 | 该公司的种子为空，进入"待起草"清单；不阻塞其他公司 |

## 7. Harness 与自测

| 测试名 | 标记 | 断言 | 夹具 |
|---|---|---|---|
| `test_marketstate_flags` | blocking | `shock_flag`、`l1_state` 全部用例（v5 共 11 个，含边界 −5.0、79.9、70，以及回撤 −10.0 / −9.9、VIX 倒挂、恰好两个条件） | `golden/m6_marketstate.json` |
| `test_residual_exact_linear` | blocking | 合成数据：个股收益 = 0.001 + 1.2·f_m + 0.5·f_s + 0.8·f_t（无噪声）→ β 估计误差 < 1e-9，当日剩余 = 0 | 合成 |
| `test_residual_leave_one_out` | blocking | 篮子收益不含本股：把本股收益放大 10 倍，篮子因子不变 | 合成 |
| `test_residual_window_excludes_today` | blocking | 改当日收益不影响 β | 合成 |
| `test_insufficient_history_null` | blocking | 有效样本 59 → `NULL` | 合成 |
| `test_post_session_null_when_missing` | blocking | 无盘后价时盘后行为 `NULL` | 合成 |
| `test_beta_share_bounds` | blocking | 限制在 [0, 1]；小于 0.5% 为 `NULL` | 合成 |
| `test_marketstate_price_only` | blocking | `marketstate` 的输入表清单只含 `ingest.bars_*`、`graph.baskets`、`ingest.macro_observations`（只取 VIX 系列）、`ingest.issuer_profiles`（只取 SIC） | 源码扫描 |
| `test_graph_draft_requires_citation` | blocking | 录音：无原文引用的关系被丢弃；无信息 id 的金额被丢弃 | 录音 |
| `test_candidate_edges_not_used` | blocking | 状态为"候选"的关系不出现在供 M8 隐含幅度使用的视图里 | 合成 |
| `test_auto_cluster_suggestion` | blocking | 构造 3 只高相关、不在同一篮子的股票 → 出现建议；与现有篮子 Jaccard ≥ 0.5 → 不出现 | 合成 |
| `test_marketstate_live_smoke` | live | 真实跑一天：59 + 广域股票都有行或 `insufficient_history` | 真实 |

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应需求 | 阻塞 |
|---|---|---|---|---|
| AC-M6-01 | 第 7 节 blocking 测试全绿 | H | FR-M6-01–15 | 是 |
| AC-M6-02 | 59 只每只至少 3 条已起草的关系，每条都有原文引用；13 个 L3 篮子和全部 L2 篮子已建立；每只股票的主篮子已指定 | E | 四层市场主体、传导链 | 是 |
| AC-M6-03 | OpenAI 合作方篮子 6 只中至少 4 只有带出处的美元暴露草稿；WDC、STX 的 HDD 分部收入已作为暴露 | E | 按渠道的隐含幅度可用 | 是 |
| AC-M6-04 | 用户已按篮子完成至少一轮批量审核（审核工具可用，需求方现场演示一个篮子的确认流程） | D | 图谱人工审核 | 是 |
| AC-M6-05 | 用真实数据复算 3 只股票、3 个交易日的剩余涨跌（需求方用独立脚本按 FR-M6-08–09 计算），误差 < 1e-6 | E | 剩余涨跌口径一致 | 是 |
| AC-M6-06 | 监控实体清单包含初始种子，且每个实体至少有一个可用渠道（榜单 / 趋势 / 官网） | E | 一手数据 | 是 |
| AC-M6-07 | 自动聚类建议每周产出一次（可以为空，但要有运行记录） | E | 发现新篮子 | 否 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M6-1 | 回归要不要截距？ | 要，剩余扣除截距 |
| Q-M6-2 | 一只股票属于多个 L3 篮子时用哪个做因子？ | 主篮子；其他篮子只在篮子层面使用 |
| Q-M6-3 | LLM 起草的暴露未审核能不能先用？ | 不能。未审核 → 隐含幅度"无法检验" |
| Q-M6-4 | 收益率用原始价还是调整价？ | 拆股调整价：`ret` = 当日调整收盘 ÷ 前一日调整收盘 − 1，调整收盘 = `close × adj_factor`。用原始价的话，拆股当天会出现假的 ±50% 或 ±90% 涨跌，M7 会误报。盘后 `ret_post = post_close ÷ close − 1` 是同一天内的比较，不受拆股影响 |
| Q-M6-5 | VIX 用哪个来源？ | 当日判定需要当天的 VIX 收盘，但 FRED 的 `VIXCLS` 通常第二天才更新。**主来源**用 CBOE 的公开日线文件 `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`（需求方已验证可以访问；v18 复现用的也是 CBOE 收盘价，结果与标准答案完全一致），作为 `series_id = VIX_CBOE` 写入 `ingest.macro_observations`；当天 CBOE 还没更新时用 `VIXCLS`，两者都没有时按第 6 节的 VIX 缺失处理。**授权 M6 开发**在 `inves_cog.ingest` 里新增这个采集任务（M1 已关闭，这是 M1 代码的唯一例外），挂在 M1 的调度器上，写 `job_runs` 和 `source_health` |
| Q-M6-6 | FR-M6-10 的广域股票按 SIC 映射行业 ETF，SIC 从哪来？ | M1 的 `ingest.wide_universe` 没有 SIC。新增表 `ingest.issuer_profiles`（`cik, ticker, sic, sic_description, fetched_at`），每月随广域集合重算一次，从 SEC submissions 取 `sic`，用共享 SEC 客户端（5 次/秒，约 1,300 次请求，约 5 分钟）。授权方式同 Q-M6-5。`config/sic_to_etf.yaml` 由开发起草，需求方审核；映射不到的用 SPY 单因子并标 `sector_unmapped` |
| Q-M6-7 | 10-K 原文从哪来？ | M2 没有保存 10-K 正文。按 `ingest.sec_filings` 的 `primary_document` 取最近一期 10-K（外国申报人取 20-F），提取 Item 1（业务）、Item 1A（风险因素）、Item 7（管理层讨论与分析）和收入、客户集中度、RPO 相关附注，存入 `graph.source_texts`（`ticker, accession, section, text, char_start, char_end, fetched_at`）。FR-M6-02 的"原文引用"就是指 `accession + section + 字符位置` |
| Q-M6-8 | 监控实体给 M1 的接口 | M1 已经实现了读取（`SELECT e.*, m.channels FROM graph.monitored_entities m JOIN graph.entities e USING (entity_id)`），两套列名都兼容（`app_ids` 或 `app_store_ids`、`trends_keywords` 或 `trend_keywords`、`urls` 或 `official_urls`）。M6 按第 4 节建表即可；`channels` 是 `text[]`，取值为 `app`、`trend`、`site`。初版内容以 `config/monitored_entities.yaml`（M1 起草、需求方已审）为准导入 |
| Q-M6-9 | AC-M6-03 的分部暴露依赖什么？ | 依赖 M2 的 `fundamentals.segments`。WDC 分拆 SanDisk 后只剩 HDD 业务，可能是单一分部，这时用合并营收作为 HDD 暴露，`exposure_basis = 分部收入`。M2 的分部映射草稿（AC-M2-08）还没生成，M6 起草暴露时直接读分部原名，不等映射审核 |
| Q-M6-10 | 为什么在 M6 加资金流向图？ | 需求方回放 2024-07 至 2026-10 的数据发现：2024-07-11（CPI 回落后小盘 +3.6%、科技 −2.2%）这类风格轮动，以及 2026-10-14 这类多因素叠加的抛售，单看某个篮子是看不全的，需要同一天把大盘、风格、行业、篮子放在一起比。这张图只用价格，不依赖 M7 的阈值，所以不必等 M7 的验证集 |
| Q-M6-11 | 为什么改警戒规则？ | 需求方回放 2019-01 至 2026-10：v4 规则下全部日子 32% 是警戒，平静期也有 15–25%；v5 规则下平静期 88–98% 为正常，2022 熊市 84% 为警戒或危机，急性冲击的判定不变；全部日子正常 71%、警戒 20%、危机 8%。VIX 期限倒挂在新冠期间 95%、关税期间 100% 的天数出现，平静期 0–5%。`golden/m6_marketstate.json` 已按 v5 重新生成 |
| Q-M6-12（K01） | 缺失原因和轮动汇总存在哪里？ | 采用 A：`marketstate.daily`、`marketstate.baskets`、`marketstate.rotation` 各加 `health_codes text[]`、`null_reason text`；`marketstate.daily` 加 `factor_set text`（实际使用的因子组合）；`marketstate.market` 加 `null_reason`、`sector_spread_z`（数值）、`style_spread_z jsonb`（键 `iwm_qqq`、`mtum_vlue`、`rsp_spy`）。缺 β 时为 `NULL`，不得用 0。第 4 节已有字段不改名 |
| Q-M6-13（K02） | 两只股票的篮子留一后只剩 1 只；跨多个 L2 的篮子用哪个行业因子？ | 采用 A：篮子自身的行仍要求至少 2 只有效成员；个股的留一篮子因子剩 1 只也照样使用，剩 0 只时退化为少一个因子的模型并在 `factor_set`、`null_reason` 里写明。个股的行业因子始终来自它唯一的主 L2；跨 L2 的篮子（AI 资本开支链、云厂商等）的行业因子用它配置的基准 ETF 对 SPY 正交化；数据中心电力篮子用 XLU、XLI 等权。篮子的 `factor_basis` 存进 `graph.baskets` |
| Q-M6-14 | 代码放哪个包？AMD 的主篮子？ | 图谱放 **`inves_cog.perception.graph`**（M0 已建；README §3.7），价格结构放 `inves_cog.marketstate`，不得新建顶层包 `inves_cog.graph`，否则绕开导入防火墙。AMD 的主 L3 篮子默认为 **AI 加速芯片**（2026 年的主要增量来自数据中心 GPU），同时是 CPU 篮子的成员；用户在图谱审核时可以改 |
| Q-M6-15（RD-M6-01） | FR-M6-08 的"回归的残差"用什么窗口？ | **逐日滚动**：每个交易日 d 的 `f_s(d)` = d 的行业等权收益 − 用 d 之前 120 个交易日（不含 d，有效样本 ≥ 60）回归 `f_m` 得到的截距和斜率算出的拟合值；`f_t(d)` 同理，对 (`f_m`, `f_s`) 回归。因子值算出后不再改。个股 OLS 再用这些逐日因子，按 FR-M6-09 计算。需求方验收时按此独立复算一致（M6 验收报告 3.1） |
| Q-M6-16（用户决定） | SKHY 没有年报业务原文、季度拼不出四季，AC-M6-02 怎么算？ | 不阻塞。关系不编造；季度数据读 M2 `interim_results`，拼不出连续四季就标"无法检验"并写明缺哪几个季度 |
| Q-M6-17（用户决定） | STX 没有 HDD 分部数据怎么办？ | STX 只有 HDD 一项业务，用 `fixed` 年报的合并营收作为 HDD 暴露，`exposure_basis = 分部收入`，并保留"单一业务，合并营收"的标记。只对配置里明确列为单一业务的公司这样做 |
| Q-M6-18 | 主 L3 和主 L2 的成员相同怎么办？ | 个股的主 L3 留一后的成员集合与主 L2 留一后的完全相同时，不用主题因子：`factor_set = m+s`，`health_codes` 加 `l3_same_as_l2`，`beta_t` 为 `NULL`。篮子自身的行不受影响 |
| Q-M6-19 | `config/sic_to_etf.yaml` 审核意见 | 批准现有规则，并补充：3714 汽车零部件、5500–5599 汽车零售、5810–5812 餐饮 → XLY；3812 国防电子、7340、8742 → XLI；3823、3825 测量仪器 → XLK；3826 实验室仪器、8731 商业研究 → XLV；7990 娱乐 → XLC；8200 教育 → XLY。按公司改正：BKNG → XLY，SHW → XLB（规则之前用 ticker 覆盖）。7389（商业服务，PYPL、UBER 等）行业太杂，仍用 SPY 单因子 |

