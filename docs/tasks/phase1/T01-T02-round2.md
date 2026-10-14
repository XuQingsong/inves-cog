# T01 / T02 第二轮：完成 M1、M2 并提交验收

> 交给：正在开发 M1、M2 的 agent。
> 基线：main 最新提交（含 M1 v6、M2 v6、规格 v1.4、阶段任务书 §4.6）。开工前先把 main 合进两个分支。
> 问题清单原文：[`../../phase1/acceptance/M1-M2-review-2026-10-15.md`](../../phase1/acceptance/M1-M2-review-2026-10-15.md)（16 项，每项都附需求方核实的事实）。

## 1. 这一轮要达到什么

M1、M2 都转为正式 PR 并通过验收、合并进 main，第一阶段的数据底座正式关闭。之后才开始 M3、M6。

当前状态（需求方 2026-10-15 核实）：数据收得很准（Muse 对照零差异、行情覆盖约 100%、SEC 时间核对通过），但**信息处理链还没转起来**：6 万条新闻只有 10 条经过 LLM 处理，嵌入不通，一致预期实时采集为 0，官网监控 0 条。另有 5 只美国大盘股在修复版下不能打分。这一轮先解决这些问题。

## 2. 先读：效率规则（阶段任务书 §4.6，从现在起执行）

1. **只有以下情况才停下等答复**：会改跨模块接口或表结构；会改 golden、规则 A 结果或交易行为；需要新数据源、付费、key 或权限；不可逆地删改数据。**其余问题**按最保守、可逆的做法自行决定，写进 `questions.md` 的"已自行决定"一节，继续开发。
2. **单个卡点限时 1 小时**：超时就用如实标注、不阻塞的方式绕过，记进 `handoff/Mx/backlog.md`，回到主线。
3. **精度分级**：只有规则 A 输入、v18 复现、财报反应日、按当时可见口径取数（PIT）要求逐字段精确；只观察的标的和辅助字段，如实标注缺口即可。
4. **先端到端，后打磨**。
5. **每条验收条款只留一份最终证据**，旧版本留在 Git 历史里，删掉 `*-v3`、`*-k16` 这类多版本文件。
6. **批量处理时逐项隔离失败**，一个子项失败不拖垮整个源；偶发失败记 `degraded`，确认不可用才记"未接通"。

## 3. 工作顺序

**第一步：M1（在 `phase1/m1-market-info-ingest` 上）**

| 序 | 清单号 | 做什么 | 完成标准（需求方怎么查） |
|---|---|---|---|
| 1 | #3 | 嵌入改用用户提供的 DashScope key 和 `DASHSCOPE_BASE_URL`。之前填的是 Token Plan 的 key，地址为空（Q-M1-27） | `GET {base}/models` 返回 200；10 条真实条目嵌入成功；然后对全部条目做嵌入，失败率 < 2%（AC-M1-08） |
| 2 | #4 | 官网监控：OpenAI 改用 `https://openai.com/news/rss.xml`；跟随重定向（Google AI 博客已搬家）；按 URL 逐个记健康状态；源名改为 `EntitySites`（Q-M1-25） | 5 个站点各自有健康记录；故意改坏一个 URL，其余 4 个照常入库 |
| 3 | #5 | Trends 按关键词隔离失败；偶发错误记 `degraded`（`signals.py` 的 `collect_trends`） | 测试：一个关键词抛超时，其余关键词照常出结果，源状态为 `degraded` 而不是"未接通" |
| 4 | #6 | 接入美联储和 EIA 的 3 个 RSS：`federalreserve.gov/feeds/press_all.xml`、`eia.gov/rss/press_rss.xml`、`eia.gov/rss/todayinenergy.xml`（Q-M1-26） | 3 个源都有健康记录和入库条目，`source_level = 1` |
| 5 | #7 | `info.py` 两处捕获全部异常后，记录异常类型和信息 | 代码检查 |
| 6 | #16 | `source_root`：没有上游 id、规范化正文少于 300 字符时，哈希用"标题 + 正文"（Q-M1-28） | 两篇 "Earnings Scheduled For October 5 / 12" 不再同根；转载样例仍然同根 |
| 7 | #2 | LLM 用量表 `ingest.llm_calls`，共享客户端写入；`job_runs` 汇总每日 token（FR-M1-17） | 表里每次调用都有任务、模型、输入输出 token、耗时、状态 |
| 8 | #1 | 新闻分级送 LLM（FR-M1-18）：规则 → 批量标题初筛（每 25 条一次）→ 完整处理 → 按需处理；同根只处理一次；积压只补最近 30 天；每日预算 150 万 token | **AC-M1-09**：用最近 7 个交易日的真实新闻跑一遍，报告各层条数、每层 token 和每日总 token；需求方从第 3 层抽 30 条检查漏判；东芝扩产（2026-10-02）和 OpenAI ARR（2026-10-08）的相关新闻必须进入第 2 层 |
| 9 | #14 | 代码规范门禁（清单第 3 节）：`ruff format --check` 和 `ruff check`（E、F、B、W、I，行宽 120，`C901` 上限 25）只查本次 PR 改动的文件；现有超标函数列入豁免清单。授权修改 `pyproject.toml` 和 `tests/harness/` | 故意在一个改动文件里写一行 `a=1;b=2`，CI 变红 |
| 10 | #8 | 一次由调度器按时触发、美东 20:45 前完成的真实运行（AC-M1-02） | `job_runs` 里该次运行的开始、结束时间和状态 |

