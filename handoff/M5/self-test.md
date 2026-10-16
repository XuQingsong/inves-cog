# M5 自测报告

模块：M5　文档：v2，含 Q-M5-4 / main 2090a71 的 K01 澄清　日期：2026-10-16

验收代码提交：[2bbd615e0d25dceec8b284c105eeb87183e7707d](https://github.com/XuQingsong/inves-cog/commit/2bbd615e0d25dceec8b284c105eeb87183e7707d)。[该完整 SHA 的 phase1-blocking CI](https://github.com/XuQingsong/inves-cog/actions/runs/38914730518) 已成功。证据提交后的最终 head / CI 以 PR #17 和 agent-status 的 A 线回报为准；`code-manifest.sha256` 可核对实现及测试内容。

**提交状态**：实现与自测齐备，仍保持草稿。D-15（第二次完整59只一致预期采集）要求在 M5 提交验收之前完成，目前仅能核实一批；已向需求方回报，A 不越过 M1/M2 只读边界自行采集。该前置关闭后才正式提交。

估值参考 v1，不参与仓位

## 1. Harness

在项目锁定依赖的 Python 3.11 环境执行：

```bash
PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 INVES_COG_LIVE=0 python -m pytest -q -m 'phase1_blocking or phase1_replay'
INVES_COG_LIVE=1 PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/m5 -m phase1_live -q
```

- 全仓离线 **127 passed，0 skipped，7个 live 测试按约定未选入，34.03秒**，`blocking-replay.xml`。包含 M4 已有 v18 回放和 M5 的订单隔离回放。
- M5 的 **12 blocking + 1 replay 全部通过**；真实只读 live **1 passed，13 deselected，2.98秒**，`live-smoke.xml`。live 从本项目现有表读取，以既有 `role_valuation` 验证权限，没有请求新数据源、产生订单或写生产表。
- 所有14个指定测试名存在；Ruff 检查及格式检查通过。未改 golden；标准答案只由 `load_golden` 读取。
- 代码提交的 GitHub CI 在干净环境检查，结果见上方准确SHA链接。本机使用同一离线集合；不将本机 Python 命令说成已运行本机 Docker。
- 初始13个离线合同全部失败（`red.xml`）后才实现。K01、输入口径、SIC/候选、总目标、缺失置信度、同日权益/未知合计、3%端点、实际差异描述、FCF绝对值各有先失败后修复的提交及 `*-red.xml`。没有 skip 或修改标准答案转绿。

| 指定测试 | 标记 | 结果 |
|---|---|---|
| test_valuation_synthetic | blocking | 全部五类、P90、p、档位、隐含增速、分位/截尾命中 |
| test_growth_valuation_v11 | blocking | 三年衰减；现金跑道严格使用FCF绝对值 |
| test_valuation_ignores_price | blocking | 所有合成案例改变现价，三档不变 |
| test_valuation_monotone_and_stable | blocking | 有序与稳定；3%端点及紧邻float64步长均按严格阈值处理 |
| test_trading_without_valuation | replay | 同输入的M4计划字节相同 |
| test_valuation_schema_revoke | blocking | 静态有效权限、迁移和写表白名单 |
| test_valuation_label | blocking | 各输出固定句；调度夏令时/冬令时及收盘边界 |
| test_type_switch_needs_two_periods | blocking | 不同财报期确认；重复同一期不凑两期；人工审计 |
| test_change_decomposition_sums | blocking | 固定替换顺序，总和等于中性值变化 |
| test_pending_review_over_25pct | blocking | 无新财报大幅变化不替换；新旧并列 |
| test_implied_growth_no_solution | blocking | 无解NULL并说明；超60%的隐含增速保留 |
| test_position_panel | blocking | 全部golden；SIC、候选、同股多笔、总目标、同日权益、未知汇总、单股失败隔离 |
| test_shadow_rules_no_orders | blocking | 阈值两侧；单版本V3；K01节点/插值/钳位；缺失不改用p |
| test_valuation_live_smoke | live | 本项目59只都有真实输出或具体不估原因 |

## 2. 应关闭的不变量

| 不变量 | 自测 | 证据 |
|---|---|---|
| I17 三档不读现价 | 通过 | 价格变动合同；历史PE逐日取当时fixed EPS，月首缓存；当日价格不进入倍数样本 |
| I18 有序与稳定 | 通过 | 全部可估行有序；五日56组有效对照三档变化为0 |
| I19 交易独立 | 通过 | 关闭/启用估值后五日M4计划字节完全相同；不写交易表 |
| I20 权限隔离 | 通过 | 隔离库实际 role_trading SELECT 被拒；role_valuation 写 trading 被拒 |
| I21 固定标注 | 通过 | ranges、panel、summary、shadows及JSON入口均带固定句 |
| I27 成长三年公式 | 通过 | 全部成长golden、P90封顶、独立算术对照 |

## 3. pending / milestones

仅删除实际转绿的14行 M5 pending；不修改真实 milestones，不删除其他模块行。

继承 main 2165c29 时，M8 新增两个测试名未登记导致全仓收集退出4；需求方在 8d748ef 修复，A 只合入 main。最终对 main 的 pending 差异只有 M5 的14行删除，未放宽门禁。K01 / K02 的闭环记录见 `questions.md`。

## 4. 验收条款自评

| 条款 | 自评与边界 | 证据 |
|---|---|---|
| AC-M5-01 | 自动测试通过，14个测试均已存在并转绿 | `blocking-replay.xml`、`live-smoke.xml`、准确代码SHA的CI |
| AC-M5-02 | 59行：14行有数值、45行明确不估、0行异常失败。没有用普通股代替稀释股本或用ROE代替ROTE | `real-ranges.json`、`daily-values.md`、`coverage-and-outliers.json` |
| AC-M5-03 | 全部可估行悲观≤中性≤乐观；比例软指标未达标，按条款逐只附解释，不调参数凑比例 | 同上；14个有p样本中，10个p>1（71.43%）、2个p<0（14.29%）；另列59只总分母比例16.95%/3.39%，不把缺失当中性 |
| AC-M5-04 | 五类型真实/明确缺失样例齐备，含AMD；可计算的3行用独立算术复算一致。周期WDC和金融JPM的真实字段不足，明确保留缺失，另附标注为合成的标准公式例，待需求方手核 | `manual-check.json`，真实V、AMD、WDC、CRWV、JPM；补充合成周期/银行例不冒充实盘 |
| AC-M5-05 | 最近五个真实交易日10-09/12/13/14/15，按当时可见财报/预期逐日产出。只比较两日都有数值且无新财报、预期变化≤3%的56组，三档完全不变；未用NULL==NULL凑稳定覆盖 | `five-day-replay.json`（去重输入快照可按SHA核对）；1次准时调度属合并后运维确认，尚未运行，不冒称已按时触发 |
| AC-M5-06 | 同一真实上游数据、M4自带的合成历史纸面账户，估值关闭→启用，五日完整计划字节一致；隔离库实际M4计划记录也未变 | `trading-decoupling.json`、`isolation.json`；没有公开真实账户/计划明细 |
| AC-M5-07 | 全部持仓与计划候选、总目标（持仓+新增）、同股多笔、组合及篮子汇总在冻结样例和隔离库验证；未知合计不写0，低置信度影子不入统计。**生产M4表尚未部署，真实面板显示未接通，不能声称真实持仓已核验** | `isolation.json`、`test_position_panel`；`real-ranges.json`的holdings_reason以及59条影子实际比较不可用标记 |

AMD真实取样（2026-10-15收盘输入）：悲观 **216.1520106783**、中性 **334.9227242095**、乐观 **408.3733578489** 美元；价格562.23，**p=1.8004139208**，g=23.5980362350%。这些是本模型快照值，非现时价格或交易建议。

## 5. 破坏性与正反自测

- 现价170改成10000000：三档完全相同，位置变化。价格不能反向改价值。
- 两端截尾、EPS≤0、未来快照、未来捕获时间、过期财年与最新失败快照：该剔除的剔除，正常历史/有效快照保留，不用更早成功值掩盖最新失败。
- 当前普通股口径不能当稀释股本；已核实的稀释加权来源能正常进入。
- 无新财报把中性提高超过25%：新值待复核、原值保持；新财报有效更新可正常重算。
- 相同财报期重复两次不切换类型；两个不同期间满足则切换；人工指定必须带操作者/理由。
- 隐含增速在[-50,200]区间无解：NULL和明确原因；超过基础60%上限的真实解不截断。
- role_trading读估值、role_valuation写交易、role_web写估值均在隔离库被拒；正常估值写入、web只读成功。临时库已删除，生产迁移0次。
- 失效单股输入只使该行failed；其余行继续。卖单不混进新开候选；多笔新增不覆盖实际持仓或总目标；账本旧权益用同日标价重估，缺标价不假造0。
- K01每个节点、插值和两端钳位均验证；成长Δg缺失时V1为NULL而不是改用p。V3同版本已触发则不重复；不产生任何交易订单。

## 6. 已知限制与依据

1. **D-15未关闭，尚不正式提交**：M2 AC-M2-06b及遗留清单要求至少两次完整59只真实一致预期采集，期限M5提交验收之前。现有可核实Yahoo批次为1次；Muse历史导入不能代替。`upstream-readiness.json`是只读核对，A不跨模块补写或换源。待需求方安排/明确一次既有采集授权。
2. **45行不估不是45个“上游没有数据”的结论**：多数是M2已交付接口只暴露期末普通股，M5需要稀释加权股本；金融接口没有ROTE/TBV；部分IPO年度序列不足且没有已确认的板块常态利润率参数。按README§3.4和AC-M5-02逐只列原因，未臆造或用代理字段替代。是否扩展M2输入由需求方另行安排。
3. **比例软指标**：有p样本中p>1超过30%，按AC-M5-03作为后续调参输入；逐只列定价EPS、g、区间和取样价格，给可复算的数值原因，未声称市场必然高估。PANW出现顺序重排，已标方法异常/待复核。
4. **真实持仓未接通**：M4已验收但生产表未部署。开发接口和隔离数据验证完成，真实返回明确缺口；合成账户与真实公开财务取样分别标明，不将其混称真实仓位。
5. **上线未执行**：只新增M5迁移和美东22:30入口，job_runs由既有运维角色记账，估值写入走自身角色；未部署服务、运行生产迁移或新增权限。需合并后由明确运维任务配置 `INVES_COG_VALUATION_DATABASE_URL` 并核对一次真实按时任务。沿用既有数据源与依赖，无新key或付费源。

## 7. 新问题与下一步

K01影子节点、K02主线登记均已由正式答复关闭。剩余是D-15前置证据与已有输入/部署缺口，不擅自扩大到M1/M2或其他线。详见 `questions.md`、`tracker.md`。

D-15关闭后按任务把PR #17转正式「[M5] 提交验收」；不自行验收或合并，M5完成后停止取任务，等待M0–M8整体验证。

## 8. 最新main集成复核（2026-10-16）

需求方已按用户G4批准合并PR #11和#16。本分支合入main **a5991c93855018e62e4005e2b6aa05076272cfc4**，合并代码提交 **2cca0ad9629b823d803206b23ae86c5de596c7cc**。唯一冲突是pending：采用main已完成的M7状态，并继续删除本分支已通过的14条M5；夹具MANIFEST和CHANGELOG取并集。相对新main，docs、golden、milestones无差异，M5实现与测试的13个文件内容哈希均未变。

本轮只复核实际集成：全仓blocking+replay **143 passed、9 deselected，34.37秒**，`integration.xml`。首次在文件系统沙箱执行时142通过，唯一失败是AF_UNIX bind被执行环境拒绝；用允许进程内通信的环境运行相同离线集合后全部通过，没有改代码、门禁或测试（首次实际输出保留在`integration-sandbox.xml`）。新head的准确CI链接见PR与agent-status最终回报，不把旧CI冒称为新head结果。既有真实只读live、五日历史回放和隔离库历史验收材料保持原始执行记录，未重复采集或重新部署。

K03已在main **9d88f0601bc7203a49778168020fb79513c9432b** 正式答复：只允许北京时间2026-10-17 **09:15–10:30**运行既有M2 consensus一次；先核对当天已有完整59/59则跳过，窗口外不运行、失败不循环重试，不改源、配置、权限、服务或调度。D-15仍是1/2，等待窗口执行并独立确认后才正式提交。由协调方提醒当前任务；不恢复自动接单。
