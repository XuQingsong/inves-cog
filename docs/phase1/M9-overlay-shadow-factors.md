# M9 覆盖层、影子信号与因子候选池

| 项 | 内容 |
|---|---|
| 文档版本 | v1 |
| 规格章节 | 11.1–11.4、13.7、10.3（F-01、F-02、F-06 的定义）、10.4（S10 的资格条件） |
| 依赖 | M8（联动事件、标签）、M4（打分快照、持仓、计划，只读）、M5（估值影子）、M6（`marketstate`）、M2 |
| 关闭的不变量 | I24、I32、I35 |
| 规模 | 中 |

## 1. 目标

把模块一的结论以**只收紧**的方式交给交易：冷静期和撤单。其余所有"模块一应该怎样影响交易"的想法（基本面恶化减仓、核查期减半、高 PE 成长股的买入路径、按波动定仓位、系统性冲击下的止损复核……）都在这里每天算出"如果生效会怎样"，只记录、不下单，为第二阶段攒证据。

对应需求："情绪和资金变得太快，不能让它们直接驱动交易"；"高成长、高 PE 的股票必须有买得进去的路径"（第一阶段以影子因子的形式持续迭代）；"不断复盘，改善交易，扩充交易因子"；"用战争、关税、疫情这类指标再评一次止损"（第一阶段影子）。

## 2. 范围

**做**：覆盖层的生成与投递；影子信号 X1–X4；因子候选池登记表和 F-01–F-08 的每日影子值；单因子替换后的"是否过线"判定（N9）；F-02 的持有滞回影子状态；S10 资格的影子判定（含系统性事件标签）。

**不做**：任何订单；A+ 规则的完整组合模拟（第二阶段）；影子结果的后续收益统计（M10 的周报和月报）。

**边界澄清**：

- **冷静期与方向无关**：直接暴露的利好事件也会触发冷静期（"不追"），见 Q-M9-1。
- "单因子替换后是否过线"只替换一个账本或一个参数，**其他条件全部沿用规则 A 当日的结果**，不模拟持仓、名额、额度的连锁变化。这样做的含义是"差在哪一项"，不是"A+ 会怎么交易"。
- 影子写入 `perception_shadow` 和 `factor_shadow`；交易角色对这两个 schema 没有任何权限（I32、I35）。

## 3. 输入

| 输入 | 来源 |
|---|---|
| 联动事件、生命周期、暴露、机制、方向、背离标签、系统性事件标签 | M8 |
| 打分快照、持仓、计划 | M4 `trading.daily_scores`、`trading.ledger`、`trading.plan`（只读） |
| 估值影子 V-T1 / V-T2 | M5 `valuation_v1.shadow_rules` |
| `marketstate` | M6 |
| 财报、分部、一致预期衍生指标 | M2 |

## 4. 输出

- `overlay.versions`：规格第 11.1 节的 JSON，每次生成一个版本；HTTP `GET /api/linkage/overlay?date=YYYY-MM-DD`；文件 `event_overlay_YYYY-MM-DD.json`。
- `perception_shadow.signals`：`date, signal(X1–X4), ticker, event_id, condition_detail jsonb, shadow_action, rule_a_action, params_version`。
- `factor_shadow.registry`：`factor_id, version, definition, inputs, pit_note, target(哪本账 / 哪条规则), rationale, source, expected_direction, status(登记 / 影子计算 / 回测 / 前向影子 / 生效 / 退役), created_at`。
- `factor_shadow.daily`：`date, ticker, factor_id, version, value, substituted_value, would_pass(bool), rule_a_entry_pass, gap_detail jsonb`。
- `factor_shadow.f02_state`：持有滞回状态机的每日状态。

## 5. 功能需求

### 5.1 覆盖层

