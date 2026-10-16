# M3 开工复述单

模块：M3；需求文档：M3 v2；规格：v1.4；复述人：开发 agent；日期：2026-10-15。

基线：合并 PR #4、#6 后的 main `1f121fa0084f27a33ecaf85958722fdb027df7eb`，同时纳入任务补充 `62e4b48`。分支：`phase1/m3-rule-a-scoring`。本次只提交本复述单，没有实现代码、迁移或新增测试；提交草稿 PR 后等待答复。

已按顺序读整体任务书、阶段任务书（含 §4.6）、README §3–4、T03、M3 全文、规格 §9.1–9.8/9.13，以及 next-stage 任务、tracker 和 M2 验收报告 §6。Muse 只读固定提交的源码文本，没有导入、运行或复制其实现。

## 1. 要做的事

| FR | 我的理解与交付 |
|---|---|
| FR-M3-01 | 用截至信号日的拆股调整行情计算 §9.2 全部技术字段；不足 MA200 时不能入场并说明历史不足。 |
| FR-M3-02 | 重写分段线性插值及账本缺项重配权，覆盖全部曲线、端点、区间外、缺值和真实 0 分。 |
| FR-M3-03 | 计算质量、成长、估值、时机及五组时机子项，固定权重计算排名；核对合成 golden 和 Muse 600 行冻结结果。精度冲突见 K01。 |
| FR-M3-04 | M-07 过期清空三个基本面账本；M-08 拆股疑似仅清空估值。legacy 不套 fixed 的额外健康门禁。 |
| FR-M3-05 | 实现 M-13–18 的严格边界；前三类排除阻止入场，M-18 交 M4 阻止新开/加仓，M-16/17 只留标签。 |
| FR-M3-06 | 首次出现和新财报生效日重估层级，进攻优先，日常波动变化不改层；层级状态通过前序快照显式传入纯函数。 |
| FR-M3-07 | 输出成长确定性及点数、持有资格分、hold_ok、fund_bad、现金跑道。 |
| FR-M3-08 | 按层比较 M-30 门槛，应用 M-31/M-32，生成 entry_pass 及逐交易日累计的 consec_pass。 |
| FR-M3-09 | 仅接受 rule_set=A，其他值直接报错，拒绝隐式回退。 |
| FR-M3-10 | 读取并校验现有 rule_a_v18.yaml；保留上限、首笔和预算常量，不引入 tracker 固定止损止盈。 |
| FR-M3-11 | 财报和历史健康码唯一入口为 state_asof(ticker, signal_date, extractor)。 |
| FR-M3-12 | 每日 M2 财报状态任务完成后执行，按美东 22:30 配置（北京夏令时 10:30、冬令时 11:30），记录 job_runs；不等一致预期。 |

纯函数接收行情、PIT 财报状态、前序分层/连续天数和规则参数，不在计算内部取系统时间、访问数据库或网络。数据库读取和持久化放在任务适配层。

## 2. 不做的事

不做候选排序 M-34、订单、持仓、首笔数量 M-35–37、加减仓、卖出、风控、A+、估值区间或页面。SPY/VIX 不参与 M3 的四本账；大盘/恐慌闸门归 M4。外国申报人参与计算和观察，始终 tradable=false，不进入交易候选。

## 3. 输入与缺失处理

| 输入 | 来源与处理 |
|---|---|
| 日线 | M1 ingest.bars_daily；价格使用 open/close × adj_factor，成交量使用来源提供的 volume，不填补缺失、不另造分红复权。按真实交易日排序。 |
| 财报及健康码 | M2 state_asof；legacy 用于 v18，fixed 用于日常。禁止用最新 fundamentals.health 替换历史。M2 已交付的外国季度状态也只通过该接口读取，不在 M3 重算财报。 |
| 健康矩阵 | legacy 仅 M-07/M-08；fixed 用 M2 Q-M2-10 及 v9 Q-M2-32。extreme_value_verified 本身不阻止打分，其他阻塞码仍生效。 |
| 冻结输入/答案 | 仅通过 tests/harness/tools/golden.py 的 load_golden 读取 v18 下全部冻结行情、财报、VIX、scores_20days.json.gz，以及 m3_interp_points.json、m3_books_synthetic.json；不运行 Muse 生成答案。 |
| 参数 | config/params/rule_a_v18.yaml；每日快照登记 params_version。 |

