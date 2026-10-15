# 下一阶段：M1、M2 收尾，M3、M6 开工

> 交给：正在开发的 agent。日期：2026-10-15。
> 先读：本文；[跟进清单](../../phase1/tracker.md)；[M2 验收报告](../../phase1/acceptance/M2-report.md) 第 6 节。
> 效率规则照旧（阶段任务书 §4.6）。

## 1. 先合并

M2 第三轮复验**通过**（M2 报告第 6 节）。请按顺序：

1. PR #4 合入最新 main，CI 绿后用 merge commit 合并；
2. PR #6 合入新的 main，CI 绿后用 merge commit 合并；
3. 在两个 PR 里各留言：合并提交 sha 和 main 上的 CI 链接。不要改 `milestones.txt`。

需求方的一处更正：上一轮判定"LITE 的净利润算错"是需求方的错误，你重新核对原件的结论是对的（M2 报告 6.1）。

## 2. 上一阶段遗留项（与 M3、M6 并行，按期限完成）

| # | 事项 | 依据 | 期限 |
|---|---|---|---|
| D-17 | **合理性门禁先核对原件**：命中 Q-M2-27 时先与申报原件核对，一致则标 `extreme_value_verified`（不阻止打分），不一致才标 `implausible_value`。LITE、SKHY 应变为 `extreme_value_verified`，LITE 恢复可打分 | M2 v9 Q-M2-32 | M3 提交验收前 |
| D-10 | M1 `test_ingest_live_smoke` 跑通后从 pending 删除 | M0 FR-M0-05 | M1 关闭前 |
| D-11 | 明早（美东 10-15 晚间）的按时调度证据，补进 `handoff/M1/market-bars.json` | AC-M1-02b | 2026-10-16 |
| —— | M2 `test_fundamentals_live_smoke` 跑通后从 pending 删除 | M0 FR-M0-05 | M2 关闭前 |
| D-14 | 嵌入调用的用量记录：`ingest.llm_calls` 的 `model` 只允许两个对话模型，嵌入记不进去。扩充这张表或单独建表 | M1 报告第 4 节 | M8 开工前 |
| D-15 | 一致预期第二次完整采集（59 只） | AC-M2-06b | M5 提交验收前 |
| D-16 | 分部映射的真实草稿（`glm-5.3`） | AC-M2-08 | backlog |

### 2.1 补充：需求方直接核查数据库发现的问题（2026-10-15，只读账号）

| # | 事项 | 需求方核查到的事实 | 要做什么 | 期限 |
|---|---|---|---|---|
| D-21 | **历史财报事件没建** | `ingest.earnings_events` 只有 54 行（每只最新一次，2026-07-16 之后）；而 `ingest.sec_filings` 里 2015 年以来有 2,338 份 8-K Item 2.02 | 按 FR-M1-06 和规格 4.2"每次财报发布一行"，用已有的 `sec_filings` 补齐 2015 年以来的全部财报事件（接收时间以索引页 Accepted 为准，Q-M1-8）。XOM 只有 1 份 8-K 2.02，请查明它用什么方式发布财报 | M3 提交验收前（M3、M4 的财报日规则要用） |
| D-22 | **健康表有过期和演示数据** | `source_health` 里仍有已改名的 `CompanyIR`（未接通）、已接通却仍显示未接通的 `DashScope`，以及演示用的 `EntitySites:https://round2-invalid-site.example.invalid/rss.xml` | 删除或更新这三行；以后的演示只在测试库里做，不写生产库 | 下一次提交前 |
| D-23 | **嵌入的唯一来源** | 生产用 `ingest.info_embeddings` 里的 `text-embedding-async-v1`（1536 维，覆盖 99.4%）；`info_items.embedding` 列还留着 12,331 条旧向量 | 用户已决定先用 async-v1（M1 Q-M1-29）。代码里以 `info_embeddings` 为唯一来源，`info_items.embedding` 标为弃用、不再写入 | M8 开工前 |
| —— | LLM 日用量 | `llm_calls` 显示 10-15 当天对话模型约 333 万 token（实体标注 8,989 次、字段抽取 3,629 次），超过每日 150 万的预算 | 说明这是一次性回补（AC-M1-09 的 7 天回放和 30 天积压）还是日常；日常运行请确认预算逻辑生效 | 下一次提交前 |

