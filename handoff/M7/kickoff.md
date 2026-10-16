模块：M7    文档版本：v7    复述人：B 线    日期：2026-10-16

本文件只复述。不写检测代码，不改 `docs/`、golden、milestones，不改 M6，不连、不写共用库。提交后停下，等需求方答复。

## 1. 我理解本模块要做的事

每天收盘后（含盘后）只看价格，找出个股、篮子、行业、大盘上不正常的涨跌，并记下形状和资金放大特征。不写原因。新建异常的状态一律是「已发现·原因未明」。代码放在 `inves_cog.perception` 下的新子包，调用现有的 `inves_cog.marketstate`，不改 M6。

M6 给我的价格结构按已经决定的口径用，不重算因子：

- Q-M6-15：`f_s`、`f_t` 是逐日滚动的。交易日 d 的行业因子用 d 之前 120 个交易日（不含 d，有效样本至少 60）对 `f_m` 回归；主题因子再对 (`f_m`, `f_s`) 回归。因子算出后不再改。个股 β 用信号日之前 120 日。
- Q-M6-18：主 L3 留一后的成员和主 L2 留一后的成员逐日都相同，则该股没有主题因子（`factor_set = m+s`，`health_codes` 含 `l3_same_as_l2`，`beta_t` 为空）。篮子自己的行不变。路径 B 直接用 M6 已经算好的 `resid_z`。

收益和 z 与 M6 已入库的小数一致：`pct_change` 的 0.03 就是 3%。比较前不舍入。`≥`、`≤` 含等号。缺数是 `NULL`，不用 0 或前一日填。阈值放 `config/params/p-2026.10/m7.yaml`，不写进业务代码。文档给出的参数是：`watch_z = 2`、`watch_same_sign = 0.8`、`watch_abs_ret = 0.05`、`linked_abs_ret = 0.07`、`linked_member_abs_ret = 0.05`、`linked_same_sign = 0.8`。

下面每条都是「全部条件同时成立才命中」。z 的分母都是该序列自身、不含当日的 120 个交易日标准差；有效样本少于 60 则这条 z 为空，该路径不命中。

### 路径 A，总冲击（FR-M7-01）

对象：每个 L2、L3 篮子，以及本周自动聚类里尚未并入现有篮子的组合。

- `|篮子当日等权收益 ÷ 自身 120 日收益标准差| ≥ 3`
- 有行情的成员里，收益符号与篮子等权收益相同的比例 ≥ 0.60

这是原始收益的 z，不是 `marketstate.baskets.resid_z`。`same_sign_share` 是剩余的同号比例，路径 A 不用它，按成员原始收益另算。`severity = alert`，入口 `A`。

### 路径 B，个股相对异常（FR-M7-02）

先满足下面任一，再过 v6 过滤：

- `|resid_z| ≥ 3`，或
- `|个股收益 − 主 L3 篮子等权收益（不含本股）| ≥ 0.04`（4 个百分点）

v6 过滤（两条都要）：

- 个股自身 `|收益| ≥ 0.03`
- 个股收益的符号与剩余 `resid` 的符号相同

剩余为空时过不了方向过滤，不命中。没有主 L3 时，4 个百分点这条不算，只看 `resid_z`。`severity = alert`，入口 `B`。

### 路径 B，篮子（FR-M7-03）

L2 或 L3 篮子 `|resid_z| ≥ 3`。没有同号、绝对涨跌的附加条件。`severity = alert`，入口 `B_basket`。

### 关注级（FR-M7-03b）

L2 或 L3 篮子，并且还没走到路径 A：

- `|等权收益 ÷ 自身 120 日收益标准差| ≥ 2`
- 同号成员比例 ≥ 0.80（同样按原始收益，不是 `same_sign_share`）
- `|等权收益| ≥ 0.05`

`severity = watch`，入口 `A_watch`。关注级也进 M8，排在 `alert` 后面。

### 板块联动绝对幅度（FR-M7-03c）

