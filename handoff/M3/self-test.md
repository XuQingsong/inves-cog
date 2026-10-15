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
| AC-M3-03 | 通过 | kickoff §7 源码位置已登记；Q-M3-10–13 的舍入、真值例外、gate_pass、包路径均实现。technical.py、books.py、rules.py 逐项注释对应固定 aacea04；原始数据库缺项仍为 NULL。 |
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
