# B 线回报

> 只由 B 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## B-005  已完成  2026-10-16 14:48 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ea089ff`。标题改为「[M7] 提交验收」，已取消草稿。没有合并。没有改 `docs/`、golden、milestones，没有改 M6，没有连接或写入共用库。迁移文件 `migrations/phase1_m7_0001_anomalies.sql` 只在一次性测试库里应用过，共用库留给 A 线在合并后执行。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38863086547 （phase1-blocking，75 passed，9 deselected，31.51s）。本地 `make phase1-test` 同样 75 passed、9 deselected。M7 的 10 个 blocking 测试通过，`test_case_detection` 通过。`test_anomaly_live_smoke` 仍留在 `pending.txt`，等待 R5。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 3.328（2208 个交易日，7349 条）。前三项过线。3.328 高于每天 2.5 的上限。多出来的主要是路径 B 的 4 个百分点分支，约每天 1.3 条只因个股和主 L3 留一收益差达到 4 个百分点、自身涨跌达到 3%。阈值没有下调。
- AC-M7-03：最近 5 个交易日 2026-10-08、10-09、10-12、10-13、10-14 的收盘和盘后清单在 `handoff/M7/ac-m7-03.json`。AC-M7-05：盘后价只从 2026-10-07 起，序列只有 6 个交易日，自身 120 日 z 为空，没有合适的盘后例子，留给 A 线在合并后补。自测逐条写在 `handoff/M7/self-test.md`。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。四个案例窗口留在 `tests/fixtures/phase1/m7/`。
- 已自行决定：无新决定。HDD、CPU、2026-10-14 的收益 z 落在关注级，又和 `|resid_z|≥3` 或路径 B 成员合并，严重级别按规则成为 `alert`，入口仍保留 `A_watch`。这是按冻结阈值改期望，不是改阈值。
- 下一步：无。不合并。不开始下一条。

## B-005  进行中  2026-10-16 13:48 北京

- 测试先红：`8f0f7ed` 提交了失败的 blocking 测试和四个案例窗口夹具。检测代码还没写。

## B-005  已收到  2026-10-16 13:40 北京

- 任务：在 PR #11 上开发 M7。先红后绿。不连库，不执行迁移，不改 M6、`docs/`、golden、milestones，不合并。
- 依据：`origin/main` `344deab`；`ops/control.md` 中 B 为「运行」。M7 v8 已冻结。K01 只计 `close`+`pool` 合并后对象；K02 迁移只授予 `job_runs` 的 INSERT/UPDATE；K03 轮动按答复 A，主题轮动是 `alert`。
- 下一步：读 `data/m7-export` 的 README，先提交失败测试和四个案例夹具。

## B-004  已完成  2026-10-16 13:16 北京