## 3. M3 规则 A 打分：开工复述

- 任务卡：[`T03-M3-rule-a-scoring.md`](T03-M3-rule-a-scoring.md)；需求文档：[`M3-rule-a-scoring.md`](../../phase1/M3-rule-a-scoring.md) **v2**。
- 需求方已经准备好的材料，开工复述时直接引用，不需要再找：
  - **v18 冻结输入**：`docs/phase1/golden/v18/`（Nasdaq 拆股调整价、CBOE VIX、标准答案）。需求方用 Muse 源码在这套输入上重跑 v18，**90 笔交易与标准答案逐笔一致**（M4 Q-M4-5）；
  - **Muse 逐日打分对照**：`golden/v18/scores_20days.json.gz`（20 个信号日 × 30 只，含四本账、红线、层级、入场判定，Q-M3-8）；
  - 和 M2 对齐的 6 条决定：健康码从 `state_asof` 读（Q-M3-4）；`legacy` 只执行 M-07 和 M-08（Q-M3-5）；空字段按 M-11 重配权（Q-M3-6）；用拆股调整价（Q-M3-7）；不依赖一致预期（FR-M3-12）。
- 复述单仍要按任务卡列出"以 Muse 源码为准"的全部计算细节，附源码位置。

## 4. M6 图谱、篮子与价格结构：开工复述

- 任务卡：[`T06-M6-graph-baskets-marketstate.md`](T06-M6-graph-baskets-marketstate.md)；需求文档：[`M6-graph-baskets-marketstate.md`](../../phase1/M6-graph-baskets-marketstate.md) **v5**。
- 先读需求方的验证报告 [`validation/M7-validation-report.md`](../../phase1/validation/M7-validation-report.md)，它解释了 M6 v5 为什么这样改。
- v3 至 v5 的要点：
  - 收益率用拆股调整价（Q-M6-4）；
  - **授权在 `inves_cog.ingest` 里新增的采集**（M1 已关闭，这是唯一的例外）：CBOE 的 VIX 和 VIX3M 日线（Q-M6-5、FR-M6-16）、`ingest.issuer_profiles`（SIC，Q-M6-6）、ETF 日线 XLB、XLRE、XLC、RSP、KRE、MTUM、VLUE（FR-M6-16）；
  - 10-K 原文取到 `graph.source_texts`（Q-M6-7）；
  - 资金流向图 `marketstate.rotation`（FR-M6-16）；
  - 新的警戒规则和 VIX 期限倒挂（FR-M6-14 v5），`golden/m6_marketstate.json` 已按 v5 重新生成，共 11 个用例。
- AC-M6-04 需要用户按篮子做一轮图谱审核，复述单里写明审核工具的形式，以及每个篮子大约有多少条候选。

## 5. 开工复述的写法（按 §4.6 精简）

- 两份复述单分别写在 `handoff/M3/kickoff.md` 和 `handoff/M6/kickoff.md`，各开一个草稿 PR（分支 `phase1/m3-rule-a-scoring`、`phase1/m6-graph-baskets-marketstate`）。
- 疑问分两级。只有"必须停"的列在"待答复"里：跨模块接口、golden、规则 A 结果、新数据源或付费、权限。其余写在"已自行决定"里，写明你的做法，需求方答复时一并确认。
- 提交复述单后停下等答复。

## 6. 不要做

- 不改 `docs/`；
- 不导入、不运行 Muse 或 stock-pm 的代码（v18 的输入和对照答案已经在 golden 里）；
- 不开始 M7：M7 v6 已定稿，等 M6 通过后再开工。