L2 或 L3 篮子，并且路径 A 和关注级都没中：

- `|等权收益| ≥ 0.07`
- 同号成员比例 ≥ 0.80
- 每一只有行情的成员 `|收益| ≥ 0.05`

`severity = watch`，入口 `A_linked`。

### 路径 C，因子自身异常（FR-M7-04）

相对各自 120 日标准差 `|z| ≥ 3`：

- 日收益：SPY、QQQ、IWM、11 只行业 ETF，外加 KRE
- 日变化（今日值减昨日值，不是百分比）：VIX、2 年期美债（`DGS2`）、广义美元（`DTWEXBGS`）、WTI（`DCOILWTICO`）

行业 ETF 和 KRE、三大指数的 z 用 M6 `marketstate.rotation` 里已经算好的 z。宏观四条由 M7 按同样窗口自算。命中为 L1，`severity = alert`，入口 `C`。

### 大盘绝对门槛（FR-M7-04b）

下面任一成立就建 L1、`severity = watch`，即使没到 3σ。入口 `C_abs`：

- `|SPY 日收益| ≥ 0.02`，或
- `|QQQ 日收益| ≥ 0.025`，或
- VIX 收盘相对前一日上涨 ≥ 20%（`今日 / 昨日 − 1 ≥ 0.20`）

已经因路径 C 建了同一对象时，不另建一条，把 `C_abs` 并进 `entry_paths`。

### 轮动（FR-M7-12）

读 M6 `marketstate.rotation` 和 `marketstate.market` 的 `sector_spread_z`、`style_spread_z`，不另算一套 z。

1. 风格：`iwm_qqq`（IWM − QQQ）或 `mtum_vlue`（MTUM − VLUE）的 `|z| ≥ 3`。`rsp_spy` 只展示，不触发，因为这条 FR 没写它。
2. 行业：SPY 的 `|z| < 1`，且行业 ETF 最强与最弱的 z 之差 ≥ 4（用 `sector_spread_z`）。
3. 原有的主题轮动仍保留：同一天一个 L3 的收益 z ≥ 3、另一个 ≤ −3，且 SPY `|z| < 1`。这里的 z 也是收益 ÷ 自身 120 日标准差，用 `rotation` 里 `group_kind = l3` 的 z，不是篮子 `resid_z`。

命中时类型候选写「主题轮动」。`members` 写最强和最弱的分组，表示资金从哪边流向哪边。严重级别见第 6 节必须停的第 3 条，答复前不实现。

### 多日累积（FR-M7-05）

3 日和 5 日都做。M6 只存了 5 日剩余，3 日由 M7 用每日 `resid` 现算，不改 M6 的表。

- `|n 日剩余之和 ÷ (σ × √n)| ≥ 3`，n 为 3 或 5
- 这 n 天里剩余符号与累积和相同的天数占比 ≥ 0.60

同一对象当天已经有单日异常：不新建，把 `multi_3d` 或 `multi_5d` 并进那一条。

### 其余 FR