行情整行缺失按文档不写当日分数行，在任务覆盖明细中记 no_bar；不足历史写可解释快照。财报缺项按 M-11 对同账本有效项重新分配权重，全空则 NULL，不能用 0、前一天财报值或最新值冒充缺项。真实 0 是有效值。没有 SPY/VIX 不影响本模块计算。

## 4. 输出与下游合同

新建唯一编号的 `migrations/phase1_m3_0001_*.sql`，由 inves_cog_admin 建 trading.daily_scores，业务写入用 role_trading，遵循现有 schema 的默认权限，不改 M0 权限矩阵。job_runs沿用现有共享运行记录接口，不给计算角色额外授予ingest写权限。

完整输出包括：signal_date/ticker/extractor/rule_set/params_version；tech；derived 中 pe/peg/mktcap/ps/fcf_yield；quality/growth/valuation/timing/timing_subitems/rank_score；red_lines/tier/tier_changed_on/certainty/certainty_points/hold_score/hold_ok/fund_bad/runway_ok；m31_adjusted_valuation/m32_ok/gate_pass/entry_pass/consec_pass/tradable/null_reason。供 M4 使用，M10 只展示已存快照。

按日期、代码、提取器和规则版本幂等写入，legacy/fixed 不覆盖彼此。NULL 保留为数据库 NULL/JSON null；时机明细包含缺项及原因。M-31 仅用于门槛比较，原始估值账不被修改。未应用 M-31 时 m31_adjusted_valuation 依合成 golden 为 null；回放比较时将 Muse 的 val_adj 作为有效门槛估值进行单独适配，不据字段名字改变计算。

## 5. 验收与先红后绿计划

| AC | 测试或证据 |
|---|---|
| AC-M3-01 | 先提交失败测试/夹具，再实现。12 个 blocking 原名保留：test_interp_points、test_books_synthetic、test_red_line_boundaries、test_tier_reassess_only_on_filing、test_m31_m32、test_stale_books_are_null、test_split_suspect_valuation_null、test_pit_filed_date、test_foreign_filers_not_tradable、test_rule_set_a_locked、test_v18_constants、test_no_tracker_stops_in_rule_a。 |
| AC-M3-02 | test_scores_match_muse 使用已有 20 日 × 30 只 = 600 行，比较全部约定字段、相对容差 1e-9；从 2025-12-31 初始财报及 2026 年连续交易日推进状态，再抽取指定 20 日，不能只计算抽样日而丢失分层/consec_pass。逐字段差异另表对应下述源码索引。 |
| AC-M3-03 | 本单 §7 的每条细节与需求方后续 Q&A 对应，代码注明固定提交及规则；K01/K02 未答复前不选定相冲突的算法。 |
| AC-M3-04 | 真正使用 2026-10-09 当时可见数据，提供 AMD、ANET、VRT、GEV、ETN、CEG 与规格现算表的逐账对照（容差 0.5）；LITE、BE、COHR 单独列 fixed。不把今天的健康状态倒灌到该日。 |
| AC-M3-05 | 59 只逐日覆盖明细：快照行或明确原因；检查空账本 JSON 为 null。外国五只即使算出分数也不能交易。 |

关闭不变量 I02/I03/I04/I08/I09/I13。所有门禁均有正反断言：例如第 180/181 天、阈值等于/刚越过、允许的 A/拒绝其他规则、有效 0/缺项、外国/本土、健康已核验极值/原件不一致。测试不联网、不取系统时间、不用真实 key；LLM 不进入 M3。完成后运行 phase1-test/replay，删除本模块 13 条 pending，不改 milestones。

## 6. 待答复（仅必须停的问题）

### K01：账本/排名舍入与两套 golden 冲突

位置：README §3.3、FR-M3-03、Q-M3-8；Muse factor_framework_v3.py L40–48、paper_trade_2026.py L209–217。

已核对证据：合成 SYN-DEF 的 golden 质量=87.825、成长=59.766667、估值=50.506087、时机=72.704167、排名=66.730168；Muse weighted_book 明确 round(score,1)，排名也 round(...,1)。冻结 v18 中 AAPL 2026-02-17 为 90.5/83.7/52.8/74.7、rank=76.1。两者不能在同一舍入规则下同时按既定容差通过。

