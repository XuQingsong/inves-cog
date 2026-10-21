# M9 自测与剩余接口问题（草稿，未提交验收）

模块：M9 / A-015；规格：M9 v2、T09 2026-10-21更新。
业务实现提交：`4ef3ceb2ebcee61372acf883e0e343302f6e0061`。PR45保持草稿；最终完整head和对应真实CI由A状态回报标识。

## 1. 已实际验证

- 指定12项测试真实先失败提交`e63629dafee13772e7efdef36bffa55e6fabcd4b`，`red.xml`；核心实现在其后提交，未篡改golden或跳过测试。
- M9目前22项离线测试通过；与原M4覆盖层/纸面行为回归合并为 **39 passed、3 deselected**，证据`green.xml`。没有真实数据库、行情、模型或生产订单调用。
- 新增pipeline/input/risk测试也各自保留实现前失败证据：`pipeline-red.xml`（4失败1通过）、`inputs-red.xml`（3失败）、`risk-red.xml`（2失败）。S1夹具在实现阶段补明确财报period_end，避免用缺财报身份的两行数据冒充连续两期。
- Ruff check及format通过。M9的12行pending已因实际转绿删除；其他pending原样保留。milestones、docs、golden未修改。
- 完整核心head`311380cb9832890b2e260236fb88dccfb750e30c`的[真实CI成功](https://github.com/XuQingsong/inves-cog/actions/runs/39551966469)。该CI不能冒称后续head的CI；后续完整head须另查并记录。
- 本地整仓直跑记录`local-environment.xml`：415通过、6失败、21 deselected；失败涉及本机无Docker/SciPy及沙箱拒绝AF_UNIX。没有改门禁或跳过；干净容器的make phase1-test以准确head CI为准。本机没有Docker，未将直跑pytest冒称本机make clean-container全绿。

## 2. 不变量和边界

| 项 | 证据 |
|---|---|
| I24只收紧 | 严格输出字段白名单、冷静期正反例/多事件并集、first_lot_multiplier恒1、stop_review_eligible恒false；HTTP与文件一致；恶意增买/卖出字段被拒；原M4冷静期撤买/缺失照常出计划回归通过。 |
| I32影子信号隔离 | X1–X4只写perception_shadow；固定表写入白名单拒绝trading.orders；原M0交易角色拒读影子schema，M9迁移再次显式REVOKE。 |
| I35因子隔离 | 8项因子、N9、F02状态只写factor_shadow，写入器拒绝trading.ledger；没有引擎/下单调用，actual orders不变。 |
| PIT | live输入仅只读、filed/observed_at/captured_at按cutoff筛选；历史CLI要求原快照和明确cutoff，不从当前可变DB行反推过去；嵌套晚生成记录被拒；历史回放生成时间用真实执行Clock，不能冒称自然按时发布。 |
| 版本 | 注册定义含实际参数，改变定义新增版本，原版本每日行保留；覆盖层递增版本、M8未完成保留旧generated_at；文件写失败不将DB准备记录标已发布。 |

## 3. AC自评（不代需求方验收）

| AC | 当前自评与范围 |
|---|---|
| AC-M9-01 | 12个指定blocking存在且通过；额外10项、原M4回归也通过。最终完整head make CI仍需独立确认，未据此宣称整模块关闭。 |
| AC-M9-02 | `synthetic-contract-evidence.json`明确标为合成：WDC/STX冷静、MU不冻，A分支到期解除，B分支延续至合成下一份10-Q；只是分支规则验证，不冒充真实经营/历史证据。真实源快照定位见K01。 |
| AC-M9-03 | **真实5日PIT回放尚未证明**：现有M8可变report不能冒充历史快照，未造5份空“成功”覆盖层。缺失源保留旧版本及M4照常出计划已有离线回归。一次自然运行单列OPS，不阻塞代码开工；共享调度接线另见K02。 |
| AC-M9-04 | 合成正式59只×8=472项完整样例，非适用或缺输入均NULL/原因；LITE/BE有逐项book_shortfall，BE-like F01为29.166917、距30约0.833083，LITE示例估值过线但质量不足，不把组合替换当单因子N9。其余标的缺输入明说，不冒充59只真实批次。 |
| AC-M9-05 | 合成X1/X2/X3/X4的源事件/信息/订单ID、逐条件输入已验证；X1使用每事件独立EPS基线、持仓段/事件一次。真实M8/M4逐记录对账待K01真实快照；不生成假信号充数。 |

## 4. 交付入口

- `inves_cog.overlay.api:create_app(delivery)`为可组合只读HTTP接口；`python -m inves_cog.overlay.api --directory ... --port ...`提供无新依赖的独立只读监听入口。未在生产监听。
- 文件沿用M4原`INVES_COG_OVERLAY_DIR/event_overlay_YYYY-MM-DD.json`合同；不改M4读/写代码。
- `python -m inves_cog.shadow.cli scheduled`、`scripts/schedule_m9.py`调用既有job_runs框架，使用独立overlay/shadow原角色连接；缺连接不借其他角色或管理员。当前未安装生产服务、未创建登录或修改生产权限。
- `python -m inves_cog.shadow.cli replay --snapshot ... --cutoff ... --output-directory ...`只在独立目录回放显式快照，默认摘要输出，不导出私人持仓/页面。
- `tests/m9/evidence.py`生成合成审阅样例；仅经load_golden读取，未联网、未调模型、未读其他项目库。

## 5. 真实适配与数据限制

K01：请需求方定位既有M8当日完成标记与历史PIT事件快照。默认未接通时不会发布一份假新覆盖层，原生成时间保留。

K02：`integration-timing.json`已用FrozenClock复现现有M4固定北京时间20:00、M9按美东08:00的冬令错位，以及缺少先发布后读计划的明确顺序。需需求方确认共享调度合同，A不擅自改M4规则或一次运行保护。

真实旧持仓的B2入场适用快照未明确时，f02_state写出入场状态缺失原因，不能拿今天分数追认原入场资格。多轴/多重述分部或四季不足不猜核心分部；事件建立日前EPS快照不够则X1该条件未知；S10缺历史时不判资格成立。这些均不以0替代，也不修改上游输入。

## 6. 尚未做的事

未提交正式验收，未合并PR；未执行生产迁移/服务安装/历史回填；未调用模型；未实现A+组合模拟或M10页面。A014剩余自然OPS仍按今晚/明早窗口由A跟进，未被本模块测试替代。
