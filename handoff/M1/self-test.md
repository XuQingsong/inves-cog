# M1 自测报告

模块：M1；文档：v3（main e7db5a9）；代码提交：c8aa3152d11fec891c0400501831aadc184eaf5b；日期：2026-10-14。

代码和本轮修复已提交；下面分别列出已验证结果与仍缺的验收证据。PR #3 暂为草稿，未合并，未写 milestones。

## 1. Harness

- 原名 14 项 M1 blocking 与 M0 门禁合计 **24 passed，0 failed，0 skipped，7.39 秒**；命令 `PYTHONPATH=src .venv/bin/python -m pytest -q -m phase1_blocking --junitxml=handoff/M1/blocking-v3.xml`，证据 [blocking-v3.xml](blocking-v3.xml)。本机无 Docker；此结果不冒充干净容器 CI。
- 回补日期/25 分钟预算、指定调度任务、历史回补不抑制当日调度，均先独立提交失败断言，再提交实现。既检查历史任务放行，也检查当日已运行任务不重复。
- 原 [database-verification.json](database-verification.json)、[extraction-queue-verification.json](extraction-queue-verification.json) 的真实数据库事务和录音验证继续有效。docs/、golden 和真实 milestones 未修改；M0 变更仍在已授权范围内。
- 两分支联合验证结果见 integration-blocking-v3.xml / integration-replay-v3.xml（生成后附）；临时联合目录不推送。

## 2. 本模块不变量

| 不变量 | 结果与证据 |
|---|---|
| I22 盘后行情 | blocking 绿；常规/半日市/缺交易两面断言；5 日真实常规分钟覆盖见下表 |
| I28 财报反应时间（数据部分） | blocking 绿；索引 Accepted 为权威，缺索引不生成反应日；10 次真实索引核对已完成 |

## 3. pending 和 milestones

14 项 blocking 已移除；原名 `test_ingest_live_smoke` 暂保留。两个 Token Plan 对话模型和 R7 导出均已验证，不再笼统列为等待全部 key。嵌入尚未接通，CompanyIR 实测 403；正式调度证据另行核对。未删除其他模块行，未修改 milestones。

## 4. 逐条验收自评

| 条款 | 自评 | 可复核证据 |
|---|---|---|
| AC-M1-01 | 本地 blocking 通过；最终 CI 单独核对 | blocking-v3.xml；PR #3 Actions |
| AC-M1-02 | 5 日正式回补通过；至少一次准时调度尚待今晚真实触发 | v3-m1-backfill.json，下表；调度器已真实启动，不用冻结时间，不把回补算作按时触发 |
| AC-M1-03 | 实源诊断入选 1,302；正式启动集合等待同一调度器执行 | wide-real-verification.json：13,228 候选/1,302 入选，诊断外层回滚；首次启动例外按 Q-M1-20，不伪造月初快照 |
| AC-M1-04 | 10 条原文显示分钟已逐条核对；5 条真实转载仍未证明 | v3-news-time-proof.json：10/10 落在原文显示分钟内；原网页仅分钟且未显式写时区，按美国站美东解释，限制保留。直接请求原文 403 与网页读取结果不混写。v3-info-maintenance.json：当前新闻库只有一个重复正文组，且是通用财报日历文字，不能冒充五条通讯社转载 |
| AC-M1-05 | 10 次真实索引 Accepted / session / reaction_day 核对已完成 | v3-sec-metadata.json 的 earnings_audit，含官方索引 URL、申报号、原始 JSON 时间和权威 Accepted；59 只 submissions 原始元数据均已入库。原 3 个冲突样例夹具保持不变 |
| AC-M1-06 | 真实断开、其他源继续及恢复演示通过 | v3-source-demo.json：同一 HTTPClient 请求失效域名，两次失败后 Trends 为 degraded；同时 AppStoreFree 真实 100 行、ok；恢复 Trends 8 关键词后 ok。不是 mock 网络故障 |
| AC-M1-07 | 实源存档/计数恒等式和断点回补通过 | news bootstrap 累计 60,509 行；24,038 = 23,199 入库 + 839 去重；R7 27,624 = 27,624 + 0。v3-info-maintenance.json：按现有已测试空正文规则修复 41,967 个旧空正文根，原文/数量不删，备份在仓库外提交范围的忽略缓存 |
| AC-M1-08（非阻塞） | 对话标注真实通过；嵌入未接通，原因已验证 | v3-embedding-check.json：同一 key 为 Token Plan key；Token Plan models 200，未列规定嵌入，嵌入 404；北京和国际站 models / embeddings 均 401。需要开通 text-embedding-v3 的百炼普通 API key。原 10 条嵌入探针因地址未配置在本地失败，不能说成十次网络 401 |

5 个最近完整交易日均经正式 `Pipeline.runtime().run(['bars_full'])`，真实 SystemClock；historical_backfill 的 deadline_met 为 NULL，不假称按时完成。

| 美东交易日 | 日线 | 常规分钟总覆盖 | 最低单标的覆盖 | 真实耗时 | 分页/状态 |
|---|---:|---:|---:|---:|---|
| 2026-10-07 | 73/73 | 99.9684% | 98.9744% | 87.03 秒 | 全部完成 / ok |
| 2026-10-08 | 73/73 | 99.9824% | 98.9744% | 45.04 秒 | 全部完成 / ok |
| 2026-10-09 | 73/73 | 99.9438% | 97.9487% | 24.29 秒 | 全部完成 / ok |
| 2026-10-12 | 73/73 | 99.9368% | 98.7179% | 91.05 秒 | 全部完成 / ok |
| 2026-10-13 | 73/73 | 99.9649% | 98.9744% | 115.84 秒 | 全部完成 / ok |

## 5. 边界与破坏性验证

blocking 保留原名和应拦/应放行双向断言：非普通股/合法股本；缺 ADV/完整 20 日；相同/不同/空正文；401 不重试/5xx 重试；索引缺失/有效 Accepted；回补日期/未来日期；当日旧回补/已完成当日任务。M0 网络、Clock、模型白名单、golden 门禁一起运行；未修改标准答案或放宽门禁。

## 6. 已知限制与已执行答复

Q-M1-17 至 Q-M1-22 已按 v3 实施。全部任务按美东配置；当日 bars_full 20:20 开始、20:45 截止。当前实际启动的调度器选择 bars_full 和 wide_universe，不启动新闻抽取子进程。下一个窗口为北京时间 **2026-10-15 08:20–08:45**；用户已授权 **08:50 一次**自动核对日志/数据库、更新本报告并推送，尚未发生的结果不提前写通过。采集进程不是开机自启服务。

## 7. 新问题与待证事项

没有待答复的 M1 业务问题。阻塞证据仍缺一次真实按时调度及五条真实转载；CompanyIR 和嵌入响应如实记录。原文一分钟核对保留页面精度/时区解释限制，不用合成稿件填充真实转载证据。