- FR-M7-06：`close`（收盘到收盘）和 `post`（收盘到盘后收盘）都算。盘后收益用 M6 的 `ret_post`。
- FR-M7-07：先做数据质量，再判定。（a）`|收益| > 0.30` 且当天 `adj_factor` 变了，先按复权价重算再判定；（b）连续 3 天收盘价完全相同，标 `stale_price`，不判定；（c）盘后累计成交量 < 20 日均量的 0.5%，标 `thin_post`，照常判定，写入 `data_quality`；（d）报价来源不一致，标「待核验」。
- FR-M7-08：同一 `trade_date`、同一 `session`，成员集合有交集，或一个是篮子、另一个是它的成员，合并成一个异常，`entry_paths` 取并集。
- FR-M7-09：归层只向上。命中路径 C 的 L1 代理 → L1；否则 L2 篮子异常且同号成员 ≥ 0.60 → L2；否则 L3 篮子异常 → L3；否则 L4。
- FR-M7-10：广域集合只跑路径 B（因子是 SPY + SIC 行业 ETF），`universe = wide`。进清单，不进 M8 的完整归因。
- FR-M7-11：每个异常一组资金放大特征。踩踏：成员 6 个月涨幅在全池加广域的前 10%；篮子 20 日平均两两相关比 60 日高 0.1 以上；跳空低开 ≤ −0.03；成交量 ≥ 20 日均量 2 倍；同号成员 ≥ 0.80。轧空：空头占流通股 ≥ 0.15 或回补天数 ≥ 5；放量 ≥ 3 倍上涨；跳空高开 ≥ 0.03。杠杆 / 被动：当天是指数调整日或月度期权到期日；相关杠杆 ETF 成交量 ≥ 20 日均量 2 倍。情绪放大留空给 M8。个股隐含波动率和偏度第一阶段不接，`NULL`。数据没有就 `NULL`，并写「未接通」或「数据暂缺」。
- FR-M7-13：北京 20:00（美东 08:00；冬令时顺延 1 小时）做盘前复核。只看持仓，以及联动事件状态为「假设中 / 市场确认 / 核查中」的标的。`premarket_z = 盘前收益 ÷ 日剩余 σ`，`|z| ≥ 3` 才置 `flag`。不创建日级异常。持仓表和联动事件表都还没有，测试用合成输入；真实盘前由 A 线在合并后跑。
- FR-M7-14：每个交易日美东 21:00 前完成日级判定（北京夏令时 09:00，冬令时 10:00）。各路径命中数和数据质量拦截数要留下。写到哪张运行表见第 6 节必须停的第 2 条。

`marketstate` 当天缺失：不判定，日志标红「价格结构未更新」，不用前一日。某篮子当天为空：跳过该篮子，成员的路径 B 照常。

## 2. 我理解本模块不做的事

- 不找原因，不做冲击分解，不判定「事件冲击 / 叙事冲击」，不渲染处置卡。这些是 M8、M10。
- 输入里不读 `ingest.info_items`，不读任何新闻。`test_no_news_dependency` 扫源码。
- 不改 M6 的表、因子和代码。M6 的问题只记在下面的疑问里。
- 不改 `docs/`、golden、milestones，不合并 PR。
- 不连、不写共用库。验收时 AC-M7-04、AC-M7-07 由需求方在只读库上复跑；AC-M7-03、AC-M7-05 的真实跑和写库由 A 线在合并后做（Q-M7-7、Q-M7-8）。
- 不把广域异常送进 M8 的完整归因（Q-M7-2）。
- 盘前复核不新建日级异常（Q-M7-4：东芝是 2026-10-02 常规时段，不拿来证明盘后）。

## 3. 输入

| 输入 | 来自 | 没有时 |
|---|---|---|
| `marketstate.daily` / `baskets` / `rotation` / `market` | M6。文件模式下用现有 `calculate()` 在内存里算，不 INSERT | 当天不判定 |
| `graph.baskets` 成员和 `effective_from` / `effective_to` | M6 | 该篮子不判定 |
| `graph.cluster_suggestions` | M6 周聚类 | 没有则路径 A 不跑自动聚类 |
| `ingest.bars_daily` | M1。含 `post_close`、`adj_factor`、`volume` | 该标的当天跳过 |
| `ingest.bars_minute` 的 `pre` | M1。只服务盘前复核 | 该标的不写盘前行 |
| `ingest.macro_observations` | `VIX_CBOE`、`VIX3M_CBOE`、`VIXCLS`、`DGS2`、`DTWEXBGS`、`DCOILWTICO`。可见性用 `realtime_start` | 对应路径 C 或放大特征为 `NULL` |
| `ingest.short_interest` | M1 | 轧空特征 `NULL`，写「未接通」 |
| `ingest.issuer_profiles` | SIC，广域路径 B | 映射不到则 SPY 单因子，沿用 M6 `sector_unmapped` |
| `config/calendar_events.yaml` | 文档点名，仓库里还没有这个文件 | 指数调整日记「未接通」。月度期权到期按第三个周五计算，不编造指数调整日期 |
| 持仓、联动事件 | M4、M8，表都还没有 | 盘前复核范围为空；测试注入合成名单 |

