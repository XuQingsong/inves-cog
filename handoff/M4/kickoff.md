# M4 开工复述

模块：M4　文档版本：M4 v3（2026-10-16）　复述人：A 线 Codex　日期：2026-10-16

依据：main `a6dfeeefe784f51b4e5155b96712a7320bc9d4a1` 的 A-004、整体需求、阶段任务书（含 §4.6–4.8）、README §3–4/§7.1、T04、M4 v3 全文、规格 §9.8–9.15、§11.1–11.2、§12.5、§16.6。T04 尚保留“连续 5 日真实运行”的旧表述，本次按 A-004 和 M4 v3 Q-M4-6 的明确更新执行：最近 5 日历史计划是阻塞证据，1 次真实准时调度为运维确认、不挡合并；不自行修改任务卡。

本 PR **只提交本复述单**，不包含 M4 实现、测试、迁移或服务配置。答复后再提交失败测试和夹具，然后实现。

## 1. 我理解本模块要做的事

| FR | 实现范围与边界 |
|---|---|
| FR-M4-01 | 实现主候选、价格退出后的回补、进攻层优先、同日名额/额度占用，逐个生成新开仓意图；不把 M3 的 gate_pass 当组合许可。 |
| FR-M4-02 | 确定性决定首笔，回补折扣、低仓位补偿、Form 4 加成和追高减半按源码顺序；信号日检查额度，次日开盘计算成交数量。整数股和费用边界见 K02。 |
| FR-M4-03 | 先处理持仓的确认加仓、确认补满，记录 first_frac、filled_frac、入场财报状态、连续过线和交易日龄。 |
| FR-M4-04 | 逐股票按 M-50→M-51→M-52→M-53→M-54→M-55→M-56 的短路顺序卖出，M-57 恢复阶段；组合风控独立排队的顺序也登记，不能误删 golden 中同日多笔。M-58 范围冲突见 K01。 |
| FR-M4-05 | 核心仓波段、观察名单波段、深跌两次确认、第二笔、止盈止损和转核心仓；维护波段股数、笔数和确认状态。 |
| FR-M4-06 | 实现 SPY 黑天鹅、权益高水位回撤刹车、VIX 恐慌闸门及解除条件。VIX 按信号日可见数据计算，不能用 M6 的另一种百分位秩替代。 |
| FR-M4-07 | 信号收盘→下一交易日开盘，稳定排序先卖后买，每笔成本 0.1%，整数股；原始开盘价参与计算，价格显示才保留两位。I07 的阈值/费用冲突见 K02。 |
| FR-M4-08 | 每个订单记录 M 编号和中文解释，解释交易规则而不掺估值区间；取消、跳过和持仓状态保留规定 N 代码和具体原因。 |
| FR-M4-09 | 只有 inves_cog.trading.engine 的受控写入口可以生成/变更订单；其他业务包无写入口，数据库仅既有 role_trading 可写。 |
| FR-M4-10 | 按交易日和上市日确定成员，上市前不产生状态、候选或交易；外国只观察标的沿用 M3 tradable，不擅自纳入可买集合。 |
| FR-M4-11 | 读取覆盖层版本、生成时间与冷静期；过滤新买/加仓，已有未成交买单移入 cancels；拒绝增加数量、放宽和卖出请求。缺失/过期不伪装健康，但不阻塞规则 A。 |
| FR-M4-12 | 可交易集合的有效行情覆盖率低于 95% 不发布、不生成新订单，列出缺失代码；单股票缺行情不编价。 |
| FR-M4-13 | 日常纸面用 fixed，v18 用 legacy，两者执行同一份获批规则 A；硬锁 rule_set=A。 |
| FR-M4-14 | 冻结输入→本项目 M2 legacy→已验收 M3 score_history→独立重写的 M4 引擎，回放 2026-01-02–10-07，逐笔及摘要对账。 |
| FR-M4-15 | 每日任务记录真实 job_runs；按美东 08:00 起读覆盖层、08:30 前发布（夏令时北京 20:00/20:30，冬令时按 README 顺延），不是硬编码北京时间。 |

