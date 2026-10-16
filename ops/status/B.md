# B 线回报

> 只由 B 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

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
