# M4 自测报告

模块：M4。文档：v4（含 main 89ac693 的 Q-M4-11）。代码提交：700bdbbcf264a3294c0a4c7f4f39ff94abe1d47d。日期：2026-10-16。

## 1. Harness

- 本模块 15 个规定测试名全部存在：12 blocking、2 replay、1 phase1_live；未增加替代验收名，没有 skip。最后全仓离线 `pytest -m 'phase1_blocking or phase1_replay'` **114 passed、0 failed、0 skipped，45.82 秒**，见 blocking-replay-final.xml。其中包含 M4 全部 14 项离线测试和其他模块回归。
- 独立 M4 集合 14 passed、1 live deselected，8.66 秒，见 offline-final.xml；live 显式 INVES_COG_LIVE=1、-m phase1_live、只读真实 inves_cog 库 **1 passed，5.055 秒**，live-smoke.xml。deselected 是未选 live 标记，不是 skip。
- 本机没有 Docker，`make phase1-test` 在创建容器之前明确退出，未冒称本机容器入口通过；该入口、M0 CI 断言及破坏性自测以本 PR **当前完整 SHA 的 GitHub phase1-blocking CI** 为准，准确链接同步在 PR/ops/status/A.md。Ruff check 与 format --check 全绿。
- 保留红灯历史：初始测试/夹具 f02bd7b（12 failed）；容量冲突测试 5258363；按 Q-M4-11 接受 12+1，核心第十三名/观察第四名仍被拦；北京冬夏边界先 b04c09b（2 failed）后 e5818e9 修复；缺账本持仓说明先 aa6eb21（1 failed）后 700bdbbcf264a3294c0a4c7f4f39ff94abe1d47d 修复。原红灯 XML 均保留。
- 全仓首轮唯一格式失败已保存在 blocking-replay-format-red.xml；格式化本模块 service.py 后重跑同一集合通过，没有改门禁或断言。

## 2. 不变量

| 不变量 | 结果和证据 |
|---|---|
| I05 订单理由 | test_order_reason_tokens：M- 编号、中文解释；估值情景、非规则编号正反校验 |
| I06 订单单一入口 | test_orders_only_from_engine：唯一 INSERT 在 trading.engine；迁移 role_trading 写、role_web 只读；database.json 实际拒写 |
| I07 成交及成本 | test_fill_timing_and_cost：前一信号日、次交易日开盘、整数股、0.1% 成本；Q-M4-9 spend 门槛/手续费单扣/负现金如实标记 |
| I14 当日成员 | test_membership_asof：上市前排除、上市日纳入 |
| I15 v18 复现 | test_v18_replay：90 笔日期/代码/动作/股数零差异 |
| I16 AMD | test_amd_entry_2026_01_12：01-09 信号，01-12 实际开盘买入 |

## 3. pending 与 milestones

本模块 15 项在分别实际通过后已全部从 pending.txt 删除；最后未因容量红灯重新放回 pending。milestones.txt 完全未改，模块关闭由需求方决定。docs/golden 与合入 main 的原文一致，未编辑标准答案。没有运行或导入 Muse/stock-pm，也没有访问它们的数据库。

## 4. 验收逐条自评

| AC | 自评 | 证据 |
|---|---|---|
| AC-M4-01 | 通过 | blocking-replay-final.xml，12 个 M4 blocking 全绿；北京固定时段、覆盖层、容量与持仓说明均有正反断言 |
| AC-M4-02 | 通过 | replay.json：收益 **49.4527339798%**、最大回撤 **−12.6370184987%**、匹配率 **100%（90/90）**；终值 1,494,527.339798 美元 |
| AC-M4-03 | 通过 | replay.json comparison.differences=[]，90 笔日期/代码/动作/股数全部一致，无未匹配项需要归类 |
| AC-M4-04 | 通过 | test_amd_entry_2026_01_12，AMD 01-12 买单/01-09 信号日期；replay.json 逐笔可查 |
| AC-M4-05 历史部分 | 通过 | five-day-plans.json：10-09/12/13/14/15 五个目标交易日，逐日前一交易日信号，全部 54/54 可交易美股行情、覆盖 100%；M2 fixed PIT → 本项目 M3 历史纯函数，不向上游表写入；每个计划固定模拟北京 20:00，而非真实按时运行 |
| AC-M4-05 调度部分 | 待合并后运维确认，不挡合并 | 没有把五日回放、缓存、白天探针或 live 冒烟当作准时调度。M4 未部署/未做生产迁移，1 次准时发布仍需实际 job_runs |
| AC-M4-06 | 待需求方抽查 | 可抽 five-day-plans.json 的 10-09、10-13、10-15；订单分别 13/4/5，跳过 10/9/13，逐条保留规则编号和中文理由；此处不代替需求方手工验收 |
| AC-M4-07 | 通过 | test_overlay_cooling_skip_and_cancel；overlay-demo.json：AAA 原有买单进入 cancels、次日 0 成交，BBB 正常成交；覆盖层增加请求被忽略并记录错误 |

