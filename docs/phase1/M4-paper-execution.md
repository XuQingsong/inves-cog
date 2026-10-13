# M4 纸面执行与 v18 复现

| 项 | 内容 |
|---|---|
| 文档版本 | v1 |
| 规格章节 | 9.1、9.8（M-34 起）–9.15、11.2（读取部分）、12.5、16.6 |
| 依赖 | M3（`daily_scores`）；覆盖层标记来自 M9（M9 完成前用夹具） |
| 关闭的不变量 | I05、I06、I07、I14、I15、I16 |
| 规模 | 中到大（设中期检查点） |

## 1. 目标

在本项目里重写规则 A 的交易部分，跑出与 Muse v18 一致的回放结果，并在 59 只池子上每天生成纸面盘前计划：每一笔买、卖，每一个"不买、不卖"，都有规则编号和理由。

对应需求："买卖先按现有回测里那套规则走"；"交易包含风险控制、仓位管理、止损和止盈"；"用户要看得见系统在做什么"。

## 2. 范围

**做**：新开仓候选（M-34）、首笔（M-35、M-36、M-37）、加仓（M-40）、卖出及优先级（M-50 至 M-58）、波段层（M-60 起）、组合风控（M-61、M-62、M-63）、成交与成本、纸面账本、订单理由、盘前计划、覆盖层读取（冷静期跳过、撤单）、按当日成员的池子、v18 回放、停机条件。

**不做**：A+ 规则；估值进仓位；S10；任何影子信号（M9）；页面渲染（M10，本模块只出 JSON）；扩池基线回测（第二阶段）。

**边界澄清**：

- **成交时序**：信号日收盘后生成信号 → 北京时间 20:00 读覆盖层、生成盘前计划 → 下一交易日开盘价成交。"撤单"指从当日计划中移除被覆盖层冷静期挡住的买单，并记录为撤单。
- **额度检查用信号日收盘权益，成交金额用次日开盘权益**（M-35 原文）。
- 覆盖层只能让计划**更少**：删除买单或减小买单数量。M4 读取覆盖层时，任何"增加"的请求都必须被忽略并记错误（I24 的执行侧保护）。
- 计划里只记录"考虑过、但没做"的事项（见第 4 节 `skips` 的范围），不为池子里每一只不过线的股票写跳过记录；那些股票的状态在标的总表里（M10）。
- 订单数量是否允许小数股、成交价如何取整，以 v18 标准答案 `trades.jsonl` 为准。

## 3. 输入

| 输入 | 来源 |
|---|---|
| 打分快照 | M3 `trading.daily_scores` |
| 开盘价、SPY、VIX | M1、FRED |
| 覆盖层标记 | `overlay.current(trade_date)`：`{ticker: {cooling_off, version, event_ids}}`；M9 完成前用 `tests/fixtures/phase1/overlay/*.json` |
| 池子成员 | `config/universe.yaml` + 上市日期（I14） |
| v18 标准答案 | Muse `aacea04`：`summary.json`、`trades.jsonl`、`inputs/` |

## 4. 输出

**`trading.ledger`**：现金、持仓、成本、层级、已投比例、减仓阶段、波段股数、上次卖出日期、退出类型。

**`trading.orders`**：`order_id, signal_date, trade_date, ticker, side, kind(open/add/swing_buy/swing_sell/reduce/exit), qty, fill_price, cost, rule_ids text[], reason_zh, tier, rule_set, params_version, overlay_version`

**`trading.plan`**（盘前计划 JSON，M10 渲染）：

```
{
  "trade_date", "signal_date", "rule_set": "A", "params_version",
  "overlay": {"version": str|null, "status": "ok|missing|stale"},
  "data_coverage": {"tradable": int, "with_bars": int, "pct": float},
  "published": bool, "unpublished_reason": str|null,
  "orders":  [{"ticker","side","kind","qty","notional_est","rule_ids":[],"reason_zh","tier"}],
  "cancels": [{"ticker","original_order","n_code":"N5","overlay_event_ids":[],"reason_zh"}],
  "skips":   [{"ticker","n_code","rule_ids":[],"reason_zh"}],
  "holdings":[{"ticker","qty","tier","status","n_code"|null,"reason_zh"}],
  "portfolio": {"equity","invested_pct","tier_usage":{},"holdings_count","gates":{"panic","black_swan","drawdown_brake"}}
}
```