## 4. 输出

只建 `perception` 里的两张表。迁移名 `migrations/phase1_m7_0001_anomalies.sql`。不改别的模块的迁移。

**`perception.anomalies`**

`anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members, direction, max_abs_z, data_quality, coverage, amplification, type_candidates_prelim, status, universe, params_version`

`severity` 是 `alert` 或 `watch`。第 4 节的字段清单没写它，FR-M7-03b/04b 要求它，所以加上。`params_version` 按 README §3.5，每条决策都带。`status` 固定「已发现·原因未明」。`universe` 是 `pool` 或 `wide`。`members` 是 `[{ticker, ret, resid, resid_z, vol_mult}]`。

**`perception.premarket_review`**

`trade_date, ticker, prev_close, premarket_last, premarket_ret, premarket_z, reason, flag, params_version`

`reason` 是 `holding` 或 `linked_event`。`flag` 只在 `|premarket_z| ≥ 3` 时为真。

给 M8 用的是 `alert` 和 `watch` 的池内异常。广域只供回捞。给页面的是这两张表，M7 不渲染。

## 5. 数据接口（Q-M7-8）

检测函数只认识一个读取接口，不自己打开数据库，也不分两套判定。

- `FileMarketView`：读 A 线导出的、不含账号密码的文件。日线和宏观、篮子定义读入后，调用现有 `inves_cog.marketstate.engine.calculate`，在内存里得到和表结构相同的 `daily` / `baskets` / `rotation` / `market`。不写库。
- `DatabaseMarketView`：只 SELECT `marketstate.*`、`graph.baskets`、`ingest.bars_daily`、`ingest.bars_minute`、`ingest.macro_observations`、`ingest.short_interest`。当天 `marketstate` 没有行就不判定。

两条路径返回同样的行。命令行用 `--source file` 或 `--source db` 切换。开发和自测只用 `file`。需求方验收 AC-M7-04、AC-M7-07 时用 `db` 指只读库。B 线不保存连接串。

## 6. 疑问

### 必须停

1. **AC-M7-07 的「每天异常对象」算哪些。** 文档位置：AC-M7-07 和验证报告第 6 节。理解 A：`close` 且 `universe = pool`、合并之后的对象。理解 B：把 `post` 和 `universe = wide` 都算进去。我倾向 A。验证报告写明那次回放没有盘后，对象数 1.5–1.9 也不是广域全市场；把广域算进去会超过每天 2.5 个。这决定验收过不过，所以先停。
2. **`job_runs` 写不进去。** 文档位置：FR-M7-14。`role_perception` 对 `ingest` 只有 SELECT，不能 INSERT `ingest.job_runs`。理解 A：只给 `role_perception` 补这张表的 INSERT，任务名 `anomaly_detect` 和 `premarket_review`。理解 B：运行记录改放到 `perception` 下的新表。我倾向 A，因为文档写的就是现有的 `job_runs`，而且不开放整个 `ingest`。这是权限变更，先停。
3. **轮动单独命中时的 `severity`。** 文档位置：FR-M7-12，对照 FR-M7-03b。理解 A：风格价差 `|z| ≥ 3` 算 `alert`（和路径 C 一样过了 3σ）；只有行业极差 ≥ 4、大盘平静这一条算 `watch`。理解 B：凡是类型候选「主题轮动」一律 `watch`。我倾向 A。这会改变交给 M8 的优先级，先停。

### 已自行决定

答复前不实现上面三条。下面这些按保守做法记在这里，答复后如果要改再改：