- 草稿 PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ac7c252`。复述在 `handoff/M7/kickoff.md`。没有写实现，没有改 `docs/`、golden、milestones，没有改 M6，没有合并。
- 必须停，等答复后再写代码：
  1. AC-M7-07 每天的异常对象，我倾向只计 `close` 且 `universe = pool`、合并之后的对象。把盘后和广域算进去会超过每天 2.5 个。
  2. `role_perception` 对 `ingest.job_runs` 只有 SELECT。我倾向只给这张表补 INSERT，任务名 `anomaly_detect` 和 `premarket_review`。
  3. 轮动单独命中时的 `severity`。我倾向风格价差 `|z| ≥ 3` 为 `alert`，只有行业极差 ≥ 4 为 `watch`。
- 数据申请（不含凭证，不含新闻；导出放 PR 分支 `handoff/M7/export/`，合并前删除）：
  1. `ingest.bars_daily`：篮子成员加 SPY、QQQ、IWM、RSP、11 只行业 ETF、SMH、IGV、KRE、MTUM、VLUE；列 `ticker, trade_date, open, high, low, close, volume, post_close, adj_factor, source`；2017-01-03 至 2026-10-14。
  2. `ingest.macro_observations`：`VIX_CBOE`、`VIX3M_CBOE`、`VIXCLS`、`DGS2`、`DTWEXBGS`、`DCOILWTICO`；列 `series_id, observation_date, value, units, realtime_start`；同一日期。
  3. `graph.baskets` 全表，成员保留生效区间。
  4. `ingest.issuer_profiles` 的 `ticker, sic`，范围是日线里出现的代码。
  5. `ingest.short_interest`：池内代码，`publish_date` 2018-01-02 至 2026-10-14；缺的不要填 0。
  6. `graph.cluster_suggestions` 有行才导。
- 已自行决定：见复述第 6 节。没有连接工厂或阈值之外的新决定。
- 下一步：停下。不开始实现。

## B-004  已收到  2026-10-16 13:10 北京

- 任务：M7 开工复述。只写 `handoff/M7/kickoff.md`，开草稿 PR，分支 `phase1/m7-anomaly-detection`。提交后停下，不写实现。
- 依据：`origin/main` `4c92710`；`ops/control.md` 中 B 为「运行」。用户已于 2026-10-16 批准开工（G1）。B-003 已通过，PR #8 已合并（`38510bc`）。
- 下一步：读 T07、M7 v7、验证报告、golden 77 个事件，以及 M6 的输出表和 Q-M6-15、Q-M6-18。复述三条路径、数据接口、数据申请和 AC-M7-07 复跑方式。

## B-003  已完成  2026-10-16 12:26 北京

- 已把最新 `origin/main` `b0f5eb1`（含 M3 合并 `9bbf151`）合进 PR #8。head `c144899`。没有合并 PR。
- 冲突只动了三个文件。`pyproject.toml` 依赖取并集，保留 `scipy>=1.14,<2`，其余与 main 相同。`uv lock` 已按这份依赖重算，`uv.lock` 没有变化。`tests/fixtures/phase1/MANIFEST.sha256` 两边条目都保留，Harness `validate_frozen` 通过（162 条，无缺、无多余、无哈希不符）。`tests/harness/CHANGELOG.md` 只追加，M6 `draft.json` 与 M3 `timeline.json` 两行都在。
- blocking：本地 `make phase1-test` 65 passed，7 deselected，1 warning，19.43s，退出码 0。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38850453859 （PR，65 passed / 7 deselected / 22.15s）。push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38850448970 。
- 已自行决定：无。没有改 `docs/`、golden、milestones 里原有内容；main 带进来的文档和 M3 代码原样保留。
- 下一步：无。不开始 M7。

## B-003  已收到  2026-10-16 12:21 北京

- 任务：把最新 `origin/main` 再合进 PR #8。不合并 PR，不改别的文件。
- 依据：`ops/control.md` 中 B 为「运行」。B-003 写明 B-002 第 1–5 项已通过，第 6 项取消。
- 下一步：解决 `pyproject.toml`、`tests/fixtures/phase1/MANIFEST.sha256`、`tests/harness/CHANGELOG.md`，跑 blocking。

## B-002  已完成  2026-10-16 12:21 北京

- 需求方在 B-003 中确认第 1–5 项通过。第 6 项按 Q-M6-20 取消：B 线不写共用库，三天重算改由 A 线在 PR #8 合并后执行。
- 交付仍是 PR #8，head `d5d0587`，CI https://github.com/XuQingsong/inves-cog/actions/runs/38848165567
- 已自行决定：无。

## B-002  阻塞  2026-10-16 11:59 北京

- PR #8，head `d5d0587`。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38848165567 （push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38848160877）。本地 `make phase1-test`：53 passed，6 deselected，1 warning，19.53s，退出码 0。
- 新增测试：`test_l3_same_as_l2_drops_theme_factor`（相同成员 → `m+s`、`l3_same_as_l2`、`beta_t` 为空；不同 → `m+s+t`）、`test_sic_review_additions`、`test_draft_all_does_not_share_one_connection`（复现原来 3 个线程叠在一条连接上，修完后深度为 1；有连接工厂时每个线程一条新连接）。
- 冲突：`src/inves_cog/llm/transport.py` 按任务名分开保留。`segment_mapping_draft` 仍是 `max_tokens=4096`、`reasoning_effort=low`；`graph_seed_draft` 和 `exposure_draft` 仍是 `8192` 和 `low`。模型名没改。分支已合入 `origin/main` `0035c26`。
- 第 6 项：阻塞：等待数据库连接信息。要重算 2026-10-12、13、14 并写入共用库的 `marketstate`。这台环境到不了 Mac 上的 `127.0.0.1:25432`，现有 `inves_cog_review` 又只能读。需要一份能写 `marketstate`、不写 `ingest` / `fundamentals` / `trading` 的连接，放在未跟踪的 `.env`，不提交。
- 已自行决定：无。没有连接工厂时 `draft_all` 改为串行；命令行传入工厂后才并行，每个线程自己的连接。
- 变更：无新表、无新数据源。因子口径和 SIC 映射按已经写进文档的 Q-M6-18、Q-M6-19。
- 下一步：1–5 已在 PR #8，不合并。等连接到位后只做第 6 项，不重做前面的修复。

## B-002  已收到  2026-10-16 11:40 北京

- 任务：M6 合并前修复（PR #8，分支 `phase1/m6-graph-baskets-marketstate`）。不合并 PR。
- 依据：`origin/main` `0f6371f`；`ops/control.md` 中 B 为「运行」。验收报告有条件通过。
- 下一步：合入 main 并解决 `transport.py`；Q-M6-18 先红后绿；补 `sic_to_etf.yaml`；`draft_all` 每线程一条连接；跑 blocking。第 6 项重算共用库需要可写的 `marketstate` 连接，当前只有一份到不了的只读说明。

## B-001  已完成  2026-10-16 11:08 北京

- `make phase1-test`：在 `origin/main` `273be4a` 上退出码 0。**39 passed**，5 deselected，1 warning，**10.66s**。Python 3.11.17。用的是脚本自带的一次性 docker compose 库，没有连生产库。M6 还在 PR #8，不在这条 main 上，所以这 39 个是 M0–M2 的 blocking，不是 M6 的 11 个。
- 复述：B 线做感知和解释，顺序是 M6 验收后的修复、M7、M8。M7 在每个交易日收盘后发现个股、篮子、行业、大盘的异常，对应目标 A1。M8 给每个异常找候选原因、证据和置信度，对应目标 A2、A3。代码只写 `inves_cog.perception`（含 `graph`）和 `inves_cog.marketstate`；`ingest` 只读，例外只有 M6 文档已经授权的采集。不改 A 线的 `trading`、`valuation_v1`，不改 `docs/`、`golden/`、`milestones.txt`，不合并 PR（用户批准后由需求方合并）。必须停的情况：跨模块表结构或接口、golden、规则 A 或交易行为、新数据源或付费、key 或权限、不可逆删改数据，以及仓库里的定时服务和共用库迁移。一次只做信箱里还没「已完成」的最小编号；`ops/control.md` 里 B 为「暂停」就停。
- PR #8 印象（只读，head `acf4856`，分支 `phase1/m6-graph-baskets-marketstate`，没有改）：价格层在 `inves_cog.marketstate`，按留一篮子、含截距、信号日之前 120 日的 SVD 回归算剩余涨跌，轮动和 v5 警戒分开；图谱在 `inves_cog.perception.graph`，原文切片、无引用就丢、审核日志和已确认视图是分开的。schema 在 `migrations/phase1_m6_0001_graph_marketstate.sql`，授权的采集收在 `ingest/market_structure.py`。main 上这两个包仍只有空 `__init__.py`。风险大的地方：`draft_all` 默认 3 个线程共用一条数据库连接；同一 ticker 有多条 L2 时 `active_baskets` 后写覆盖先写；`draft_ticker` 把所有异常收成 degraded，和「没有年报」分不开；STX 单一业务和 SKHY 四季 TTM 写死在图谱服务里；`handoff/M6/` 里多份证据是单行 JSON，diff 不好看。
- 疑问：这台机器没有生产库 URL 和 API key。本次测试不需要，所以没有停。下次要读共用库或跑 live，需要用户把值给我，我放进未跟踪的 `.env`，不提交。文档和 M6 v6 没有要停下来的疑问。
- 用户决策 UD-B-01：用户说每次做完任务后开启定时任务，监控 `ops/inbox/B/` 里还没完成的任务，有就直接开始开发。打算照做，但只作为这个 agent 的唤醒：每 10 分钟看一次信箱（与 A 线 UD-A-01 同一间隔），仍按 README 第 3 节一次只做一条；B 为「暂停」就什么也不做。不在仓库里加定时服务，不改调度代码。复用同一个定时器，不在每次完成时再挂一个。
- 已自行决定：无。
- 下一步：没有下一条信箱任务。不碰 PR #8，等需求方发 B-002。

## B-001  已收到  2026-10-16 11:02 北京

- 任务：入门（搭环境、读文档、复述）。不写业务代码，不开 PR。
- 依据：当时的 `origin/main` `d4afbaa`；`ops/control.md` 中 B 为「运行」。
- 下一步：读任务书 §4、M6 v6、M7 验证报告、M2 验收报告；跑 `make phase1-test`；读 PR #8。