`skips` 只包括四类：`entry_pass` 为真但没有下单的（N7 组合约束、N5 冷静期）；被 M-18 挡住的（N4）；被冷却期挡住的（M-58）；持仓满足加仓条件以外的其他条件、但因额度或闸门没有加仓的（N7）。

**N 代码**（规格第 12.5 节）在本模块使用 N3、N4、N5、N7、N8；N1、N2、N6 由 M8 在处置卡上使用；N9 由 M9 提供。

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M4-01 | M-34 候选（主候选、回补候选、进攻层优先、逐个检查名额和闸门） |
| FR-M4-02 | M-35 首笔比例、M-36 内部人加成（Form 4 按申报日，90 个自然日）、M-37 追高减半；额度检查与成交金额的权益口径按第 2 节 |
| FR-M4-03 | M-40 分级加仓（确认加仓、确认补满） |
| FR-M4-04 | 卖出 M-50 至 M-57，按规格第 9.10 节的优先级，命中一条后当天不再检查后面的；M-58 冷却期；M-59 "只观察不卖" |
| FR-M4-05 | 波段层：弱势带、核心仓波段、观察名单波段（含深跌两次确认）、止盈止损、转核心仓 |
| FR-M4-06 | M-61 黑天鹅、M-62 回撤刹车、M-63 VIX 恐慌闸门；闸门对哪些规则生效按规格 |
| FR-M4-07 | 成交：次日开盘价；先卖后买；成本 0.1%；成交金额低于权益 0.5% 不下单（I07） |
| FR-M4-08 | 订单理由：`rule_ids` 只含 `M-` 编号；`reason_zh` 为中文，格式"`M-xx` + 一句话"，不得含"悲观 / 中性 / 乐观 / 目标价 / p= / 估值区间"（I05） |
| FR-M4-09 | 订单只能由 `trading.engine` 写入；其他模块没有写 `trading.orders` 的接口和权限（I06） |
| FR-M4-10 | 池子成员按当日：上市日期之前不存在（I14） |
| FR-M4-11 | 覆盖层读取：`cooling_off = true` → 不生成该股新买和加仓，写 `skips`（N5）；当日计划中已有该股买单 → 移到 `cancels`；覆盖层缺失或 `generated_at` 早于当日 18:00（北京）→ `overlay.status = missing / stale`，照常生成 |
| FR-M4-12 | 停机条件：可交易股票行情覆盖率 < 95% → `published = false`，写缺失清单，不生成订单 |
| FR-M4-13 | 纸面任务写死 `rule_set = 'A'`；纸面运行用 `fixed` 提取器的打分，v18 回放用 `legacy` |
| FR-M4-14 | v18 回放入口：吃冻结输入，输出交易清单和摘要，与标准答案对比，生成逐笔差异报告 |
| FR-M4-15 | 每日运行写 `job_runs`；计划 JSON 在北京 20:30 前发布 |

## 6. 异常与降级

| 情况 | 行为 |
|---|---|
| 行情覆盖率 < 95% | 不发布计划（FR-M4-12） |
| VIX 缺失 | 当日视为非恐慌日，计划上标注"VIX 缺失"；不得把缺失当成恐慌日 |
| 覆盖层缺失 | 照常运行并标注 |
| 某只打分为空 | 不能买；已持有的按卖出规则中不依赖该账本的条款运行（例如破位减仓），依赖空账本的条款（例如 M-50 质量线）当日不判定，并在 `holdings.status` 写明 |

## 7. Harness 与自测