- 路径 A、关注级、联动的「同号」按成员原始收益，不用 `same_sign_share`。
- 3 日累积在 M7 里用每日 `resid` 现算，不给 `marketstate` 加列。
- `rsp_spy` 不触发轮动。
- 路径 C 的宏观用水平值之差，不用百分比变化。VIX 的 20% 门槛才是百分比。
- 路径 C 已经命中时，`C_abs` 并进同一条。
- 成员用 `effective_from` / `effective_to`。导出里如果只有当前名单，复跑报告写明「成员按导出日的名单回看」，不改篮子。
- `config/calendar_events.yaml` 不存在时，指数调整特征为 `NULL` 并写「未接通」。月度期权到期用第三个周五。
- `|收益| > 0.30` 且当天 `adj_factor` 变化，视为有拆股或分红记录。
- 合并时方向相反也合并；`direction` 取 `|z|` 最大的那一侧。
- `coverage` 只记有行情的成员数和同号比例，不另造口径。

M6 没有要停下来的问题。`calculate()` 已经能在不写库的情况下产出 M7 要的四张价格结构。

## 7. 规格让位给 Muse

不适用。M7 不是 M3、M4。

## 8. 数据申请

按 B-003：不连共用库。请 A 线导出下面这些文件，不要带账号、密码、连接串。文件先放到本 PR 分支的 `handoff/M7/export/`。四个案例的窗口会抄进 `tests/fixtures/phase1/m7/` 并登记清单；整包导出在合并前从本地和分支删除，status 里写「已删除」。

| 文件 | 表 | 列 | 范围 | 用来做什么 |
|---|---|---|---|---|
| `bars_daily.jsonl` | `ingest.bars_daily` | `ticker, trade_date, open, high, low, close, volume, post_close, adj_factor, source` | 篮子成员里的股票，加上 SPY、QQQ、IWM、RSP、11 只行业 ETF、SMH、IGV、KRE、MTUM、VLUE。日期 2017-01-03 至 2026-10-14 | 内存里跑 M6 `calculate()`；路径 C；四个案例；AC-M7-07 |
| `macro.jsonl` | `ingest.macro_observations` | `series_id, observation_date, value, units, realtime_start` | `VIX_CBOE`、`VIX3M_CBOE`、`VIXCLS`、`DGS2`、`DTWEXBGS`、`DCOILWTICO`，同一日期 | 路径 C、`C_abs`；按 `realtime_start` 做当时可见 |
| `baskets.json` | `graph.baskets` | `basket_id, level, name, benchmark, members` | 全表，成员保留 `effective_from`、`effective_to`、`weight`、`primary` | 篮子成员和基准 |
| `issuer_profiles.jsonl` | `ingest.issuer_profiles` | `ticker, sic` | 日线文件里出现的代码 | 广域路径 B 的行业 ETF；池内复跑也交给 `calculate()` |
| `short_interest.jsonl` | `ingest.short_interest` | `ticker, settlement_date, publish_date, short_interest, avg_daily_volume, days_to_cover, si_pct_shares_outstanding` | 池内代码，`publish_date` 从 2018-01-02 至 2026-10-14 | 轧空特征。没有的行就缺着，不要填 0 |
| `cluster_suggestions.jsonl` | `graph.cluster_suggestions` | 表上的全部列 | 有行才导 | 路径 A 的本周自动聚类。空表就不要文件 |

不要导出 `ingest.info_items`。不要导出分钟线全历史：盘前的 blocking 测试用合成数据，真实盘前按 Q-M7-8 由 A 线在合并后跑。

## 9. 四个案例的冻结窗口

行情来源是上面的 `bars_daily` 导出，不另上下载。窗口按 XNYS、事件日前 130 个交易日到事件日后 25 个交易日。登记方式：抄进 `tests/fixtures/phase1/m7/`，`MANIFEST.sha256` 各加一行，`tests/harness/CHANGELOG.md` 只追加。