五日计划订单数为 **13/5/4/1/5**，跳过 **10/9/9/12/13**。10-09 的十三只由 **十二个核心买单 + HD 观察波段**构成，按 Q-M4-11 合法；没有删除这个真实正例。

生产 live 与历史复算分别标明：live-plan.json 的 score_source 为 trading.daily_scores，10-15 只有 UNH 已发布快照，其他 **53 只缺 M3 快照**；missing_scores 列全名单，health_codes 含 upstream_scores_missing。没有用历史重算伪装已发布分数，也不声称完整日常交易数据已就绪。

持久化/权限：database.json 使用新建后已删除的独立临时测试库跑全部迁移；重复保存订单、账本各 1 行，恢复后的同日重复成交不重复扣现金；role_web 能读而写入被拒。生产 M4 迁移 **0**、新角色 **0**。

## 5. 中期检查点和规则细节

checkpoint.md/checkpoint.json：2026-01-02–03-31 **36 笔、100% 一致**，收益 **−4.4592360022%**，回撤 **−9.8453132174%**。

Q-M4-9：完整区间负现金 **0 天**，最低 **3,377.696828** 美元；前三个月负现金 0 天、最低 245,662.891198 美元。合成边界实际出现 −5 美元，账本保留并标 cash_negative，未预留手续费改变股数。

Q-M4-10：90 笔中因计划/成交分层不同的买单 **0 笔**，对应股数改变 **0 笔**；每个买单保留 planned_tier、tier、planned_tier_only_qty。replay_v18 使用成交日 tier；paper 使用已发布计划时 tier，不读取未来成交日分层。

## 6. 破坏与放行检查

模块文档没有额外独立破坏清单。规定测试内完成：非法理由/非 M 编号拒绝；合法中文订单放行；上市前排除/当日纳入；恐慌阻止限定卖出而放行 M-50/51/波段退出；核心冷却拦截而合法波段不误伤；覆盖层冷静撤单而其他标的继续；增加请求拒绝；94% 行情不发布、95% 放行；VIX 缺失不恐慌；十二核心和三观察的合法容量放行，分别超限被拦；缺账本在持仓标 N8，同时不阻止独立价格破位条款。

本次还修正北京时段近似纽约小时造成的冬令时错位：20:00–20:30 发布、18:00 覆盖层门槛均为 Asia/Shanghai。beijing-time-red.xml 保留修前错误；冬夏和边界/未来覆盖层均已转绿。缺账本持仓原先笼统显示 M-59，现明确缺失字段及已选动作，holding-status-red.xml 保留修前失败。

## 7. 已登记偏差与待办

- Q-M4-8：核心冷却与波段各自间隔按 v18；Q-M4-9：取整前 spend 与手续费边界；Q-M4-10：回放和 paper 分层 PIT 区分；Q-M4-11：观察挂单独立名额。源码固定 aacea04，只读位置及实现注释在 kickoff/checkpoint 与对应代码中。
- 无未答复的 M4 规则问题。AC-M4-06 仍由需求方实际抽查；准时发布属于合并后运维项。
- A-006 日常 M3/M6/M2 部署独立待数据库 CONNECT 权限：两个既有角色已有 LOGIN 和原有表权限，但实际不能建立连接。已在 GitHub 信箱如实报告；未擅自增加权限、启用管理员长期账号或改生产定时服务。该部署等待不冒称 M4 已上线。