| 测试名 | 标记 | 断言 | 夹具 |
|---|---|---|---|
| `test_order_reason_tokens` | blocking | I05 | 合成订单 |
| `test_orders_only_from_engine` | blocking | I06：除 `trading.engine` 外没有代码路径写订单；迁移脚本中只有 `role_trading` 有写权限 | 源码扫描 + 迁移 |
| `test_fill_timing_and_cost` | blocking | I07 | 合成 |
| `test_membership_asof` | blocking | I14 | 合成 |
| `test_sell_priority` | blocking | 同一天同时满足 M-50 和 M-55 → 只执行 M-50 | 合成 |
| `test_panic_gate_scope` | blocking | 恐慌日不生成 M-55、M-56、M-61 减仓、M-62 −8% 减仓；M-50、M-51、波段止盈止损照常 | 合成 |
| `test_cooldown_m58` | blocking | 卖出后 10 个交易日内不加仓、不新开 | 合成 |
| `test_overlay_cooling_skip_and_cancel` | blocking | 冷静期 → 跳过（N5）；已有买单 → 撤单；覆盖层要求"增加"时被忽略并报错 | `overlay/*.json` |
| `test_overlay_missing_marked` | blocking | 缺失 / 过期时标注并照常运行 | 合成 |
| `test_plan_unpublished_low_coverage` | blocking | 覆盖率 94% → 不发布 | 合成 |
| `test_plan_json_contract` | blocking | 计划 JSON 字段齐全；`rule_set = "A"`；`skips` 只含第 4 节四类 | 合成 |
| `test_vix_missing_not_panic` | blocking | VIX 缺失不当成恐慌日 | 合成 |
| `test_v18_replay` | replay | I15 | v18 标准答案 + 冻结输入 |
| `test_amd_entry_2026_01_12` | replay | I16 | 同上 |
| `test_paper_live_smoke` | live | 真实跑一天：计划已发布，字段齐全 | 真实 |

**中期检查点**：v18 回放的前 3 个月（2026-01-02 至 2026-03-31）交易清单与标准答案的逐笔对比。

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应需求 | 阻塞 |
|---|---|---|---|---|
| AC-M4-01 | 第 7 节 blocking 测试全绿 | H | FR-M4-01–15 | 是 |
| AC-M4-02 | `test_v18_replay`：收益 +49.45% ± 1 个百分点，最大回撤 −12.64% ± 0.5 个百分点，交易清单匹配率 ≥ 95% | H | "先按现有回测规则走" | 是 |
| AC-M4-03 | 差异报告：每一笔不匹配都有解释，解释只能是三类之一：浮点 / 数据版本 / 已登记的 Muse 源码细节；出现第四类即不通过 | E | 同上 | 是 |
| AC-M4-04 | `test_amd_entry_2026_01_12` 全绿 | H | 高 PE 成长股在规则 A 下有过买入 | 是 |
| AC-M4-05 | 连续 5 个交易日真实运行：每天北京 20:30 前发布计划；每一笔订单、撤单、跳过、持仓状态都有规则编号或 N 代码和中文理由 | E | 用户看得见系统在做什么 | 是 |
| AC-M4-06 | 需求方抽 3 天计划，逐笔用规格第 9 节手工复核（每天至少 2 个动作或跳过），结论一致 | E | 交易可解释 | 是 |
| AC-M4-07 | 用夹具演示：某只股票被设为冷静期 → 当日买单进入 `cancels`，次日无成交 | D | 接刀漏洞修补 | 是 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M4-1 | 计划里要不要列出每只不过线的股票？ | 不要。只列"考虑过但没做"的四类；其余在标的总表 |
| Q-M4-2 | VIX 缺失算不算恐慌日？ | 不算，并在计划上标注 |
| Q-M4-3 | 59 只池子的回测基线（A5）做不做？ | 第一阶段不做，放第二阶段 |
| Q-M4-4 | 订单是否允许小数股？ | 不允许。v18 标准答案的持仓均为整数股（例如期末 NVDA 731 股、AMD 75 股）；取整方式以 Muse 源码为准，开工复述时确认 |
