# M9 自测与剩余接口问题（草稿，未提交验收）

模块：M9 / A-015；规格：M9 v3、T09 2026-10-21更新。
业务实现提交：`e18beb15c29394c3cf14425e8f8a7886cb77cf09`（最新说明文案及完整head见A状态）。PR45保持草稿，未通过完整模块验收。

2026-10-22 增量：已合入需求方统一的deadline语义与唯一JSON，完成独立M9逐标的缺项消费；A1–A6分项证据和尚未满足的真实接线/回放见 `provider-contract-checklist.md`。消费实现阶段本地M9/M4相关58 passed / 3 deselected。随后up/down合同14 passed记录为 `provider-direction-green.xml`。最新继承main aefc62b的check_scope裁定：M8真实链保留“无关系→纯共振”，M9防御输入单独验证；新增纯共振off用例并直接消费新版合同，15 passed、Ruff通过，`provider-scope-green.xml`，原业务判定未变。以下旧K01“不完整”的描述仅记录此前B035读取路径，不取代最新provider的整日complete/逐字段missing合同；最新已合并快照接线验证见下节。

## 最新集成结果（2026-10-22 22:18 北京）

已继承验收合并 main 6ee26bb/B036–B041，默认原生 provider 已由真实形态不可变快照 fixture 验证；单字段缺失正常发布 unknown，只有整日缺快照沿用旧版本。旧 B035 夹具与“字段缺失导致整日不完整”的描述仅为历史记录，当前语义见 provider-contract-checklist.md。

新增 `replay-m8` 只读历史快照入口，逐日输出带 replay=true 封装的覆盖层到新的独立目录，保留真实生成时间、字段缺口及空日原因；不使用实时 FileDelivery 文件名，不写业务库、不调模型。先失败提交1d13d10、5 failed已保存，后实现及路径/账号保护回归通过。最新 M9/M4 **70 passed / 3 deselected**、Ruff通过，证据 m8-replay-green.xml。真实五日生产回放仍未执行：M8账号接线修复B042与费用确认停点继续有效；A5未冒称完成。新准确head干净CI由PR和A状态另核。

## 1. 已实际验证