| 编号 | 需求 |
|---|---|
| FR-M9-01 | `cooling_off = true` 的条件：标的在某联动事件的影响范围内，暴露为"直接"，机制不是估值倍数，且该事件处于"市场确认"或"基本面核查中"；或该事件为"已验证·有影响"且方向不利，直到该标的下一份 10-Q / 10-K 生效 |
| FR-M9-02 | "已衰减·无影响""已证伪"、到期转"条件风险"、"已验证·有影响"且方向有利 → `cooling_off = false` |
| FR-M9-03 | `first_lot_multiplier` 恒为 1.0；`stop_review_eligible` 恒为 `false`；`divergence_tag` 照抄 M8；`reason` 为中文，含事件 id |
| FR-M9-04 | 每个交易日北京 20:00 读取盘前复核后生成，20:30 前发布；版本号递增；HTTP 和文件两路都可读 |
| FR-M9-05 | 覆盖层只能删除买单或减小数量（I24）：生成器没有"增加"字段；M4 侧的保护见 M4 FR-M4-11 |

### 5.2 影子信号

| 编号 | 需求 |
|---|---|
| FR-M9-06 | X1：持仓 ∧ 事件"已验证·有影响"且方向不利 ∧ 暴露直接 ∧ 当年 EPS 共识较事件建立日 ≤ −5% ∧ 收盘 < 50 日线 → 影子动作"减 1/3"；同一持仓同一事件只记一次 |
| FR-M9-07 | X2：事件"基本面核查中" ∧ 暴露直接 ∧ 当日计划里有该股的开仓单 → 影子动作"首笔 × 0.5"（即使已被冷静期挡住也记录） |
| FR-M9-08 | X3：每一笔规则 A 的观察名单波段买入，记录当时是否有"情绪性折价"标签；有标签且满足观察名单波段资格、但规则 A 没买的，也记录 |
| FR-M9-09 | X4：一致预期快照满两个季度（2027-04-08）之前，只记录 F2 的修订值，状态"快照不足"；之后按 F-03 的定义计算 |

### 5.3 因子候选池

| 编号 | 需求 |
|---|---|
| FR-M9-10 | 登记表初始化 F-01–F-08（规格第 13.7 节），状态"影子计算"；改定义必须新增版本，旧版本的每日记录保留 |
| FR-M9-11 | F-01 成长调整估值分：按规格第 10.3 节 B1；有效估值分 = min(65, max(原估值分, F-01))，原估值分 > 65 时保留原值；适用条件不满足时 `value = NULL`；替换：把规则 A 的估值账（含 M-31）换成有效估值分，重算该股当日 M-33。`golden/m9_factor_shadow.json` 的 `f01_growth_adjusted_valuation` 全部命中 |
| FR-M9-12 | F-02 拐点质量分：按 B2；有效质量分 = max(原质量分, min(60, F-02))；替换：质量账换成有效质量分，重算 M-33。持有滞回影子：对规则 A 的持仓按 `f02_hysteresis` 的状态机逐日记录"若 B2 生效，今天会怎样" |
| FR-M9-13 | F-03 一致预期修订：成长与预期账加一项"当年 EPS 共识 30 日变化 %"，曲线 −10→10、−3→35、0→55、3→75、10→95，权重 15，其余四项权重按比例缩到 85 |
| FR-M9-14 | F-04 主营分部利润率改善：核心分部（最近 4 季收入最大的分部）的分部利润率同比变化（pp），曲线 −5→10、−2→35、0→55、2→75、5→95；加入质量账，权重 15，其余按比例缩到 85；单一分部或无分部时 `NULL` |
| FR-M9-15 | F-05 核心分部增速：核心分部收入同比，沿用营收增速曲线；加入成长账，权重 20，其余按比例缩到 80 |
| FR-M9-16 | F-06 波动率调节仓位（B9）：记录 `cap_eff` 和"若生效，当日计划首笔或加仓金额变为多少" |
| FR-M9-17 | F-07 估值位置：引用 M5 的 V-T1 / V-T2 结果，不重复计算 |
| FR-M9-18 | F-08 S10 资格：对规则 A 当日每一笔价格型卖出（M-51、M-55），按规格第 10.4 节四项条件判定资格，并记录当日系统性事件标签；资格成立时记录"若 S10 生效：卖一半，二级线价位" |
| FR-M9-19 | N9：规则 A 当日 `entry_pass = false`，而某个因子单独替换后 `would_pass = true` → 生成 N9 记录（附因子编号和"差在哪一项"），供 M10 的标的总表和盘前计划展示 |
| FR-M9-20 | 每天在 M4 的计划生成之后运行；写 `job_runs` |