- A（倾向）：规则 A 的 legacy/fixed 共同保留 Muse 的账本/排名舍入节点，由需求方将合成 golden 及“阈值前不舍入”规定写成明确例外；其他中间量仍 float64。这样同一规则不因提取器改变算法。
- B：仅 legacy/v18 使用兼容舍入，fixed 使用全精度，并由需求方明确这项规则差异。

请裁定；开发不改标准答案，也不偷偷放宽容差。

### K02：估值 0 分和缺失值的真值判断

位置：M-21、M-17、README 缺数据约定；Muse paper_trade_v18_full30.py L61–72、paper_trade_2026.py L193–203。

源码将“估值为 0”与 None 一起按 100 参与进攻层条件；M-21 的文字则是估值 <45。M-17 还把缺失营收增速按 0 比较，可能额外产生“等价格”。这会改变规则 A 层级或标签，不能作为普通实现选择。

- A：两个提取器共同保留上述 Muse 布尔语义，作为明确的规则兼容例外；不向数据库写假 0。
- B（倾向）：真实估值 0 按 0，缺失比较不成立，两个提取器保持一致；需求方明确源代码例外。已检查 600 行冻结答案没有估值 0 的行，但这不足以替代边界规则裁定。

### K03：gate_pass 的跨模块含义

位置：M3 §4 列出 gate_pass，但 M-30–33 只定义 entry_pass，M4 另有组合/大盘闸门。

- A（倾向）：gate_pass 仅为 M-30 在 M-31 修正后的四本账门槛结果；entry_pass 再与 M-32、排除红线结合。M4 自行计算其组合/大盘闸门。
- B：gate_pass 表示 M4 闸门；则 M3 不具备该输入，应由 M4 存储，M3 字段保持 NULL。

请确认字段合同，避免下游把“账本过线”误读为“已批准下单”。

## 7. Muse 源码细节登记

以下全部固定为 `aacea04e4562f70854d69330fe724aa2799f2858`，文件均在 Muse 的 `code/`。仅作为公式参照，在 inves_cog 内独立重写。