## 2. 不做的事

不实现 A+、S10、固定百分比的 paper_tracker 卖出法、估值驱动仓位、M9 影子信号、M10 页面、第二阶段 59 只扩池收益基线或实盘交易。不改 M3 公式、M1/M2 采集、M6/M7；只消费已验收上游。覆盖层只读取，M9 未完成时注入本项目夹具，不写 overlay schema 或实现第二套覆盖层服务。

不运行、导入或复制 Muse 实现；固定源码只作为规则参照。docs/golden/milestones 只读；标准答案不是调参目标，差异不能靠改答案解决。

## 3. 输入和缺失处理

| 输入 | 合同与取数 | 缺失/时间边界 |
|---|---|---|
| 打分快照 | trading.daily_scores，读取 signal_date、extractor、rule_set、params_version、tech、四账、rank_score、red_lines、tier、certainty、hold_score、hold_ok、fund_bad、runway_ok、entry_pass、consec_pass、tradable、null_reason。 | 只取指定信号日/版本；缺账不能买，卖出按 M4 §6 只判所需字段齐备的条款。缺字段不补 0。 |
| 财报状态 | 既有 ingest.fundamentals.repository.Repository.state_asof(ticker, signal_date, extractor)，只读 fundamentals.fin_state。用于新一期财报识别、rev_accel 等 M4 所需字段；entry_filed 作为本项目持仓状态，不改 M3 表。 | 不使用信号日之后的财报。成交日分层的 Muse 例外需 K03 裁定。 |
| 行情/日历 | 日常只读 ingest.bars_daily 的信号日及更早 OHLC/技术历史、SPY；已知下一日开盘价仅用于实际成交入账。XNYS 日历统一交易日索引、半日市与 DST。 | 缺价不能成交，保留待处理和 N8；盘前不能读取尚未发生的开盘。账本在开盘数据真正到位后对账，不伪造任务发生时间。 |
| VIX | 日常 ingest.macro_observations：VIX_CBOE 主、VIXCLS 备用，按可见版本和观察日期取值；记录实际使用的 series/source 与日期。 | 备用也没有当天所需观察时标 VIX 缺失、不判恐慌，不拿前日值顶替。分位样本不足同样说明。 |
| Form 4 | 日常只读 ingest.form4_events：code=P，按 filed_at 在信号日之前 90 个自然日（含边界），高管优先；不按交易日或 Form 4 交易发生日计。 | 缺事件表示没有得到加成证据，不编造买入；覆盖缺口单独标注。v18 不读 R7 Form 4，见 Q-M4-5。 |
| 覆盖层 | 注入 overlay.current(trade_date) 的读取器；规范化规格 §11.1 的 version/generated_at/tickers 到 M4 所需 cooling_off、事件 id 和版本。 | generated_at 早于目标交易日美东 06:00（夏令时北京 18:00、冬令时 19:00）标 stale；不可用标 missing；保留版本与错误，不新增跨模块接口。 |
| 成员 | config/universe.yaml、M1 日线首个可交易日期及已知上市日；日常 59 只表中只有当日可交易者进入覆盖率分母。 | 上市前不存在；无法证明有可交易数据时标注缺口，不能凭今天的成员倒灌历史。 |
| v18 | load_golden 读取 v18/prices/*.json.gz、vix_close.csv、companyfacts_used.json、paper_trade_v18full_trades.json；30 份原始 companyfacts 使用 M2 已冻结夹具并校验未压缩哈希。 | 仅用这些冻结输入，不读生产 bars_daily、R7 或实源 API；通过已验收 M3 逐日打分，不能只读 20 个抽样日充当整段信号。 |

已通过 load_golden 预读标准答案：90 笔、终值 1,494,527.34、收益 49.45%、最大回撤 −12.64%；这只是**答案预检，不是本模块已跑通的回放结果**。需求方已完成冻结输入生产和精确复跑（Q-M4-5），本项目不重新生成这套输入。内部人两份文件不在冻结输入里，按已明确“不影响这 90 笔”的合同回放，不补造文件或调用 Muse。

## 4. 输出、表与迁移计划

代码拟为 src/inves_cog/trading/engine.py（唯一订单写入口）、execution/ 下的纯规则/组合状态、repository/service/cli、只读覆盖层适配，以及 tests/m4/。参数新增 config/params/p-2026.10/m4.yaml；既有 rule_a_v18.yaml 只读并复用校验，层名 defense/normal/attack 与 defensive/normal/aggressive 显式映射。

本模块只新建 **trading** 下三张表，迁移暂定 **migrations/phase1_m4_0001_paper_ledger_orders_plan.sql**（当前无 M4 编号，提交前再核对，避免重号）。不改既有 M0/M3 迁移，不迁移共享生产库；后续合并和明确部署任务后再执行。

| 表 | 拟存内容与幂等边界 | 消费者 |
|---|---|---|
| trading.ledger | 按 portfolio_id、交易日/阶段、extractor、rule_set、params_version 保留快照；现金、权益/高水位、持仓整数股/均价/当前和入场层级、first_frac/filled_frac、stage/clear_streak、入场/卖出/波段交易日索引、entry_filed、退出类型、波段股数/笔数、首次止跌、黑天鹅及 dd8/dd12 状态。 | M4 恢复/重跑；M5/M9/M10 只读。 |
| trading.orders | 模块文档的全部字段，加订单状态及内部意图证据；order_id 包含账户/信号日/执行序号/规则，允许同股同日多笔；pending/filled/canceled/blocked 可追溯，不能用一天一股唯一键吞掉订单。 | M4 唯一写入口，M10 展示与逐笔对账。 |
| trading.plan | 按组合/目标交易日/版本存完整计划 JSON 和真实发布时间；历史回放与日常 portfolio_id 隔离。包括 orders/cancels/skips/holdings、覆盖率/缺失、gates 及 VIX 来源、持仓和预算。 | M9 读取基础计划，M10 渲染。 |

金额美元、数量整数、数值 float64；未知的成交价、成交股数和成本在成交前为 NULL，notional_est 表示估计金额，不把信号日价格冒充次日开盘成交价。内部意图保存 target fraction/value 和数量上限，开盘才落实际股数；订单取消后不会在账本成交。日常和回放的账户状态分开，重跑同一键不重复扣现金/手续费。

job_runs 沿用 M3 的两连接做法：交易连接只写 trading；既有运营连接调用 M1 OperationalRepository/JobRunner 记运行和健康，不给 role_trading 增加 ingest 写权限，不改 ingest 表或客户端。订单理由只包含 M 编号和中文规则说明，不读估值区间；跳过/取消按 N3/N4/N5/N7/N8 及具体规则记理由，M-58 的冷却记录同时保留规则编号。

## 5. 验收证明与中期检查点

| AC | 计划证据 |
|---|---|
| AC-M4-01 | 12 项 blocking：test_order_reason_tokens、test_orders_only_from_engine、test_fill_timing_and_cost、test_membership_asof、test_sell_priority、test_panic_gate_scope、test_cooldown_m58、test_overlay_cooling_skip_and_cancel、test_overlay_missing_marked、test_plan_unpublished_low_coverage、test_plan_json_contract、test_vix_missing_not_panic。每个过滤/门禁均有应拦及不误伤两侧用例，边界含相等、空值、半日市/DST。 |
| AC-M4-02 | test_v18_replay：完整冻结区间收益/回撤与 90 笔对比，目标逐笔一致；最低门槛仍为收益 ±1pp、回撤 ±0.5pp、日期/代码/动作匹配 ≥95%，股数同时报告。 |
| AC-M4-03 | 一份最终 diff.json/报告，按标准答案和实际逐笔对齐；每个差异仅能归浮点、数据版本、已登记 Muse 细节，禁止第四种解释。没有差异也输出零差异报告。 |
| AC-M4-04 | test_amd_entry_2026_01_12：检查对应信号日、次日成交、层级、整数股和触发规则，不把日期标签当实现。 |
| AC-M4-05 | 最近 5 个真实交易日按当时已公开数据连续回放计划，保存每一天输入 as-of/版本/订单/撤单/跳过/持仓原因；另记录 1 次调度器真实按时触发并在美东 08:30 前发布（运维确认，不阻塞合并），不为证明规则去等待 5 天。 |
| AC-M4-06 | 提供上述 5 日中至少 3 日的原始输入和逐动作规则证据，供需求方每天至少抽 2 个动作/跳过手工复核；没有人为造单充数。 |
| AC-M4-07 | 合成/录音夹具演示：先有待成交买单，再来有效冷静覆盖，订单移入 cancels；次日即使开盘跌穿仍无成交；同时证明非冷静股票和卖单不被误取消。 |

第 15 个测试 test_paper_live_smoke 仅在明确 -m phase1_live 且 INVES_COG_LIVE=1 时联网，不进 CI；真实通过才删除 pending。本模块全部 15 个名字不变，不改其他模块 pending 或 milestones。

**中期检查点 handoff/M4/checkpoint.md**：先交 2026-01-02–03-31 的本项目引擎 v18 冻结回放，附收益、最大回撤、交易数/匹配率、完整逐笔列表、差异报告初稿及每个差异所属类别；说明这是冻结夹具回放，与日常 5 日真实输入回放、调度证据分别标明。先让端到端链路成立，再补齐边界。该检查点是下一阶段开发产物，本次不生成或伪称已有结果。

收到本复述答复后：先单独提交失败测试和自建夹具（登记 MANIFEST/CHANGELOG）→ 独立实现 → 交中期检查点 → 全仓 blocking/replay 与自测。完成后写 self-test.md，PR 转正式“[M4] 提交验收”；不自动合并。

## 6. 疑问分级

### 必须停：需要需求方答复的三项

**K01｜M-58 的“任何卖出”与已冻结 v18 的波段买入冲突**

位置：规格 §9.10 M-58、M4 test_cooldown_m58；下表源码 L303–309、L535–538、L561–583。源码只在核心加仓检查 last_sell_idx；波段买入不检查这项，波段卖出也不更新 last_sell_idx。不是假设：通过 load_golden 读取 90 笔后，MU/MRVL 在 **2026-07-17 回撤减仓后 07-20 波段买入**，MRVL 在 **08-18 分批止盈后 08-19 波段买入**，均只隔 1 个交易日。

- A（倾向，为保持同一规则 A 与 90 笔一致）：把 v18 现有冷却适用范围登记为兼容例外，M-58 的普通新开/回补/核心加仓按源码检查；波段按各自 last_swing/last_exit 间隔。测试明确“适用买入应拦、波段合法路径不误拦”。
- B：所有卖出后 10 日禁止所有买入，两个提取器共用此修订；这会改变已冻结标准答案中的上述交易，须需求方明确如何处理 v18 目标，不能开发自行改 golden。

**K02｜整数股后的最小成交额和手续费现金边界**

位置：I07、FR-M4-07；源码 L316–319、L330–334、L353–367。实际先 spend=min(目标金额, cash)，再 floor(spend/open)，但用取整前 spend 比较 0.5% 权益，手续费另外扣；未先从现金预留手续费。合成边界可直接证明差异：权益 100 万、spend=5000、开盘=3000 时源码买 1 股，实际名义金额 3000 < 5000；现金恰好花尽时手续费可能造成少量负现金。

- A（倾向，为兼容重写）：将上述计算节点明确登记为规则 A 例外，0.5% 检查按源码 spend、手续费单独扣，并在账本如实显示现金；不把这个例外扩散成缺数据补值。
- B：按实际整数股成交额再检查 0.5%，且扣费后现金不得负，买股数改为可覆盖费用的整数。安全口径更严格，但会改变源码的边界交易结果，须明确批准，不能开发悄悄改成另一套算法。

**K03｜成交日分层是否使用尚未完成的当天打分快照**

位置：规格 PIT/I08、M-35；源码 L334–355。Muse 在次日开盘处理 buy_to/buy_watch 时取 signals[t].get(成交日) 的 tier，缺失才回退订单 tier。该 signals 预先用成交日整日技术/财报状态算出，可能包含开盘时未知的新分层；若下一日分层变化，单票 cap 和整数股都会改变。

- A：两个提取器都保留该 v18 兼容行为并明确登记 PIT 例外；需要说明日常纸面在开盘前无法获得当日完整分层时的合同，不能宣称它仍是严格实时 PIT。
- B（倾向）：成交沿用已公开的信号日订单 tier；日内后续层级变化到下一信号处理。符合实时 PIT，但潜在 v18 差异必须先由需求方裁定。本次只报告源码事实，不声称 90 笔里已发生了这一差异。

这三项影响规则 A 交易行为/标准答案解释，按阶段任务书 §4.6 属必须停。本次按 A-004 只在 kickoff 中列清单；答复前不写实现或测试，不修改 docs/golden。

### 已自行决定：不等待的工程与证据事项

- 全部引擎放 trading 包内，复用 M3/M2 公共读取接口；不新建顶层 execution 包或复制评分器。缺 M4 辅助连续计数时，在 M4 自己的状态中按完整日序派生，不改 M3 表。
- 覆盖层采用规格 §11.1 已有顶层时间/版本和 tickers 合同做读取适配；无 M9 时注入夹具。未生成的成交数量/价格保留 NULL，notional_est 明示估算，避免未来价格泄露。
- 迁移只写 trading，业务账户/回放账户隔离、订单以序号幂等、计划保留版本。初始 v18 资金固定 100 万；日常纸面初始账本拟同额配置并标明启动日，不把最近 5 日回放当第二阶段扩池收益基线。
- 测试不启本地 TCP；时钟一律注入。金标只用 load_golden；新增自建夹具按 Harness 冻结登记，不复制真实 golden。
- M4 参数放独立 m4.yaml，既有冻结常量不增删；数值不为展示而提前取整。只有本表已登记/待答的 Muse 舍入节点作为兼容细节。

## 7. “以 Muse 源码为准”的计算细节登记

固定仓库 XuQingsong/muse，提交 **aacea04e4562f70854d69330fe724aa2799f2858**；以下路径均为 code/paper_trade_v18_full30.py。源码仅只读，下面是语义登记，不导入、不执行、不拷贝代码。K01–K03 未裁定处不会擅自成为实现。

| # / 对应规则 | 源码位置 | 要保留或待裁定的细节 |
|---|---|---|
| 01 / 常量、M-24 | [L39–55](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L39-L55) | 初始现金 100 万；费率 0.001；cap 12/12/8%、首笔 50/40/30%、预算 30/30/40%、相对缓冲 1.25、层只数 4/6/6；不能按旧文件头 15/12/5% 重写。 |
| 02 / M-35 | [L112–118](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L112-L118) | 高 min(0.75,base+0.20)、中 min(0.65,base+0.08)、低 max(0.20,base−0.08)，依次调整。 |
| 03 / M-36 | [L121–154](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L121-L154) | 只取公开市场 P、filed 存在的记录；90 自然日左右端含信号日/第90日；任一高管 1.35，否则内部人 1.20；回补不加成，最高 0.80。 |
| 04 / M-63 | [L157–163](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L157-L163) | 升序 VIX 收盘序列，**含当日** rolling(252,min_periods=120).quantile(0.90)，默认 linear，VIX>=阈值为恐慌；缺样本不为真。与 M6 排除当日的百分位秩不同。 |
| 05 / 交易日龄 | [L169–190](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L169-L190) | 行情日期并集作为交易日序列；持有、冷却、确认用全局交易日索引差，不用自然日或某只股票缺价后的行数。 |
| 06 / M-35、I07 | [L264–280](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L264-L280) | equity=cash+持股×价格；eq_open 在执行队列前算一次，用所有持股的当日原始开盘估值；先卖后买稳定排序，相同方向保留生成次序。 |
| 07 / 整数卖股 | [L281–315](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L281-L315) | 全卖取全部整数股；比例卖 int(shares×frac)，正数向下取整，0 股不成交；波段卖只扣 swing_shares。部分卖先扣波段股数并截下限 0。 |
| 08 / M-58 状态 | [L281–315](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L281-L315) | 全卖/比例卖记录 last_sell；清零记录 last_exit 和退出类型；波段卖只记 last_swing、不写 last_sell。此与“任何卖出”边界关联 K01。 |
| 09 / 波段数量 | [L316–352](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L316-L352) | 核心波段/观察仓按信号日固定 value 与现金取小，再 spend//open；成交后均价按未含手续费的股价加权、成本另记；更新波段股数、笔数和日期。I07 边界见 K02。 |
| 10 / M-35 目标买入 | [L353–382](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L353-L382) | cap_val=cap×固定 eq_open，目标=目标比例×cap_val−旧股开盘市值，追高先将差额减半；随后 min(delta,cash)、floor(spend/open)。成交日 tier 见 K03。 |
| 11 / 已投比例 | [L368–380](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L368-L380) | filled_frac 用订单目标累计，半笔用目标×0.5；新增取 max，不按收盘市值每天重置；first_frac 保存原目标而非扣减后的实际市值比例。 |
| 12 / 价格精度、成本 | [L281–382](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L281-L382) | 现金按未舍入 open、整股名义金额及买1.001/卖0.999 更新；只有输出价格/名义金额 round(...,2)，不是先把价格四舍五入再成交。 |
| 13 / M-62 高水位 | [L385–411](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L385-L411) | 当日已成交后收盘权益入曲线，高水位含当天；dd<=−8 且未激活/非恐慌触发进攻减1/3，dd>−4 才解除；dd12=dd<=−12 或旧激活且dd<−6。 |
| 14 / M-61 | [L394–418](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L394-L418) | SPY 1日用[-2]、5日用[-6]；阈值含等号；距上次触发必须>10，swan_until=i+3，i<=swan_until 禁买；恐慌只阻止减仓，不取消黑天鹅禁买。 |
| 15 / 风控队列顺序 | [L403–430](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L403-L430) | 先 dd8 再黑天鹅，再个股卖出链；组合减仓与个股链可同日排队。golden 2026-07-17 AMD 确有“回撤刹车减仓+分批止盈”两笔，不可用一股一天一单去重。 |
| 16 / M-24 额度 | [L420–426](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L420-L426) | limit=层预算×1.25×收盘权益；非进攻且组合投入<85% 时，另借尚未用进攻额度的75%；投入比按当前现金/权益，不把当日待卖当现金。 |
| 17 / 持仓层级/高点 | [L433–450](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L433-L450) | 个股信号缺失整条跳过；有信号按当前层级退出线；peak_price 为持有期间最高收盘（初值买入开盘），不是日内最高。 |
| 18 / M-50、M-51 | [L443–459](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L443-L459) | M-14/15、层质量/成长、进攻营收/跑道、fund_bad 触发逻辑死亡优先；再判进攻 price<=峰值×0.60 且破200线；一条命中不再查下面个股卖出。 |
| 19 / M-52 | [L460–473](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L460-L473) | 纯波段先过死亡/灾难检查，再按 dev50>=动态阈值止盈、price<=均价×0.82 止损；然后直接结束，不走 M-54–57。 |
| 20 / M-53、M-54 | [L474–487](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L474-L487) | 核心波段止盈优先翻倍锁利；进攻阈值 clamp(.40vol,10,18)，其余 clamp(.32vol,8,14)；翻倍锁利要求>=20 交易日、阶段0，卖25%。 |
| 21 / M-55、M-56 | [L490–514](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L490-L514) | 破位先于警戒，持有>=10且stage<2；阶段在生成信号时置2/1；普通警戒要求state_idx>entry_state。两者都被恐慌挡；等于200线不算下方。 |
| 22 / M-57、M-59 | [L488–522](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L488-L522) | 不警戒、在200线上且entry_pass 连续5/3/5日才清stage；中断归0；不因涨超预算或普通分数回落卖出。 |
| 23 / M-40 转核心 | [L524–540](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L524-L540) | 转核心先发生于后续 sold/过热/冷却判断；filled_frac=min(.6,市值/(cap×eq_close))，entry_idx重设；确定性沿用入场保存值，不每日换成新确定性。 |
| 24 / M-40 分级 | [L541–560](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L541-L560) | first+.30 和满额比较各减1e−9；确认加仓与补满用 if/elif，同日不两步跳满；N=3/5，回踩可代替等待；新财报与持有15/连续10触发补满。 |
| 25 / M-60 核心波段 | [L561–583](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L561-L583) | 弱势带两条件与MA200>-8；股数/层额度按信号收盘检查，金额固定 .2×cap×eq_close；同股的普通加仓与波段可同时生成，golden 中 AMD/MU/JNJ 均有这种双单。 |
| 26 / 观察波段资格 | [L584–605](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L584-L605) | 按信号字典原顺序，已有纯波段+当日待新建最多3；普通/防守资格>=60，进攻>=65、vol<=60且跑道够；accel缺失不过度判坏，已知<-10才拒绝。 |
| 27 / 两次确认 | [L606–620](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L606-L620) | 至少12条历史，5日涨跌shift5、最近10条收盘最低（非low字段）；深跌<=−35，首次/超过15日/低于首次97%重置，<5日继续等，5–15日达标才买并清记录。 |
| 28 / 波段金额/补仓 | [L621–646](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L621-L646) | deep=MA200偏离<-8；首笔2/3%或2.5/4%，上限6/8%；第二笔dev50>=0、间隔>=5，目标差额<=0.5%权益则跳过（此处严格大于，区别成交门槛的>=）。 |
| 29 / M-34 排序 | [L647–664](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L647-L664) | 主候选按(rank,ticker,False)逆序（同分ticker逆序），再拼回补逆序列表、rank−3；最后稳定分出进攻优先，其余保持原顺序，不把两张列表重新全局排序。 |
| 30 / M-34 名额 | [L665–672](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L665-L672) | 总只数用已有positions+pending buy_to笔数判断<12，层只数逐笔加；防守主候选资格>=55；dd12仅许防守。不能偷偷按不同去重口径重排。 |
| 31 / M-35–37 顺序 | [L673–691](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L673-L691) | 回补先 round(first×.8,3)，低投入补偿后再内部人；额度检查先用未减半 first_val，开盘执行才追高减半；planned_mv 只对本轮新开仓累加，并不把所有波段/加仓意图统一重算预留。 |
| 32 / 验收摘要 | [L693–713](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_v18_full30.py#L693-L713) | 回撤取收盘权益相对其累计最高的最小值；累计收益按最终收盘权益/100万；最后一天产生的待单不虚构区间外成交；均价/费用与展示字段分开对账。 |

## 8. A-004 服务核验和前序交接

需求方已把 A-003 的最后两项证据接走，本线不再手动运行它们。PR #10 已由需求方合并为 `61a97e139d80c1b43b4a5a72b30c7f2fa678483a`；开始 A-004 后按明确授权把 Mac 主仓库快进到最新 main `a6dfeeefe784f51b4e5155b96712a7320bc9d4a1`，未编辑 docs。

实际重启：**2026-10-16 13:23:52–13:23:58 北京**（05:23:52–05:23:58 UTC）。Supervisor scheduler：PID 14313→51341；watchdog：98185→51364；再次核对均 RUNNING，模块路径和文件 blob 与该 main 相同。原任务参数、登录自启、自动拉起及 caffeinate 保留；embedding 已退出，未重新拉起，也未手动执行任何采集、迁移、回填或用量调用。操作记录在仓库外 `/private/tmp/inves-m4-sync/service.json`，运行 SHA/时间同时写进 agent-status 的 A 线回报。
