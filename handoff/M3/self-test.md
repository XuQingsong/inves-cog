# M3 自测报告

模块：M3；冻结文档：v3（be2137e）；验收基线：main 3d7db6980c7898139a13c17636dcdbb761eb752c；日期：2026-10-16。实现提交见本文件所在 PR 的提交历史。

## 1. Harness 与先红后绿

先提交 `ed2db5e` 的 13 个失败测试及冻结输入，之后实现。D-17、D-21、继任 CIK、M2 live 所需修复及证据已移入独立 PR #9（phase1/m2-closeout），本 PR 的最终差异不包含 M1/M2 实现或测试。保留原先失败测试、后实现的提交顺序，不重写已发布历史。原名 13 个测试均存在：12 blocking、1 replay。

- 全仓 `pytest -m phase1_blocking`：51 passed、6 deselected，9.95 秒；[blocking.xml](blocking.xml)。
- M3 全部 13 项：13 passed，7.25 秒；[replay.xml](replay.xml)。
- `test_scores_match_muse`：20 日 × 30 只 × 27 字段 = 16,200 项比较，零差异；独立输入适配器校验冻结 companyfacts SHA，未导入或执行 Muse。
- cases 当前尚无测试：输出 `NO TESTS COLLECTED — pending: 3`，不记为通过；[cases.xml](cases.xml)。
- Ruff 按 Harness 的改动文件范围检查，保留已有具名复杂度例外；未改其他模块的样式基线。

## 2. 不变量

I02（只允许 A）、I03（v18 常量）、I04（无 tracker 固定止损）、I08（过期账本清空）、I09（拆股疑似只清空估值）、I13（财报 PIT）均在本模块原名测试中正反覆盖并通过。时钟、网络、包防火墙、模型白名单等 M0 门禁同时全绿。

## 3. pending / milestones

M3 的 13 行在测试实际通过后删除；其他模块的行保留。`milestones.txt` 未修改。M2 的 live pending 行已由获验收的 PR #9 从 main 删除；本 PR 对 pending 的最终差异仍仅删除 M3 的 13 行。

## 4. 验收条款

| 条款 | 自评 | 证据 |
|---|---|---|
| AC-M3-01 | 通过 | 12 blocking 全绿；合成三例、全部插值断点/中点/越界均经 load_golden 读取并命中。 |
| AC-M3-02 | 通过 | 600 行、16,200 项零差异，`tests/m3/replay_support.py`、replay.xml；滚动状态从初始财报逐日推进，不仅计算抽样日。 |
| AC-M3-03 | 通过（A-002 补齐） | kickoff §7 全部 21 条按原顺序对应下表；原有 5 处注释保留，分散实现均补充固定 aacea04 的文件和行号。只读源码作参照，没有运行或导入 Muse。注释以外的 Python token 和 AST 与修复前完全一致，见 [a002-comment-only.json](a002-comment-only.json)。 |

以下代码路径除另注外均相对 `src/inves_cog/trading/scoring/`；每处注释中的 Muse 源码固定为 `aacea04e4562f70854d69330fe724aa2799f2858`、`code/` 下相应文件。序号严格对应 kickoff §7，M2/M4 的归属项只在 M3 消费入口或边界注明，不新增实现。

| 细节（kickoff §7 顺序） | 本项目代码位置（文件:函数或常量） |
|---|---|
| 1. 财报初始状态与生效 | `__init__.py:score_day`（逐信号日查询 M2 PIT）；`books.py:derivatives`（重算价格派生）；`tests/m3/replay_support.py:states_for`（2025-12-31 初始状态和 filed 日期）。 |
| 2. MA 与动量 | `technical.py:technical_series`（完整均线窗口及 shift(20/63/126)）。 |
| 3. RSI | `technical.py:technical_series`（14 日涨跌均值与 RSI 输出，保留既有注释）。 |
| 4. 量能 | `technical.py:technical_series`（20/60 日量比，close>=open，60 日上涨量占比）。 |
| 5. 波动与回撤 | `technical.py:technical_series`（vol20/vol60、252 日回撤）；`__init__.py:score_fields`（分层使用 vol60 回退 vol20）。 |
| 6. 当前价格派生 | `books.py:derivatives`（正 EPS 的 PE、当日市值、PS、FCF 收益率和 PEG，覆盖旧价格派生）。 |
| 7. FCF/净利润、EPS 增速 | `__init__.py:score_day`（消费 M2 状态）；`books.py:WEIGHTS`、`books.py:build_books`（消费负 NI 仍有效的 FCF/NI、正 TTM EPS 的增速合同；提取仍归 M2）。 |
| 8. 插值和端点 | `curves.py:finite`、`interp`、`weighted_book`（有限值、端点、有效 0、重配权与账本 round(1)，保留既有注释）。 |
| 9. 账本曲线及权重 | `curves.py:CURVES`；`books.py:WEIGHTS`、`build_books`（三本账曲线及固定权重）。 |
| 10. 时机内层 | `curves.py:mean_available`；`books.py:TIMING`、`build_books`（组内等权后再用五组权重；Q-M3-6 缺项重配）。 |
| 11. 过期/拆股 | `books.py:split_suspect`；`__init__.py:score_fields`（严格 >180 天清三账，拆股疑似只清估值；fixed 消费 M2 健康码）。 |
| 12. 红线、排名 | `rules.py:EXCLUDED`、`red_lines`（严格比较、M-16/17 标签与 M-18）；`__init__.py:score_fields`（固定排名权重和 round(1)）；原真值兼容注释保留。 |
| 13. 分层优先级 | `rules.py:assign_tier`（质量/成长缺项、先进攻再防守、NI/FCF 双负，保留估值 0 的兼容注释）；`__init__.py:score_fields`（波动输入）。 |
| 14. 分层重估 | `__init__.py:score_fields`（新 filed 状态或层级空才重估，保留沿用层级的既有注释）；`repository.py:Repository.previous`、`service.py:ScoringService.run`（保存和接续层级状态）。 |
| 15. 确定性 | `rules.py:certainty`（加减点、缺失不加减及 4/2 分界）。 |
| 16. 持有资格 | `rules.py:HOLD`、`holding`（满分 90、不归一化、六项缺项保底及 hold_ok>=55）。 |
| 17. fund_bad 与跑道 | `rules.py:holding`（资格分/三项衰退组合、FCF 缺失或非负、负 FCF 的一年现金跑道）。 |
| 18. 入场与 M-31/32 | `rules.py:ENTRY`、`entry_rules`（三层门槛、M-31 上限 65 且不改原账、M-32 增速/现金要求及 M-18 归 M4）。 |
| 19. 连续过线状态 | `__init__.py:score_fields`、`score_history`（MA200 历史门禁、逐日累加/归零）；`repository.py:Repository.previous`、`service.py:ScoringService.run`（跨任务接续）；`tests/m3/replay_support.py:compare_frozen`（完整 2026 日序推进后抽取 20 日）。 |
| 20. VIX 分位方法（归属边界） | `service.py:ScoringService.run`（注明 Muse 含当日 252 日、min_periods=120 的 90% 线性分位归 M4；M3 不实现，也不替换为 M6 的前一日百分位秩）。 |
| 21. 常量的权威位置 | `rules.py:ENTRY`、`load_rule_a`（以 v18 执行常量验证门槛、cap、首笔、预算、buffer 和只数，M4 后续消费）。 |