| 细节 | 源码位置 | 核对结论 |
|---|---|---|
| 财报初始状态与生效 | [paper_trade_2026.py L60–83](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_2026.py#L60-L83) | 初始 2025-12-31；按 filed_date 推进，旧价格派生值每个状态清除后重算。本项目不重写提取器，只调用 M2。 |
| MA 与动量 | [同文件 L86–105](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_2026.py#L86-L105) | MA50/200 含当日、要求完整窗口；MA200 斜率与 20 个交易日前比较；mom3/mom6 是 shift(63)/shift(126)，不是取最后第 63/126 行。 |
| RSI | [factor_scorecard_v2.py L39–43](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/factor_scorecard_v2.py#L39-L43) | 14 日涨跌额分别简单滚动平均，非 Wilder/EMA；只有涨无跌为 100，全平产生无效值，按缺项处理。 |
| 量能 | paper_trade_2026.py L91、L102–103 | 20/60 日平均成交量之比；上涨量按 close>=open（平盘计上涨），近 60 日上涨量/总量。窗口含当日。非上涨日的贡献为 0，不是把缺失成交量存 0。 |
| 波动与回撤 | paper_trade_2026.py L104–105；[paper_trade_v18_full30.py L185–212](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L185-L212) | vol20/60 均为简单日收益样本标准差 ddof=1 ×sqrt(252)×100，含当日；drawdown252 含当日，完整 252 日窗口；分层用 vol60，缺时回退 vol20。 |
| 当前价格派生 | [paper_trade_2026.py L109–125](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_2026.py#L109-L125) | 正 EPS 才算 PE；市值=股数×当日价；PS=市值/营收；FCF 收益率可负；PEG 仅正营收增速。不能沿用初始日估值。 |
| FCF/净利润、EPS 增速 | [screen_asof_2026_01_01.py L154–182](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L154-L182) | NI<0 仍计算 FCF/NI；NI=0 或缺失则缺项；不擅自统一 NI<=0 全部清空。EPS 增速要求当前/上一 TTM EPS 都>0。由 M2 返回，本模块只消费。 |
| 插值和端点 | [factor_framework_v3.py L28–48](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/factor_framework_v3.py#L28-L48) | numpy.interp 分段线性，区间外取最近端点；None/NaN/Inf 无分数；0 分有效；有效权重重配，全空为 None。账本 round(1) 冲突列 K01。 |
| 账本曲线及权重 | [paper_trade_2026.py L127–179](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_2026.py#L127-L179) | 质量 25/25/25/15/10、成长 40/25/25/10、估值 35/25/20/20；逐曲线对应现有 interp golden。 |
| 时机内层 | paper_trade_2026.py L149–173 | 趋势三项、动量两项、量能两项、位置/RSI 两项、波动/回撤两项先等权平均，再以 35/20/15/20/10 合账；不按子项个数加权。fixed 缺项按 Q-M3-6 重配并保留原因。 |
| 过期/拆股 | paper_trade_2026.py L125、L146–147、L181–187 | 营收期末距信号日严格>180自然日才过期；过期只清质量/成长/估值。拆股疑似只清估值；legacy 保留其源判断，fixed 消费 M2 状态。 |
| 红线、排名 | paper_trade_2026.py L189–217 | M-18 两条件都严格大于；M-16/17 不排除；rank 权重固定25/32.5/25/17.5，不使用 classify 行业权重。源码缺值真值语义见 K02，rank 舍入见 K01。 |
| 分层优先级 | [paper_trade_v18_full30.py L61–72](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L61-L72) | 质量/成长缺失不分层；先进攻、再防守、最后普通。未盈利要求 NI 与 FCF 都严格<0；实际波动输入是 vol60 回退 vol20。 |
| 分层重估 | paper_trade_v18_full30.py L193–213 | 新财报状态到达或层级尚为空时重估；即使财报数值没变化，新的生效状态仍触发。日常价格变化不触发重分层。 |
| 确定性 | [同文件 L75–84](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L75-L84) | 按 M-25 逐项加点，负 EPS 增速减 1；缺失不加减；4/2 为高/中边界；本项目同时暴露点数。 |
| 持有资格 | [同文件 L87–109](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L87-L109) | 六项满分实际合计 90，不归一化成 100；缺项保底依次8/0/8/8/8/5，真实0与缺项分开。hold_ok>=55。 |
| fund_bad 与跑道 | [同文件 L219–224](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L219-L224) | fund_bad=资格分<40，或营收季度同比<0、毛利变化<0且conversion缺失/<0.3；FCF缺失或非负跑道为真，负FCF而cash缺失则不能证明跑道，判否，不将cash存0。 |
| 入场与 M-31/32 | [同文件 L225–241](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L225-L241) | 按三层45–48行实际门槛；成长>=70且进攻才修估值、上限65、不改原账；负FCF进攻要求增速>=30和现金>=1.5倍烧钱；缺所需字段不能通过；M-18由M4另行过滤。 |
| 连续过线状态 | paper_trade_v18_full30.py L193–202、L240–245 | 从0按完整日序累加，不过线归0；源实现MA200不足日直接跳过。回放预热与正式2026连续日计算分开，不能用抽样日直接累计。 |
| VIX 分位方法（归属边界） | [同文件 L157–163](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L157-L163) | Muse恐慌阈值是含当日252日窗口、min_periods=120、90%线性分位数，属于M4；不在M3实现，也不能误作M6“排除当日的百分位秩”。 |
| 常量的权威位置 | paper_trade_v18_full30.py L45–55 | 以执行常量而非脚本旧说明头为准：cap12/12/8、首笔50/40/30、预算30/30/40、buffer1.25、只数4/6/6。 |

## 8. 已自行决定与遗留依赖

- 工程目录拟放 `src/inves_cog/scoring/`；计算为 float64，API 只序列化有限值和 null，内部数值异常有明确原因。舍入节点等待 K01，不能用展示四舍五入替代规则裁定。
- 将 Muse 的中文层级/字段名与本项目枚举显式映射；不改变数值、红线或入场结果。已有 golden 不新增供应商请求，长回放使用本项目 M2 的 legacy。
- D-17 与 D-21 必须在 M3 提交验收前完成：先核对申报原件并恢复 LITE 的已验证极值资格；补齐2015年以来历史财报事件、逐份核对索引 Accepted，并查明 XOM 的发布方式。它们在 M1/M2 收尾分支交付，不混入本次 kickoff。
- M1/M2 真实 live 冒烟仍须实际通过后才退出 pending；明早 AC-M1-02b 只认准时真实 job_runs。当前不能写成模块已关闭，不改 milestones。D-14 已有嵌入记账实现及真实记录，按实核验；D-15第二次完整一致预期采集期限为M5前。
- 收到答复后按“失败测试/夹具独立提交 → 实现 → 自测证据”推进；本草稿阶段停在复述单。