- 指定12项测试真实先失败提交`e63629dafee13772e7efdef36bffa55e6fabcd4b`，`red.xml`；核心实现在其后提交，未篡改golden或跳过测试。
- M9目前27项离线测试通过；与原M4及已合并B035适配器回归合并为 **50 passed、3 deselected**，证据`provider-green.xml`。此前23项M9/合计40项的证据为`green.xml`。没有真实数据库、行情、模型或生产订单调用。
- 新增pipeline/input/risk测试也各自保留实现前失败证据：`pipeline-red.xml`（4失败1通过）、`inputs-red.xml`（3失败）、`risk-red.xml`（2失败）。S1夹具在实现阶段补明确财报period_end，避免用缺财报身份的两行数据冒充连续两期。
- 权重回归先失败提交`b660e1e8cf95c84e2eb455f37708b7e7ec50a7a9`、`weights-red.xml`，再修复F03/F04/F05：逐原子项缩放后按M11对可用项重配，不能用旧账本总分直接混合。原子项未提供或不能复现当日原账本时，替换结果/过线判断保留NULL和原因；因子登记输入包含原子项快照。
- 默认入口接线先失败提交`85ad25a18b69199b89dde89bb2beb4aab12837b2`、`provider-red.xml`真实4失败，再实现：无手工注入时调用已合并B035 provider；M8三阶段job取前一已闭市输入交易日，overlay目标仍为当天；固定同一cutoff，独立只读事务，不让provider的ROLLBACK结束主输入事务；来源job/event IDs及字段缺口贯通摘要和日志。权限失败只记错误类型/未知，不暴露数据库错误文本、不换账号。
- Ruff check及format通过。M9的12行pending已因实际转绿删除；原有其他pending项均保留，另补下述新规格漏登记项。milestones、docs、golden仅继承main，未自行修改。
- 继承main的新增M10 FR-M10-15后，发现文档新测试`test_paper_input_completeness_passthrough`未登记，pytest在收集前被FR-M0-05拒绝。按既有registry规则将该精确M10名称登记为待实现；未定义假测试、未标完成、未跳过任何现有检查，未实现M10或改只读文档。
- 完整核心head`311380cb9832890b2e260236fb88dccfb750e30c`的[真实CI成功](https://github.com/XuQingsong/inves-cog/actions/runs/39551966469)。该CI不能冒称后续head的CI；后续完整head须另查并记录。
- 权重修复前head`1f6a076623150636a803c0326e7c58e7260ff015`的[真实CI成功](https://github.com/XuQingsong/inves-cog/actions/runs/39559528454)已查；该结果不代替本次权重修复后的准确head CI。
- 上一次完整head`2de34aa17230a14eac5ad3a486d7294b4f2f22ef`的[准确CI成功](https://github.com/XuQingsong/inves-cog/actions/runs/39561913979)：432项、M0两项自检；这不能替代本次接线后新head的CI。最新完整head CI由A状态另行核实。
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
| AC-M9-01 | 12个指定blocking存在且通过；额外15项、原M4及B035回归也通过。最新完整head make CI另行确认，未据此宣称整模块关闭。 |
| AC-M9-02 | `synthetic-contract-evidence.json`明确标为合成：WDC/STX冷静、MU不冻，A分支到期解除，B分支延续至合成下一份10-Q；只是分支规则验证，不冒充真实经营/历史证据。真实源快照定位见K01。 |
| AC-M9-03 | **真实5日PIT回放尚未执行**：已接入已合并B036–B041不可变快照读取器，字段缺失按ticker标unknown，整日缺快照才incomplete。独立历史回放入口已准备，不能用合成五日证明生产结果。旧覆盖层保留和M4缺失照常计划已离线验证。一次自然运行单列OPS；M4时序已获用户决定，实际调度按最新答复在A015后另派任务实施。 |
| AC-M9-04 | 合成正式59只×8=472项完整样例，非适用或缺输入均NULL/原因；LITE/BE有逐项book_shortfall，BE-like F01为29.166917、距30约0.833083，LITE示例估值过线但质量不足，不把组合替换当单因子N9。其余标的缺输入明说，不冒充59只真实批次。 |
| AC-M9-05 | 合成X1/X2/X3/X4的源事件/信息/订单ID、逐条件输入已验证；X1使用每事件独立EPS基线、持仓段/事件一次。真实M8/M4逐记录对账待K01真实快照；不生成假信号充数。 |

## 4. 交付入口

- `inves_cog.overlay.api:create_app(delivery)`为可组合只读HTTP接口；`python -m inves_cog.overlay.api --directory ... --port ...`提供无新依赖的独立只读监听入口。未在生产监听。
- 文件沿用M4原`INVES_COG_OVERLAY_DIR/event_overlay_YYYY-MM-DD.json`合同；不改M4读/写代码。
- `python -m inves_cog.shadow.cli scheduled`、`scripts/schedule_m9.py`调用既有job_runs框架，使用独立overlay/shadow原角色连接；缺连接不借其他角色或管理员。当前未安装生产服务、未创建登录或修改生产权限。
- `python -m inves_cog.shadow.cli replay --snapshot ... --cutoff ... --output-directory ...`只在独立目录回放显式快照，默认摘要输出，不导出私人持仓/页面。
- `tests/m9/evidence.py`生成合成审阅样例；仅经load_golden读取，未联网、未调模型、未读其他项目库。

## 5. 真实适配与数据限制

K01：B035已验收合并并接入默认生产路径，三阶段真实结束时间作为完成标记；源日取前一已闭市交易日。当前已合并不可变快照路径由上述最新集成验证；缺字段逐ticker unknown，缺快照才incomplete。A不扩大M8权限或制造历史版本。

K02：UD-COORD-25/UD-A-19已批准M4改到ET08:35–09:05、M9仍ET08:00–08:30，失败仍照常计划并标缺失。不再等待同一答复。最新A015答复要求M4实际调度代码在A015后另派任务，PR45未改M4窗口或一次运行保护；`integration-timing.json`保留的是旧代码真实错位复现，不能冒称新窗口已安装。

真实旧持仓的B2入场适用快照未明确时，f02_state写出入场状态缺失原因，不能拿今天分数追认原入场资格。多轴/多重述分部或四季不足不猜核心分部；事件建立日前EPS快照不够则X1该条件未知；S10缺历史时不判资格成立。这些均不以0替代，也不修改上游输入。

## 6. 尚未做的事

未提交正式验收，未合并PR；未执行生产迁移/服务安装/历史回填；未调用模型；未实现A+组合模拟或M10页面。A014剩余自然OPS仍按今晚/明早窗口由A跟进，未被本模块测试替代。