## 6. 异常与降级

| 情况 | 行为 |
|---|---|
| M8 当日未完成 | 覆盖层沿用上一版本，`generated_at` 不更新；M4 看到"过期"后照常运行 |
| 因子输入缺失 | 该因子当日 `value = NULL`，不判定 `would_pass` |

## 7. Harness 与自测

| 测试名 | 标记 | 断言 | 夹具 |
|---|---|---|---|
| `test_overlay_only_tightens` | blocking | I24 | 合成 |
| `test_overlay_cooling_rules` | blocking | FR-M9-01、02 的每种生命周期和方向组合 | 合成 |
| `test_overlay_contract` | blocking | JSON 字段齐全；`first_lot_multiplier = 1.0`；`stop_review_eligible = false` | 合成 |
| `test_shadow_signals_no_orders` | blocking | I32 | 合成 + 迁移 |
| `test_factor_shadow_no_orders` | blocking | I35 | 合成 + 迁移 |
| `test_x1_once_per_event` | blocking | X1 同一持仓同一事件只记一次 | 合成 |
| `test_f01_values` | blocking | `f01_growth_adjusted_valuation` 全部用例 | `golden/m9_factor_shadow.json` |
| `test_f02_values` | blocking | `f02_inflection_quality` 全部用例 | 同上 |
| `test_f02_shadow_hysteresis` | blocking | `f02_hysteresis` 的状态序列 | 同上 |
| `test_single_factor_substitution` | blocking | 只替换一个账本，其余沿用规则 A 当日结果；生成 N9 | 合成 |
| `test_factor_versioning` | blocking | 改定义产生新版本，旧记录不变 | 合成 |
| `test_s10_eligibility_shadow` | blocking | 四项条件缺一不成立；M-50、S4 不在作用范围 | 合成 |

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应需求 | 阻塞 |
|---|---|---|---|---|
| AC-M9-01 | 第 7 节 blocking 测试全绿 | H | FR-M9-01–20 | 是 |
| AC-M9-02 | 东芝案例回放：WDC、STX 冷静期；MU 不冻结；分支 A 截止日后解除；分支 B 延续到下一份 10-Q | D | 不接刀，也不被情绪带着走 | 是 |
| AC-M9-03 | 覆盖层连续 5 个交易日在北京 20:30 前发布；停掉覆盖层服务后 M4 照常出计划并标"覆盖层未接通" | D | 鲁棒性 | 是 |
| AC-M9-04 | 59 只每天都有 F-01–F-08 的影子值或 `NULL` 原因；LITE、BE 在因子页上能看到"差多少、差在哪一项" | E | 高 PE 路径持续迭代 | 是 |
| AC-M9-05 | 影子信号每条都有触发条件明细，能与 M8、M4 的原始记录逐条对上 | E | 可复盘 | 是 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M9-1 | 利好事件要不要冷静期？ | 要。直接暴露且非估值倍数的利好事件也进冷静期（不追）；"已验证·有影响"且方向有利时解除 |
| Q-M9-2 | "A+ 影子会买入"在第一阶段怎么算？ | 按单因子替换判定 `would_pass`，不模拟组合；完整的 A+ 组合模拟放第二阶段 |
| Q-M9-3 | F-03、F-04、F-05 的曲线和权重从哪来？ | 本文定义的 v1；第二阶段回测后可以改版本 |