A-002 回归：blocking **51 passed、0 skipped**（11.51 秒）；replay **2 passed、0 skipped**（14.38 秒），其中 `test_scores_match_muse` 对比 **600 行、16,200 字段，零差异**。证据：[a002-blocking.xml](a002-blocking.xml)、[a002-replay.xml](a002-replay.xml)、[a002-replay-diff.json](a002-replay-diff.json)。首轮执行沙箱禁止 AF_UNIX 本地通信，原始失败保存在 [a002-blocking-sandbox.xml](a002-blocking-sandbox.xml)；以正常本机权限复跑同一离线测试集后全绿，未改测试或门禁。Ruff 通过。修复仅补注释及本对照，不改变计算、常量、断言、夹具或标准答案。

| 条款 | 自评 | 证据 |
|---|---|---|
| AC-M3-04 | 通过 | real-comparison.json 与 real-scores.json；下表。 |
| AC-M3-05 | 通过 | daily-task.json 中 2026-10-14 fixed 为 59 行，空质量账本均有原因；2026-10-09 两套提取器各 59 行；JSON 保留 null。任务覆盖对无行情单独记录 no_bar，不填造分数。 |

2026-10-09，顺序为质量 / 成长 / 估值 / 时机：

| 股票 | 本项目 legacy | 规格现算 | 最大绝对差 |
|---|---|---|---|
| AMD | 74.5 / 86.9 / 11.8 / 72.8 | 74.5 / 86.9 / 11.8 / 72.8 | 0 |
| ANET | 92.3 / 81.0 / 28.3 / 73.2 | 92.3 / 81.0 / 28.3 / 73.2 | 0 |
| VRT | 81.1 / 94.6 / 38.6 / 42.7 | 81.1 / 94.6 / 38.6 / 42.7 | 0 |
| GEV | 70.2 / 88.0 / 41.4 / 63.5 | 70.2 / 88.0 / 41.4 / 63.5 | 0 |
| ETN | 51.8 / 72.1 / 36.3 / 71.3 | 51.8 / 72.1 / 36.3 / 71.3 | 0 |
| CEG | 25.5 / 57.0 / 48.7 / 48.5 | 25.6 / 57.0 / 48.7 / 48.5 | 0.1 |

fixed 独立结果：LITE 52.0 / 96.0 / 13.0 / 69.6；BE 81.7 / 92.4 / 11.2 / 71.2；COHR 34.1 / 84.0 / 17.0 / 65.6。每项容差均未放宽。

## 5. 反例与权限

原名测试包含：180/181 天；真实 0 与缺失；阈值等于与刚越过；A 与其他规则；未来财报不能提前生效；本土/外国。证据为 blocking.xml 及先红提交的 red-tests.xml；原件核验和继任 CIK 的回归归入 PR #9。

`daily-task.json`：通过现有 `role_trading` 成功写 daily_scores，写 fundamentals 的权限为 false。任务运行和健康记录通过独立 ingest 连接持久化；没有新建账号或扩大权限。真实任务是显式运行，不当作 M1 的准时调度证据。

## 6. 上游收尾依赖

D-17 / D-21、继任 CIK 和 M2 live 由 [PR #9](https://github.com/XuQingsong/inves-cog/pull/9) 独立验收通过（M2 报告第 7 节），已用 merge commit 合并，SHA 为 3d7db6980c7898139a13c17636dcdbb761eb752c。M3 已合入该 main 并重新运行 51 项 blocking 及全部 13 项打分测试；最终差异不包含 M1/M2 实现、测试或其 pending 删除。M3 按本次用户指令重新正式提交验收。

## 7. 已知限制与待办

M2 live 已独立验收通过；M1 的 live 关闭及北京时间 2026-10-16 早晨准时调度仍按独立证据跟进，未提前标绿。M3 不产生订单、不读取持仓。Q-M3-11 真值兼容例外只存在于规则判定，数据库没有假 0。没有需暂停的新增规则问题；没有修改 docs、golden 或 milestones。