完成后：`handoff/M1/self-test.md` 按 v6 的 AC 逐条更新（含 AC-M1-09），PR #3 转正式「[M1] 提交验收」。需求方验收通过后，你用 merge commit 合并。

**第二步：M2（M1 合并进 main 之后，在 `phase1/m2-fundamentals` 上）**

| 序 | 清单号 | 做什么 | 完成标准 |
|---|---|---|---|
| 1 | —— | 合入 main。共享文件冲突按规则解决：`pending.txt` 各留本模块的行；CHANGELOG、fixtures MANIFEST 取并集；`pyproject.toml` 依赖取并集；`uv.lock` 用 `uv lock` 重新生成 | CI 转绿 |
| 2 | #9 | `q4_missing` 只看最近 8 个季度、只看打分用到的字段（Q-M2-21） | COST、LRCX 在 `fixed` 下可以打分 |
| 3 | #10 | `fixed` 单季长度改为 80–120 天；`legacy` 不变（Q-M2-22） | COST 的 16 周第四季能识别；90 组 Muse 对照仍然零差异 |
| 4 | #11 | 新增 D9：JPM 营收加 `RevenuesNetOfInterestExpense`；V 取 A 类股的 EPS；XOM 先查申报原件找原因，规则写进 `m2.yaml`（Q-M2-23） | JPM、V、XOM 在 `fixed` 下核心字段非空；差异报告单列 D9 的影响 |
| 5 | #12 | 重跑健康页，核实 49 只 `earnings_event_missing`（Q-M2-24） | 缺失数降到合理范围；仍缺的逐只写原因 |
| 6 | #13 | Yahoo 数据接口 429 时，改从 `finance.yahoo.com/quote/{T}/analysis/` 取同一套字段，优先解析页面里嵌的 JSON，页间隔 ≥ 5 秒，`source` 记 `yahoo_page`（Q-M2-25） | 一次真实采集 59 只全部成功，或逐只写明失败原因；两次成功即满足 AC-M2-06b |

完成后：`handoff/M2/self-test.md` 按 v6 更新，PR #4 转正式「[M2] 提交验收」。

**第三步（M2 验收合并后，建议，不阻塞）**：以 90 组 Muse 对照为保护，拆分 `extract_state`（复杂度 169）和 `parse_segments`（复杂度 167）。

## 4. 不要做

- 不改 `docs/`；
- 不导入、不运行 Muse 或 stock-pm 的代码；
- 不为只观察的标的做文档没要求的深度修复；
- 不用代理、不换一致预期的供应商（Q-M2-25 用的是同一个 Yahoo 的网页）；
- 不伪造快照、转载样本或调度证据。