| 案例 | 美东日期 | 冻结区间 |
|---|---|---|
| 东芝扩产 → HDD | 2026-10-02 | 2026-03-27 至 2026-11-06 |
| OpenAI（对照 10-08，检测 10-14） | 2026-10-08、2026-10-14 | 2026-04-02 至 2026-11-18（两天合成一段） |
| Meta Muse | 2026-09-21 | 2026-03-16 至 2026-10-26 |
| DeepSeek | 2025-01-27 | 2024-07-19 至 2025-03-04 |

期望仍以 M7 v7 第 7.1 节为准：东芝 10-02 是 HDD 篮子关注级，10-06 不要求单独检出；10-08 没有任何篮子异常；10-14 是 OpenAI 合作方篮子关注级；META 是个股 `alert`，CPU 篮子是关注级；DeepSeek 日有 AI 加速芯片篮子，NVDA 在成员里，方向向下。

## 10. 怎样证明每条验收条款

| AC | 打算怎么证明 |
|---|---|
| AC-M7-01 | 第 7 节 10 个 blocking 测试加 `test_case_detection`。先红后绿。通过后删 `pending.txt` 里这些行。`test_anomaly_live_smoke` 仍留在 pending，原因等待 R5，不进 CI |
| AC-M7-02 | 同一套四个案例再跑一次，输入目录里不放新闻文件。源码扫描确认没有 `info_items`。现场给需求方看两次结果相同 |
| AC-M7-03 | 历史回放用导出文件跑最近 5 个交易日，每条都有层次、篮子、成员、入口、数据质量。调度器那一次真实运行由 A 线在合并后做，不挡合并（Q-M7-7） |
| AC-M7-04 | 需求方抽 5 条，在只读库上用 `--source db` 对 M6 的 `marketstate` 手工核对。B 线不跑这一步 |
| AC-M7-05 | 盘后演示由 A 线在合并后做。东芝不用于本条 |
| AC-M7-06 | 非阻塞。每条异常都有 `amplification`；缺数写原因。合成测试覆盖踩踏、轧空、杠杆被动和缺数 |
| AC-M7-07 | 见下一节 |

## 11. AC-M7-07 复跑

判定方式和验证报告第 3 节相同：事件当天，在它列出的每个范围上有没有检测输出。

- `L1`：当天有 `layer = L1` 的池内异常
- `style`：当天轮动异常的成员里有风格分组
- `sector:<ETF>`：路径 C 或轮动命中这只 ETF
- `basket:<名称>`：某条异常的 `baskets` 含这个篮子
- `stock:<代码>`：某条异常的 `members` 含这个代码

`mild = true` 的 3 条不进查全率（2023-08-02、2023-10-03、2025-06-13）。其余 74 条里，样本外 41 条、样本内 33 条。对照日只有 2026-10-08，这天不得有篮子异常（`alert` 和 `watch` 都没有）。

通过线：非温和事件「至少命中一个范围」的比例，全部 ≥ 85%，其中 `out_of_sample` ≥ 80%。2018-01-02 至 2026-10-14 每个交易日的异常对象数取平均 ≤ 2.5。对象怎么数，等第 6 节第 1 条的答复。

需求方复跑：

```
python -m inves_cog.perception.anomaly.replay \
  --events docs/phase1/golden/m7_events.json \
  --source file \
  --input handoff/M7/export \
  --start 2018-01-02 \
  --end 2026-10-14 \
  --out handoff/M7/ac-m7-07.json
```

只读库上把 `--source file --input ...` 换成 `--source db`。不改 golden。

`ac-m7-07.json` 的字段：

- `events[]`：`date, split, mild, scopes[], hit_scopes[], missed_scopes[], hit_any, anomaly_ids`
- `misses[]`：没达到「至少一个范围」的非温和事件，每条写 `date`、没命中的范围、原因
- `summary`：`recall_non_mild`、`recall_out_of_sample_non_mild`、`control_basket_anomalies`（应为 0）、`mean_objects_per_day`、`n_days`、`object_count_rule`（写明答复后的计数口径）

标准输出同时打这四个数：全部非温和查全率、样本外查全率、对照日篮子异常数、平均每天对象数。
