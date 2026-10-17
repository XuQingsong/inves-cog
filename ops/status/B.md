# B 线回报

> 只由 B 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## B-008  进行中  2026-10-17 14:04 北京

- 草稿 PR #18 head `036acfc`。没有合并进 main。本地 `make phase1-test`：231 passed，18 deselected。
- 期限复验第 3 项：写明的期限早于事件起点时，这一条记为期限早于事件。10-01 不再当成 10-14 事件的最早期限，也不会立即结案。与起点同一天或更晚的日期仍可使用。
- 期限复验第 4、第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:54 北京

- 草稿 PR #18 head `bfb3f86`。没有合并进 main。本地 `make phase1-test`：230 passed，18 deselected。
- 期限复验第 2 项：财报周期或机制周期不是正整数时，这一条记为周期无效。负数或 0 不再收成起点当天，也不会在次日早晨结案。
- 期限复验第 3 到第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:45 北京

- 草稿 PR #18 head `c3dac17`。没有合并进 main。本地 `make phase1-test`：229 passed，18 deselected。
- 期限复验第 1 项：结案看美股反应日收盘，不看北京日历。10-14 开盘、财报周期 1 个交易日，期限是 10-15。北京 10-15 09:30 继续跟踪。北京 10-16 09:30 才按空记录结成已衰减·无影响，经营影响未证实。
- 期限复验第 2 到第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:34 北京

- 草稿 PR #18 head `b08cad9`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- Q-M8-16 第 2 项：二次命中只接受本次时点已经可见、并且对上预测指纹的材料。反应用预期残差和对照残差重算，不采用预填的命中。明天才发布、只谈 XOM 的新闻不会把 NVDA 记成确认。已经可见且对得上的后续材料仍可确认。
- 第 3 到第 5 项还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:26 北京

- 草稿 PR #18 head `ceca207`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 已看到 Q-M8-16。第 1 项：截止日取写明的日期，以及起点之后财报周期、机制周期和 20 个交易日里最早的一天。没到这一天就继续跟踪。到了这一天才走原来的经营门槛。空记录仍不写成经营影响已证实。报告留下这个日期。
- 第 2 到第 5 项还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:15 北京

- 草稿 PR #18 head `370575e`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 09:30 的跟踪任务更新三轨并做截止日结案。空记录仍不会写成经营影响已证实。12:30 的打标任务不推进生命周期，报告里的标的代码留给下游。日程没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:06 北京

- 草稿 PR #18 head `c52dbc0`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 收盘时段没有起点时，用当日交易所开盘（美东 09:30）。盘后仍用收盘时刻。已经写明起点的对象不改。五日冻结报告的可见标题和状态没有因此改变。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:58 北京

- 草稿 PR #18 head `110f769`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 有连接时，候选、跟踪和截止日本身就是被记录的操作。任务行先写入，阶段在这条操作里执行；阶段失败会把该行写成失败并重新抛出，而不是先跑完再记一个条数。没有连接时仍只执行、不写任务行。日程没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:47 北京

- 草稿 PR #18 head `2a080b2`。没有合并进 main。本地 `make phase1-test`：227 passed，18 deselected。
- 按 Q-M8-15 第 5 项：已有事件从原来的生命周期续上。假设中在四项同时成立时进入市场确认，供给等机制再进入基本面核查。截止日任务才按经营证据规则结案，空记录不会写成经营影响已证实。二次命中和多日跟踪留在同一对象上。影响分解和渠道写入报告。M7 的收盘和盘后对象用交易所收盘时刻作为起点。三个定时任务分别执行候选、跟踪和截止日，没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:39 北京

- 草稿 PR #18 head `f351333`。没有合并进 main。本地 `make phase1-test`：226 passed，18 deselected。
- 按 Q-M8-15 第 4 项：主链回捞改为实体、一跳图谱和批准向量的并集，再取前 40 条。只含 XOM 的新闻不会送给 NVDA。未批准的向量不进入。同一异常的两个候选按各自引用分开打分，缺输入的分项留空。没有新的补搜。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:26 北京

- 草稿 PR #18 head `01a5cdf`。没有合并进 main。本地 `make phase1-test`：225 passed，18 deselected。
- 按 Q-M8-15 第 3 项：候选的 affected 或说法的 claims 不是数组时，这一条记为结构不合格，不再当成合法的空结果。合法的空数组仍然是空。载荷里的候选和说法都写成数组。合法的 affected.basket_id 会留下来。没有改共享传输。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:14 北京

- 草稿 PR #18 head `6d9dd5b`。没有合并进 main。本地 `make phase1-test`：225 passed，18 deselected。
- 按 Q-M8-15 第 2 项：回放只处理当时已经发生的异常。10-16 才开始的对象不会在 10-13 或 10-14 写成已发现，也不会留下历史。已经发生的对象仍回放。新闻仍要到首次见到才进入报告。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:06 北京

- 草稿 PR #18 head `4144a2d`。没有合并进 main。本地 `make phase1-test`：225 passed，18 deselected。
- 按 Q-M8-15 第 1 项：同一异常的完整回捞、说法、候选、二次命中、影响分解、市场日、标的代码和报告再次保存改为更新原行。旧回捞留下，下一日跟踪另起一行。状态变了但没有完整审计条目时，拒绝这次变更，不再补一条只有旧状态和新状态的记录。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:57 北京

- 草稿 PR #18 head `8b0a66b`。没有合并进 main。本地 `make phase1-test`：224 passed，18 deselected。
- 五个交易日 2026-10-12 至 2026-10-16 的当时可见报告已冻结。截止点是每个交易日之后的第一个北京 12:30。10-14 的对象在 10-15 12:30 只能看见 CoreWeave，巴克莱和 CPI 仍是后补录。没有录音时状态是待分析。这批标题不是全池，也不是正式五日运行。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:48 北京

- 草稿 PR #18 head `6fddc08`。没有合并进 main。本地 `make phase1-test`：223 passed，18 deselected。
- 四个案例的固定输入可以写成规范载荷。文件字节的 SHA-256 就是计划里的哈希。`--capture` 留给需求方用已批准的客户端落录音。本轮没有调用模型，没有编造成功录音。一条失败不挡住下一条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:35 北京

- 草稿 PR #18 head `e173b23`。没有合并进 main。本地 `make phase1-test`：221 passed，18 deselected。
- 东芝完整解释报告和事件历史记在冻结夹具里。合成走查从已发现走到已验证，五步历史在再次保存后仍整段留下，不会收成一跳。三天跟踪都留下。经营证据标明合成。不是现场结论。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:23 北京

- 草稿 PR #18 head `6a5216d`。没有合并进 main。本地 `make phase1-test`：220 passed，18 deselected。
- 按 Q-M8-14 第 5 项：候选和说法的返回结构写在各自载荷里。机制只有五档。分数、置信度、证据、经营结论和假设标记都标明不由模型决定。整包结构不合格时这一条降级，下一条继续。没有改共享传输、模型或密钥。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:14 北京

- 草稿 PR #18 head `075c6c2`。没有合并进 main。本地 `make phase1-test`：219 passed，18 deselected。
- 按 Q-M8-14 第 4 项：有可见新闻时，一条入口把回捞、说法、候选、规则打分、解释报告、生命周期和保存串起来。模型自填的分数不会留下。调用失败的那条标成待分析，下一条继续。五日回放只使用当时已经见到的材料。三个定时任务有代码入口，日程本身没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:02 北京

- 草稿 PR #18 head `ab54313`。没有合并进 main。本地 `make phase1-test`：217 passed，18 deselected。
- 按 Q-M8-14 第 6 项：广域异常不再写入标的代码，仍可记下回捞和报告。一条广域被拒绝后，后面的异常继续保存。池内的 N1、N2、N6 照常写。六项证据都缺失时，分数留空，不进入假设，也不再除零。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:56 北京

- 草稿 PR #18 head `5c274e6`。没有合并进 main。本地 `make phase1-test`：217 passed，18 deselected。
- 按 Q-M8-14 第 3 项：同一事件第二次保存不再撞主键。生命周期写成新状态，原来的审计历史整段留下，同日再跑不会把历史清空。同日跟踪改这一行；下一日另起一行，前一日那一行还在。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:42 北京

- 草稿 PR #18 head `80009f7`。没有合并进 main。本地 `make phase1-test`：216 passed，18 deselected。
- 按 Q-M8-14 第 2 项：校验候选时不再保留模型自填的分数、置信度、证据、经营结论和假设标记。引用、机制、传导链和受影响标的仍留下。没有规则算出的分数时，不进入中高置信，也不写经营支持。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:32 北京

- 草稿 PR #18 head `db64e96`。没有合并进 main。本地 `make phase1-test`：215 passed，18 deselected。
- 按 Q-M8-13：严格回放和检索窗口在首次取得时间缺失或为空时，不再用发布时间补上。这种材料不进入当时可见，collected_then 和 vectors_then 都为假，模式记为未知。已有首次取得时间且不晚于时点的正例仍是当时可见。明确晚于时点的仍是后补录历史复盘。生产路径不接受案例模式。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:22 北京

- 草稿 PR #18 head `e750146`。没有合并进 main。本地 `make phase1-test`：214 passed，18 deselected。
- 超预期记录最新在前，最多四季。不足四季照存，不取平均。没有季度日期的不排进去。幅度沿用传入的百分数，不从实际值和预期另算。不算经营证据，不改基本面栏。没有传入时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:12 北京

- 草稿 PR #18 head `a2e4a98`。没有合并进 main。本地 `make phase1-test`：213 passed，18 deselected。
- 当年 EPS 分歧度是（最高 − 最低）÷ |当年 EPS|。绝对值小于 0.01 时分歧度留空，等于 0.01 时照公式算。缺最高、最低或当年 EPS，或出现布尔值时留空。不写成未下修或显著下修。不算经营证据，不改基本面栏。没有传入时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:02 北京

- 草稿 PR #18 head `8f67174`。没有合并进 main。本地 `make phase1-test`：212 passed，18 deselected。
- 近 7 天和近 30 天的修订广度是（上修家数 − 下修家数）÷ 覆盖家数。家数用传入的窗口计数，不在这里重数事件。覆盖为 0、缺任一数、或出现负数和布尔值时，广度留空。下修达到覆盖的 30% 也不在这里写成显著下修。不算经营证据，不改基本面栏。没有传入时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:52 北京

- 草稿 PR #18 head `3eafdf5`。没有合并进 main。本地 `make phase1-test`：211 passed，18 deselected。
- 一致预期快照按自然日回望 7、30、60、90 天，只取正好那一天的当季、下季、当年、次年。缺那一天、当天没有快照、或同一天数字冲突时，该格是缺失，不用邻近日期填。前值为 0 时变化留空。这里不写未下修或显著下修。不算经营证据，不改基本面栏。没有传入快照时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:42 北京

- 草稿 PR #18 head `0acc18d`。没有合并进 main。本地 `make phase1-test`：210 passed，18 deselected。
- 全量库从首次取得时间起保留 90 天全文，满 90 天仍保留，超过之后全文不再返回。摘要和向量在窗口内外都按原样保留，缺了不从全文补写。没有首次取得时间、时点类型对不上、或时点早于首次取得时，不写这条。过期后仍可检索。不算经营证据，不改基本面栏。没有传入材料时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:32 北京

- 草稿 PR #18 head `509e0335`。没有合并进 main。本地 `make phase1-test`：209 passed，18 deselected。
- 叙事扩散、资金延续、基本面为「开始修订」时，解读记成「基本面开始兑现」。缺资金状态时不写这条。资金是其他状态，或基本面写成局部支持，都不套这条。解读不改估值栏，报告估值仍是「不变 / 待基本面轨道」。不提高研究优先级，不写背离标签，不算经营证据，不改基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:22 北京

- 草稿 PR #18 head `cb30b28`。没有合并进 main。本地 `make phase1-test`：208 passed，18 deselected。
- 叙事衰减且基本面未变时，回吐比例小于或等于 0 记成「价格新均衡」，研究优先级提高。大于 0 且不超过 0.5 仍不命名。这条不发起回捞，不改研究排序，不写背离标签，不改估值，不算经营证据，不改基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:12 北京

- 草稿 PR #18 head `a42f2cd`。没有合并进 main。本地 `make phase1-test`：207 passed，18 deselected。
- 有一致预期时，NTM 另给一条市场侧金额，公式仍是前一日市值乘剩余收益再除以市盈率，只用 TTM 已经计入的成员。TTM 一个都计不上时，NTM 也留空。已计入的成员里只要有一个缺 NTM 市盈率、市盈率为 0、或不是有限数，整条 NTM 留空，不把其余成员加总。负的 NTM 市盈率照公式算。这条不改 TTM 金额，不写相容或部分相容，不算经营证据，不改基本面栏。没有传入成员时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:01 北京

- 草稿 PR #18 head `776de94`。没有合并进 main。本地 `make phase1-test`：206 passed，18 deselected。
- 资金轨道的 5 日和 20 日回吐比例沿用 r = 1 − 累计剩余 ÷ 首日剩余，两个窗口分开记。缺窗口、累计或首日不是有限数、或首日剩余为 0 时，该窗口是缺失，不写成 0。算出来等于 0.5、大于 1，也不在这里写成已消化、反转或其他资金状态。不改估值，不算经营证据，不改基本面栏。没有传入窗口时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:52 北京

- 草稿 PR #18 head `384d179`。没有合并进 main。本地 `make phase1-test`：205 passed，18 deselected。
- 覆盖自检记下每天的异常总数、找到候选的数量和原因未明的数量。原因未明比例是未明数除以总数。总数为 0、缺任一计数、计数不是非负整数、找到候选或未明多于总数时，比例是缺失。报警要至少三天，而且每一天的比例都严格高于前一天。只有两天、中间持平或回落、或其中一天比例缺失，都不报警。只给出报警标记，不写健康页。这条不算经营证据，不改基本面栏。没有传入覆盖天数时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:41 北京

- 草稿 PR #18 head `bb1c6f5`。没有合并进 main。本地 `make phase1-test`：204 passed，18 deselected。
- 共识度只写市场层。独立来源根按非社交材料去重计数，空名字不算，社交来源不计数，社交标成未接通。搜索倍数只在给出的数字都相同才记下，没有或互相不一致就留空，不合成一个高低档。卖方点评只认二三级点评；一级和四级点评不算卖方，缺等级是缺失。不写置信度。这条不算经营证据，不改基本面栏。没有传入共识材料时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:31 北京

- 草稿 PR #18 head `a0f832f`。没有合并进 main。本地 `make phase1-test`：203 passed，18 deselected。
- 研究资源按四档排序：持仓风险、近期候选、可改变驱动因子的关键环节、重大未知异常。持仓而且标明风险才进第一档，只持仓或只标风险都不进。候选要另外标明近期才进第二档；规格没有写近期是多少个交易日，所以不把没标明的候选当成近期。同一档保持传入顺序。对不上四档的排在最后，原因留空。这条不替换五档核验队列，不算经营证据，不改基本面栏。没有传入研究名单时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:22 北京

- 草稿 PR #18 head `8f06c82`。没有合并进 main。本地 `make phase1-test`：202 passed，18 deselected。
- 一手数据突变直接进入关注队列，不需要新闻。监控实体的榜单名次跳升严格多于 20 名，或搜索热度严格大于自身历史的 3 倍，或官网发布新产品，三条有一条即可。恰好 20 名或恰好 3 倍不算。没有监控实体的榜单和搜索不算。缺比较值、并且另外两条也没有写成否时，是缺失。这条不算经营证据，不改基本面栏。没有传入一手信号时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:12 北京

- 草稿 PR #18 head `67831a1`。没有合并进 main。本地 `make phase1-test`：201 passed，18 deselected。
- 新边的状态只写成候选，提议更高也不提升。价格共振或证据全是价格时，不能把关系升到已确立；原来的较低状态留下，缺状态是缺失。市场共振或市场叙事要改成经营传导，必须经营证据规则给出支持。反证、条件风险、只有价格、或缺时间或缺方向，连接类型不变。即使经营证据支持了传导类型，也不改基本面栏，也不把经营影响标成已证实。没有提议这三件事时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:02 北京

- 草稿 PR #18 head `9bc8208`。没有合并进 main。本地 `make phase1-test`：200 passed，18 deselected。
- 传闻被一级否认或矛盾之后，内容退出经营依据。只认传闻或四级材料；一级文件被否认不走这条。二级否认不算证伪。价格冲击原样留下，0 也算有记录，缺记录是缺失而不是删掉。来源根或信息编号留下，空字符串不算传播记录。这条不改基本面栏。没有传入这条时不写。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:51 北京

- 草稿 PR #18 head `6bcbe26`。没有合并进 main。本地 `make phase1-test`：199 passed，18 deselected。
- 丢弃抽检每周最多 20 条。只有标明已丢弃、并且有信息编号的材料才进入人工复核。没丢弃、没标明、或没有编号，都不占名额。同一编号只占一条，按传入顺序取满 20 条后停止。规格写的是随机抽样，但没有给抽样种子，所以这一刀不打乱顺序。后来标明重要的才计入漏检，没写这一栏是缺失，不是不漏。这些材料不算经营证据，不改基本面栏。没有传入丢弃名单时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:42 北京

- 草稿 PR #18 head `30540a9`。没有合并进 main。本地 `make phase1-test`：198 passed，18 deselected。
- 探索名额每天最多 3 条。只有同时标明低热度、并且标明涉及新机制、又有信息编号的材料才进入研究。缺任一标记、热度不低、机制不是新的、或没有编号，都不占名额。同一编号只占一条，按传入顺序取满 3 条后停止。这些材料进入研究，不算经营证据，不改基本面栏。没有传入探索名单时不写这条。每周 20 条丢弃抽检仍未做。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:33 北京

- 草稿 PR #18 head `a87d205`。没有合并进 main。本地 `make phase1-test`：197 passed，18 deselected。
- 四项市场指纹只用来排除对不上的解释，不指出唯一原因。暴露梯度沿用已有的秩相关，大于 0 才算暴露更直接的反应更强，成员少于 3 或秩相关算不出是缺失。无暴露对照沿用篮子特异性，预期篮子绝对残差均值大于对照才算对照表现不同，缺篮子是缺失。时序沿用时间对齐，早于或落在时段内算相容，晚于时段不算。反证响应沿用官方否认后的绝对值减弱，没有否认、不是官方否认、或缺剩余收益时这一项是缺失。某一项为假就列入不相容，缺失不算不相容。四项都通过也不写市场关联状态，不改基本面栏，不算经营影响。没有传入指纹时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:22 北京

- 草稿 PR #18 head `c00ab17`。没有合并进 main。本地 `make phase1-test`：196 passed，18 deselected。
- 三轨组合只认两行已经写明的对照。叙事衰减、回吐严格大于 0.5、基本面未变，读成冲击已消化。叙事衰减、资金延续、基本面冲突，读成价格和基本面背离。恰好 0.5 不算已消化。缺叙事、缺基本面、衰减而未变却缺回吐、或衰减而冲突却缺资金状态时，不写结论。扩散加延续加开始修订不写成兑现，也不改估值。这两行不提高研究优先级，不挑选背离标签，不改基本面栏。没有传入三轨时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:12 北京

- 草稿 PR #18 head `cee688d`。没有合并进 main。本地 `make phase1-test`：195 passed，18 deselected。
- 官方否认之后，后一次剩余收益的绝对值更小，才记反应减弱。一级否认或矛盾才算官方否认。二级否认、一级确认、缺任一侧剩余收益，这条不写结论。绝对值相等或更大，不算减弱。符号反过来但绝对值更小，仍算减弱。这条不改二次命中结论，不算经营证据，也不改基本面栏。没有传入否认时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:02 北京

- 草稿 PR #18 head `b092942`。没有合并进 main。本地 `make phase1-test`：194 passed，18 deselected。
- 鉴伪清单有八项：原始出处、完整表述、发布时间、首次取得时间、是否旧闻重发、传播关系、独立来源数、反方材料。缺项是未知。空字符串不算完整表述。来源根按去重计数，空名字不算。转载标记为假也算有数据。清单填满也不改真实性，不算经营证据，不改基本面栏。没有传入清单时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:52 北京

- 草稿 PR #18 head `0fc5472`。没有合并进 main。本地 `make phase1-test`：193 passed，18 deselected。
- 晚于异常起点的报道可以解释之后的传播，不能解释已经发生的下跌。同一时刻或更早的报道，这条两边都不下结论。缺发布时间或缺起点是缺失。这不改时间对齐的 1.0、0.7 和 0，也不改基本面栏，也不证明经营影响。没有传入时间时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:42 北京

- 草稿 PR #18 head `3c53a64`。没有合并进 main。本地 `make phase1-test`：192 passed，18 deselected。
- 链条上市场确认、消息真实性和盈利传导分开。市场确认不把未核实改成核实。核实或修订也不自动写成盈利传导。发现异常的那次价格不能再当作传导。证伪和部分核实仍缺消息真实性。三条都齐时仍不证明经营影响，也不改基本面栏。没有传入链条时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:32 北京

- 草稿 PR #18 head `d2c1281`。没有合并进 main。本地 `make phase1-test`：191 passed，18 deselected。
- 传闻拆成两件事。有来源根或信息编号时，发表本身进叙事。内容要有另一个来源根的一二级定量说法，并且变量相同、不是价格、热度、二次命中、共识或资金流，也不是反证，才算经营证据。同一来源根、三级来源、变量对不上，或传闻自己没写变量，都不算。一级说法本身不走这条。这条不改真实性，不改基本面栏，也不证明经营影响。没有传入传闻时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:22 北京

- 草稿 PR #18 head `9e98ddc`。没有合并进 main。本地 `make phase1-test`：190 passed，18 deselected。
- 核验队列按五档排序：持仓的经营证伪或风险越限、直接量化的经营变化、异常中的新解释、可能改变产业关系的新机制，其余是普通重复背景。同一档保持原来的先后。真实性不改变档位。一级来源即使传播为 0 也必须核验，四级来源传播再高也不因此核验。价格上的数量不算直接量化。这条队列不替换检索排序，不调用模型，也不改基本面栏。没有传入队列时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:12 北京

- 草稿 PR #18 head `b1cbc23`。没有合并进 main。本地 `make phase1-test`：189 passed，18 deselected。
- 弱信号在 30 个交易日内凑齐至少 3 个来源根和 2 个阶段，并且窗口内没有直接反证时，只提高研究优先级，并记一条补证任务。生命周期停在已发现，不进入假设中。缺比较日或缺阶段时是缺失。这一条不升级真实性，不改基本面栏，也不进覆盖层。没有传入线索时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:04 北京

- 草稿 PR #18 head `a27dc2e`。没有合并进 main。本地 `make phase1-test`：188 passed，18 deselected。
- 情绪放大只作描述。来源根数达到扩散（至少 3，并且至少是昨日的 1.5 倍）、搜索热度严格大于自身历史的 3 倍，或榜单名次跳升严格多于 20 名，并且基本面还没有局部支持、支持或冲突时，记为真。缺比较日或没有热度输入时是缺失。这一条不改基本面栏，不证明经营影响，也不把不相容写成情绪。没有传入热度时不写结论。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:53 北京

- 草稿 PR #18 head `8e539f9`。没有合并进 main。本地 `make phase1-test`：187 passed，18 deselected。
- 市场确认的独立证据不是价格。两个不同来源根、带监控实体的搜索热度突增，或一二三级点评，满足一条即可。同一来源根只算一次。四级点评和没有监控实体的热度标记不算。这一条单独成立也不能进入市场确认，另外三项仍要同时满足。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:42 北京

- 草稿 PR #18 head `7b80d3b`。没有合并进 main。本地 `make phase1-test`：186 passed，18 deselected。
- 一条当时可见的一二级定量说法把基本面写成局部支持。四级来源、没有数量、价格、热度、二次命中、共识，以及截止后才见到的材料，仍是待验证。局部支持不是支持，也不证明经营影响。估值倍数仍不写基本面栏。截止日已经写出的支持、冲突或失效保持不变。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:32 北京

- 草稿 PR #18 head `805deeb`。没有合并进 main。本地 `make phase1-test`：185 passed，18 deselected。
- 隐含幅度按渠道各写一条。缺金额的渠道是无法检验。单条渠道用同一套 1.5 和 5 的界限，不相容仍写不相容，不写成情绪。没有传入隐含幅度时不写渠道行。这不改变基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:21 北京

- 草稿 PR #18 head `632f8c2`。没有合并进 main。本地 `make phase1-test`：184 passed，18 deselected。
- 没有向量、或向量不是批准的模型和维度时，检索降到规则，报告写「向量检索降到规则检索」。没有传入向量材料时不写这句。这句不改变经营结论，也不改变市场分和基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:12 北京

- 草稿 PR #18 head `945a4c6`。没有合并进 main。本地 `make phase1-test`：183 passed，18 deselected。
- 由价格异常回捞来的后续信息，首次见到时间必须早于那次响应。同一时刻或更晚见到的不算，缺首次见到时间也不算。不是从价格异常回捞来的材料，仍只看发布时间和来源根。这不改经营结论。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:02 北京

- 草稿 PR #18 head `3ca9d66`。没有合并进 main。本地 `make phase1-test`：182 passed，18 deselected。新的检查在原有二次命中测试里。
- 二次命中按预期方向取号。上涨时剩余收益至少 +1 且对照篮子绝对值小于 1 才是命中，反方向至少 1 是反证。下跌把符号反过来。对照篮子自己也到 1 时不算命中。东芝合成走查的后续剩余收益改成与下跌方向一致的负数，结论仍是确认。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:52 北京

- 草稿 PR #18 head `85152d5`。没有合并进 main。本地 `make phase1-test`：182 passed，18 deselected。
- 解释报告把市场归因置信度和基本面成立度分开。市场分按最高候选：0.70 起为高，0.50 起为中，再低是低。供给、需求、竞争、客户融资达到 0.5 时，基本面先写待验证。估值倍数和不够 0.5 的候选不写基本面成立度。市场分高不能抄进基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:41 北京

- 草稿 PR #18 head `df013dd`。没有合并进 main。本地 `make phase1-test`：181 passed，18 deselected。
- 状态至少「观察到」但没有美元暴露的边，登记一条补暴露任务，原因是缺美元暴露。候选边不登记，估值倍数不登记。这条任务不把结论改成不相容，也不写金额 0。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:32 北京

- 草稿 PR #18 head `95ffffe`。没有合并进 main。本地 `make phase1-test`：180 passed，18 deselected。
- 隐含幅度证据分只认三档：相容 1.0、部分相容 0.6、不相容 0.2。无法检验是缺失，按剩余权重重配，不记成 0。情绪这两个字不进分数。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:22 北京

- 草稿 PR #18 head `29e521e`。没有合并进 main。本地 `make phase1-test`：179 passed，18 deselected。
- 市场归因至少为中的候选才登记指纹。字段是关联实体、预期篮子和方向、对照篮子。结论留在市场层。低于中、或不打分的默认候选不登记。后续信息要晚于起点并且实体相交才对得上这枚指纹。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:14 北京

- 草稿 PR #18 head `e874546`。没有合并进 main。本地 `make phase1-test`：178 passed，18 deselected。
- 渠道由机制决定。供给走供给/价格，需求和竞争走直接收入，客户融资同时走订单/积压和融资/对手方，估值倍数只有估值倍数。信源取引用里最高的等级。美元暴露只加总状态至少「观察到」的关系。分部收入用分部利润率，不退回公司利润率。缺利润率或订单缺兑现年数时结论是无法检验，不把缺项写成 0。不相容不写成情绪。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:03 北京

- 草稿 PR #18 head `5dbdbcf`。没有合并进 main。本地 `make phase1-test`：177 passed，18 deselected。
- 市场侧金额只加总 EPS 为正的成员：前一日市值乘剩余收益再除以 TTM PE。EPS≤0、PE 不可用、或只有总涨跌没有剩余收益的成员不计入。一个都计不上时结论是无法检验，不把金额写成 0。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:51 北京

- 草稿 PR #18 head `a34efe2`。没有合并进 main。本地 `make phase1-test`：176 passed，18 deselected。
- 篮子特异性是预期篮子绝对残差均值减去对照篮子，再除以 3，限制在 0 到 1。没有对照篮子是缺失。叙事证据按同时提到事件和受影响名字的独立来源根计数，同一来源根只算一次，5 个封顶。替代解释排除只减掉自身财报反应、8-K 指引或评级变化的成员，价格本身不减。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:41 北京

- 草稿 PR #18 head `1436f12`。没有合并进 main。本地 `make phase1-test`：175 passed，18 deselected。
- 暴露梯度用状态至少「观察到」的关系：直接 3、间接 2、概念关联 1，再和按预期方向取号的残差做 Spearman，负相关记 0。成员少于 3、残差缺失、候选或已退出的关系，以及暴露全部相同，都是缺失而不是 0。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:31 北京

- 草稿 PR #18 head `17dcffe`。没有合并进 main。本地 `make phase1-test`：174 passed，18 deselected。
- 标的代码只写在池内。广域不写。没有达到 0.5 的候选时，异常成员写成 N6。达到 0.5 的估值倍数写成 N2，同一名字不再写成 N1。供给要同时是叙事冲击且基本面未变才写成 N1，否则留空。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:22 北京

- 草稿 PR #18 head `dd9672d`。没有合并进 main。本地 `make phase1-test`：173 passed，18 deselected。新的检查在原有说法测试里。
- 说法抽取只接受前 40 条。已经有说法字段的材料不再送去抽取，空说法也算已经抽过。多出来的一条不会调用模型。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:11 北京

- 草稿 PR #18 head `9a26521`。没有合并进 main。本地 `make phase1-test`：173 passed，18 deselected。
- 短名单已满 5 条时，报告不写「补证未执行」。预算用完时，这句话写入报告的补证栏和未知项，不改变经营结论，也不改变生命周期。这一步仍不发起搜索。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:01 北京

- 草稿 PR #18 head `78e6b0b`。没有合并进 main。本地 `make phase1-test`：172 passed，18 deselected。
- 短名单已经有 5 条时不补搜。不足 5 条且预算用完时，调用次数是 0，报告写「补证未执行」。补搜结果的首次见到时间是当前时刻，时间对齐仍只用发布时间；当前时刻之前的回放看不见它。这一步只做计划，不发起搜索。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:52 北京

- 草稿 PR #18 head `38c798f`。没有合并进 main。本地 `make phase1-test`：171 passed，18 deselected。
- 短名单先按可见窗口过滤，再用检索分取前 40 条，不沿用原来的 rank。对不上检索实体、也没有批准向量的材料不占名额。窗口外和当时还看不见的材料进不了说法抽取。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:42 北京

- 草稿 PR #18 head `ad48446`。没有合并进 main。本地 `make phase1-test`：170 passed，18 deselected。
- 规则命中和批准向量的前 50 条取并集，再按来源根留一条。第 51 条向量、未批准的模型，都不能靠相似度进来。同一来源根的转载并进那一条，路径仍记下规则和向量。向量查询只拼篮子名、方向和成员名。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:32 北京

- 草稿 PR #18 head `234b149`。没有合并进 main。本地 `make phase1-test`：169 passed，18 deselected。
- 检索实体只含异常成员、这些成员所属篮子的其他成员、从这组名字出发的一跳邻居，以及用代码挂到这组名字上的监控实体。邻居任何状态都算，包括驳回。邻居的下一跳、同伴所在的其他篮子、监控实体带出的其他代码，都不进入检索。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:22 北京

- 草稿 PR #18 head `37dd333`。没有合并进 main。本地 `make phase1-test`：168 passed，18 deselected。
- 供给或需求的约束清单有四档结论。缺来源、四级来源，或没有写明冲击是有限还是实质时，结论是「约束不清但有上下界」。一二三级来源写明冲突时，标签是「关键约束冲突」。这两档都不把经营影响标成已证实，也不关闭案例。东芝合成走查的经营结论仍来自合成 8-K，约束清单自己仍是不清。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:17 北京

- 草稿 PR #18 head `be94cb9`。没有合并进 main。本地 `make phase1-test`：167 passed，18 deselected。
- 解释报告带影响范围和跟踪清单。暴露只跟关系走。候选关系、已退出的关系降成概念关联。没有关系的价格成员是纯共振。估值倍数停在概念关联。供给或需求的清单上，「有数据」不是证据。东芝合成走查已验证之后，WDC 仍是纯共振，类型候选只有事件冲击。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:03 北京

- 草稿 PR #18 head `bd4da67`。没有合并进 main。本地 `make phase1-test`：166 passed，18 deselected。新的案例测试单独通过。
- 捕获命令同时打印候选路径和说法抽取路径。两条路径不同，不调用模型，也不写文件。缺候选文件时状态是待分析，缺说法文件时状态是抽取失败。截止后没有可用材料时不打印说法路径。没有编造成功录音。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:54 北京

- 已读 main `7768fc9`。Q-M8-12 的 13 项复核已关闭，没有重做，也没有重做 17 项经营门槛。草稿 PR #18 head `fd99d88`。没有合并进 main。本地 `make phase1-test`：165 passed，18 deselected。
- 解释报告的类型候选只跟已打分的机制走。分数达到 0.5 的估值倍数写成叙事冲击。经营影响已证实的供给、需求、竞争或客户融资写成事件冲击。没有达到 0.5 的分数写成原因未明。案例名字本身不会写成叙事冲击。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:44 北京

- 草稿 PR #18 head `82d485f`。没有合并进 main。本地 `make phase1-test`：164 passed，18 deselected。新的案例测试单独通过。
- 四个历史案例的录音路径可以打印。命令不调用模型，也不写文件：`PYTHONPATH=src python -m inves_cog.perception.attribution.capture_plan --fixture tests/fixtures/phase1 --root recordings`。缺文件时调用失败，状态是待分析。没有编造成功录音。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:37 北京

- 已读 main `158f056` 的 Q-M8-12。草稿 PR #18 head `b0f9ddf`。没有合并进 main。本地 `make phase1-test`：164 passed，17 deselected。
- Muse 按被引用材料的日期区间和开盘比较：09-18 早于 09-21 开盘，同一天是未知。不靠 `before_open`。R1 的前 3 名必须引用发布材料，并让受影响标的连到成员。OpenAI 的前 4 名按候选计，第 5 名不能补。结构清单空也不把 `closes_case` 设为真。
- blob：`historical.py` `0e87a6c1d117f8f7ccc0f637e18b8bffa7a34772`，`manual.py` `7d32147a2b123dd4dbe2fd14f089ed70e7ce5c85`。`cases.py` 未改。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:23 北京

- 草稿 PR #18 head `52d36b0`。没有合并进 main。本地 `make phase1-test`：161 passed，17 deselected。新的案例测试单独通过。
- 2026-10-02 的 HDD 对象成员是 STX 和 WDC，没有 MU。截止日只能看见东芝扩产这条四级转载。机制不是供给时结构清单不通过。机制写成供给后，只表示标题对上了日经转载，不能当成经营证据。TDK 时间上可以做二次命中，夹具没有价格响应，结论保持未检验。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:12 北京

- 草稿 PR #18 head `5d43332`。没有合并进 main。本地 `make phase1-test`：161 passed，16 deselected。新的案例测试单独通过。
- 2026-09-21 的池内对象已经分别含有 CPU 篮子和 META。Axios 仍停在 09-18，角色是背景。没有录音时调用失败。引用登顶材料之后，剩下的缺口是「不能证明早于开盘」，案例不关闭。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:04 北京

- 草稿 PR #18 head `744bc39`。没有合并进 main。本地 `make phase1-test`：161 passed，15 deselected。新的案例测试单独通过。
- 2025-01-27 的 M7 异常对象里，方向向下、成员含 NVDA 的篮子名含「加速」。后补录发布页在这个截止日可用，更晚的 Reuters 和 Axios 进不了候选。没有录音时调用失败。临时引用能消掉加速芯片篮子这条结构缺口，这只表示结构清单空了。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:54 北京

- 草稿 PR #18 head `79e49ef`。没有合并进 main。本地 `make phase1-test`：161 passed，14 deselected。
- TDK 标题的发布时间晚于 2026-10-02 开盘，时间上可以做二次命中。夹具没有价格响应，结论保持未检验。它的首次见到时间在 2026-10-14，发布当天的严格路径看不见。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:41 北京

- 草稿 PR #18 head `d427085`。没有合并进 main。本地 `make phase1-test`：160 passed，14 deselected。
- 现场候选录音的入口是 `candidate_capture`。文件名是载荷的 SHA-256，缺文件就失败。仓库里没有编造的成功录音。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:33 北京

- 草稿 PR #18 head `55302e7`。没有合并进 main。本地 `make phase1-test`：159 passed，14 deselected。导出文件没有进入本 PR。
- 冻结了导出 `cd02bdd` 的七条标题。规则上 CoreWeave、巴克莱和 CPI 可以补上 OpenAI 的三类，东芝标题是日经转载。这是夹具，不是现场录音。北京 10-15 09:15 只能看见 CoreWeave，看不见巴克莱和 CPI。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:22 北京

- 草稿 PR #18 head `478e93c`。没有合并进 main。本地 `make phase1-test`：158 passed，14 deselected。
- 后补录历史案例的候选只引用截止前可用的材料。不在这批材料里的引用会被丢掉。没有录音时调用失败，不编造成功。
- 案例仍未通过：发布材料还缺加速芯片篮子，Reuters 只占一类背景，Axios 不能证明早于开盘，东芝仍缺日经扩产原文。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:13 北京

- 已读 main `c5b7e96` 的 M8 v8（Q-M8-11）。草稿 PR #18 head `1f0011a`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：157 passed，14 deselected。
- 三条人工补证可以进入「后补录历史案例」：发布页走发布路径，Reuters 转述只作背景且不是 FT 原文，Axios 停在 09-18、不能证明 72 小时主窗口，角色标成背景。这不表示案例已通过，也不关闭 AC-M8-06。
- 生产路径不接受案例模式。`first_seen_at` 晚于回放时点的材料仍然不可见。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:02 北京

- 草稿 PR #18 head `4539b31`。没有合并进 main。本地 `make phase1-test`：156 passed，14 deselected。
- 三条 2026-10-16 人工补证接到对应案例日之后仍是后补录。发布页没有榜单快照，Reuters 转述不是已冻结的 FT 原文，Axios 停在 09-18。标题方向对得上也不关闭第 7.1 节。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:55 北京

- 草稿 PR #18 head `9b66ae4`。没有合并进 main。本地 `make phase1-test`：155 passed，14 deselected。`make phase1-cases`：3 passed，166 deselected。
- M7 四个案例日的异常对象在没有当时可见新闻时各有状态：池内是「已发现·原因未明」，广域是「已记录」。不调用模型。这不是第 7.1 节通过。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:41 北京

- 已读 main `a5991c9`。UD-COORD-02 已把 PR #11 和 PR #16 合并进 main。草稿 PR #18 head `15479f3`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：154 passed，13 deselected。
- M7 已实现的测试留在套件里，没有退回 pending。三条人工补证仍不关闭第 7.1 节缺口。`test_case_attribution` 继续 pending。不开始下一条，也不开始 M9/M10。

## B-008  进行中  2026-10-16 23:37 北京

- 草稿 PR #18 head `b2ea6cd`。已合入 main `2247520`。没有合并进 main。本地 `make phase1-test`：138 passed，11 deselected。
- 经营证据门槛在 `38e8471` 已关闭。本步是来源夹具：2026-10-16 人工读取的三条公开页冻结为后补录摘录，当时未采集，也没有向量。
- 官方页只有发布日期 2025-01-20，没有榜单快照。Reuters 转述印着 10-08 05:12 PM 和 10-09 02:49 AM，页面没有时区；9 月年化收入接近 500 亿美元，来源根是 Reuters，FT 原文仍未冻结。这两天都早于 10-14，只作背景，不做二次命中。Axios 日期是 09-18，不能改成 09-19，09-19 至 09-21 开盘前的榜单仍缺。
- `test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:22 北京

- 草稿 PR #18 head `38e8471`。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。
- 估值倍数类联动停在市场层，进入基本面核查会拒绝。供给、需求、竞争、客户融资仍可进入。东芝走查以供给进入核查。
- 经营证据的四项反例仍在 `f559023`，等需求方独立复核。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:12 北京

- 已读 main `31e8ceb` 对 `a028e59` 的四项反例。草稿 PR #18 head `f559023`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。
- 覆盖人数 NaN、修订人数无穷大、修订人数超过覆盖人数、EPS 变化 NaN，都保持条件风险。恰好 30% 和 3% 仍通过。空证据的条件风险不能靠普通赋值改成支持；截止日使用时会再核验。合法结构化证据仍能走到已验证。等需求方按这个 SHA 独立复核。
- `test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:04 北京

- 草稿 PR #18 head `7dbbca3`。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。`make phase1-cases`：1 passed，147 deselected。
- 空新闻路径已从 pending 删除。四个案例在标明 synthetic、新闻为空时状态都是「已发现·原因未明」，不调用模型。这不是真实源判定。
- `test_case_attribution` 继续 pending。真实冻结新闻仍缺 10-08 FT 年化营收、09-19 至 09-21 开盘前的 Muse 榜单、R1 或登顶。不开始下一条。

## B-008  进行中  2026-10-16 22:55 北京

- 已读 main `5ce0e6e` 上的经营证据预检和 M8 v7。草稿 PR #18 head `a028e59`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：137 passed，10 deselected。
- 经营已验证不再接受单独的 filing、股价、资金流、社交热度、市场共识度或二次命中。公司一级材料要有可定位引用，并且是 8-K 指引变更或电话会定量表述。EPS 修订要至少 30% 分析师同向、当年共识变化至少 3%、方向一致。产业数据要两个独立来源根。缺字段、未来材料、已证伪材料不通过。约束项仍未知时，另一条合格证据可以支持，未知项保留。截止日不能直接传入「支持」。
- 东芝走查用的是标明 synthetic 的 8-K 指引变更，不是真实公告。`test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 22:45 北京

- 草稿 PR #18 head `ed694dc`。没有合并进 main。本地 `make phase1-test`：136 passed，10 deselected。
- 感知表写入走调用方传入的连接，不打开数据库地址。广域异常只写回捞和报告，状态改成已记录。已评分但没有引用的候选会拒绝。一次性测试库里 `role_perception` 写入十张归因表成功，空引用被约束拦住，事务已回滚。`role_ingest` 插入被拒绝。没有 GRANT ingest，没有写共用库。真实补证入库仍停在 `Repository.put_info`。
- `test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。三处缺口仍缺冻结夹具。不开始下一条。

## B-008  进行中  2026-10-16 22:34 北京

- 草稿 PR #18 head `f2ddf45`。没有合并进 main。本地 `make phase1-test`：134 passed，10 deselected。
- 回放打标：`published_at` 不晚于回放时点、但 `first_seen_at` 更晚，标成「后补录历史复盘」，当时未采集，也不把向量算成当时已有。东芝 10-02 发布、10-14 才见到，在 10-02 当天是后补录；到北京 10-15 09:15 已可见，但没有向量时间戳时 `vectors_then` 为假。CPI 的 `first_seen_at` 在 10-15 14:35+08，09:15 的回放仍是后补录。
- `test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。三处缺口仍缺冻结夹具。下一步：感知表写入只在一次性测试库验证。真实补证入库仍停在 `Repository.put_info`。不开始下一条。

## B-008  进行中  2026-10-16 22:24 北京

- 草稿 PR #18 head `bb5fc2f`。没有合并进 main。本地 `make phase1-test`：133 passed，10 deselected。
- 已看到用户批准的导出分支 `data/m8-export` `cd02bdd`。核对后本机临时副本已删除。导出文件没有进入本 PR，也没有进入 main。
- 缺口在 `handoff/M8/source-gaps.md`。能对上标题的有东芝扩产、TDK 磁头、CoreWeave 债券收益率、巴克莱下调 Dell / HPE / NetApp、当天 CPI 同比 3.7% 对预期 3.6%。对不上的有 10-08 FT 约 500 亿美元年化营收、09-19 至 09-21 开盘前的 Muse 榜单、DeepSeek R1 或登顶。2026-09 至 10 月新闻最早 `first_seen_at` 在 2026-10-14，更早的异常日只能标成后补录历史复盘。巴克莱三条和 CPI 的 `first_seen_at` 在 2026-10-15 14:35+08，北京 10-15 09:15 的回放还看不见。
- 合成标题只检查案例方向。10-09 仍不能当作 10-14 之后的二次命中。`test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。下一步：等冻结夹具补上这三处缺口后再开案例测试。不开始下一条。

## B-008  进行中  2026-10-16 22:14 北京

- 草稿 PR #18 head `d42b06f`。没有合并进 main。本地 `make phase1-test`：132 passed，10 deselected。迁移在一次性测试库里建表成功。
- 新增 `migrations/phase1_m8_0001_attribution.sql`：回捞、说法、候选、联动事件、三轨、二次命中、冲击分解、系统性标签、标的代码、解释报告。没有 GRANT ingest，没有写共用库。
- 东芝中期走查是合成夹具，不是冻结新闻。候选引用日经扩产，机制为供给。2026-10-06 的 TDK 只做二次命中。生命周期从已发现走到已验证·有影响。报告写明终结原因，并保留未完成的约束项。标的代码为空，因为这条不是估值倍数连带、叙事冲击未变或原因未明。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。不假定 `data/m8-export` 已存在。下一步：把另外三个案例的候选排序接到同一份报告契约上，仍用合成或录音，等冻结新闻再开案例测试。不开始下一条。

## B-008  进行中  2026-10-16 22:09 北京

- 已读 `ops/answers/B-008.md`。草稿 PR #18 head `eaa3dae`，已合入 `origin/main` `c8fee63`。没有合并进 main。本地 `make phase1-test`：130 passed，10 deselected。
- 二次命中要求 `published_at` 晚于异常起点。2026-10-08 和 2026-10-09 对 2026-10-14 的 OpenAI 异常只作背景。负例已写进 `test_second_hit`。M8 v6 第 7.1 节仍写 10-09 做二次命中；`docs/` 和 golden 未改，冲突记在 `handoff/M8/kickoff.md` 第 12 节。
- 缺 EPS 共识或覆盖家数不是「未下修」。缺价格、基本面或联动状态时不生成情绪标签。条件风险报告写「截止日仍未知」、未知项，并且 `operating_impact_proven` 为假。
- 说法抽取和候选生成用录音。广域异常不调用模型。补证真实入库仍停：只打算走 M1 已有的 `Repository.put_info`，没有新增 ingest 写权限，也没有写共用库。`data/m8-export` 尚未按已到仓库处理。
- main 补上的两条 v6 pending 登记，对应测试在本分支已经转绿，合并时没有放回 pending。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。下一步：解释报告把东芝案例走到截止日所需的夹具，以及感知表迁移只在一次性测试库验证。不开始下一条。

## B-008  进行中  2026-10-16 21:59 北京

- 规则切片已推到草稿 PR #18，head `dc78efe`。没有合并。本地 `make phase1-test`：128 passed，10 deselected。
- 新转绿：`test_retrieval_recovers_low_rank_item`、`test_five_dims_rules`、`test_tracks_and_deadline`、`test_divergence_labels`、`test_systemic_event_tag_requires_level12`、`test_unexplained_recheck_5d`、`test_anomaly_contract`。低排序榜单按实体重合进入前 40，并被候选引用。截止日结果按复述第 6 节落入生命周期。只有四级信源时系统性标签为「无」。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。等冻结新闻和录音，不编造现场调用，不连接共用库。
- 下一步：说法抽取、候选生成和解释报告。不开始下一条。不等这条 head 的 CI 才写下一阶段。

## B-008  进行中  2026-10-16 21:44 北京

- 规则切片已推到草稿 PR #18，head `7eb7614`。没有合并。本地 `make phase1-test`：121 passed，10 deselected。
- 已转绿：`test_implied_magnitude_rules`、`test_evidence_scores`、`test_time_alignment_late_news`、`test_candidate_validation`、`test_retrieval_background_window`、`test_embedding_model_isolation`、`test_market_confirmation_four_conditions`、`test_lifecycle_transitions`、`test_second_hit`、`test_search_budget`、`test_verified_not_from_market_evidence`。golden 的隐含幅度和证据分全部命中。阈值在 `config/params/p-2026.10/m8.yaml`。
- 仍在 pending：`test_anomaly_contract`、`test_retrieval_recovers_low_rank_item`、`test_five_dims_rules`、`test_tracks_and_deadline`、`test_divergence_labels`、`test_systemic_event_tag_requires_level12`、`test_unexplained_recheck_5d`、`test_case_attribution`、`test_case_no_news_unexplained`。
- 下一步：继续这些测试和实现。不开始下一条。不等这条 head 的 CI 才写下一阶段。

## B-008  进行中  2026-10-16 21:34 北京

- 草稿 PR #18：https://github.com/XuQingsong/inves-cog/pull/18 ，分支 `phase1/m8-attribution-tracking`，head `bdb5ad8`。复述在 `handoff/M8/kickoff.md`。没有合并。没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- 没有必须停的问题。复述第 6 节按规格执行：截止日结果落入生命周期的方式、`search_daily_budget = 200`、向量只用 `text-embedding-async-v1` / 1536、M7 对象先用已验收夹具。要改写 `ops/answers/B-008.md`。
- D-28：三处都还在，但不改变 M8 要读的已入库关系和篮子 id。`draft_ticker` 的健康标签、多 L2 覆盖、STX/SKHY 硬编码列为 backlog，本模块不改 M6。
- 下一步：先提交失败的 blocking 测试和冻结夹具，再实现。不开始下一条任务。

## B-008  已收到  2026-10-16 21:30 北京

- 任务：M8 建连归因与三轨跟踪。先写开工复述和草稿 PR，分支 `phase1/m8-attribution-tracking`。没有「必须停」就直接开发。
- 依据：`origin/main` `2165c29`；`ops/control.md` 中 B 为「运行」。M8 用 v6。不连共用库，不改 `docs/`、golden、milestones，不合并。M7 尚未进 main，按已验收契约和夹具开发，不把未合并的 M7 实现混进本分支。
- 下一步：读 T08、M8 v6、M7 输出契约和 M6 图谱接口，写 `handoff/M8/kickoff.md`。

## B-007  已完成  2026-10-16 18:08 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `3102373`。没有合并。已合入 `origin/main` `e2c223c`，`MANIFEST.sha256` 和 `CHANGELOG.md` 自动合并，两边都保留。没有改阈值，没有改 M6，没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38885054082 （PR，phase1-blocking，122 passed，12 deselected，33.46s）。同头 push：https://github.com/XuQingsong/inves-cog/actions/runs/38885047902 。本地 `make phase1-test` 同样 122 passed、12 deselected。M7 blocking 12 个，含一致性测试 `test_file_and_database_views_match`。`test_case_detection` 通过。`test_anomaly_live_smoke` 仍等待 R5。
- 差异原因：`marketstate.baskets` 只从 2026-07-01 起。数据库模式用这段短窗口算收益 z，和文件模式 120 日 z 不是同一个数，关注级抢在 `A_linked` 前面；`数据中心电力与散热` 变成 `A_watch`，合并后把数据中心电力从 L3 抬到 L2。另外 `universe` 写死为 `pool`，BAC、LQDA、MMED、PGR、U 被算进池内。现在两种模式都用同一套日线重算篮子。广域只取不在 `config/universe.yaml` 和篮子成员里的 `marketstate.daily`。行业和风格 ETF 只参与轮动。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）四个数不变：非温和查全率 0.9459459459459459（70/74），样本外 0.9512195121951219（39/41），对照日篮子异常 0，平均每天对象 2.327445652173913（2208 个交易日，5139 条）。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。
- 已自行决定：无。
- 下一步：无。不合并。不开始下一条。

## B-007  进行中  2026-10-16 18:06 北京

- 实现已推到 PR #11，head `3102373`（先合入 `origin/main` `e2c223c`，`MANIFEST.sha256` 和 `CHANGELOG.md` 自动合并，两边都保留）。没有改阈值，没有改 M6，没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- 差异原因：`marketstate.baskets` 只从 2026-07-01 起。数据库模式用这段短窗口算收益 z，和文件模式 120 日 z 不是同一个数，关注级抢在 `A_linked` 前面；`数据中心电力与散热` 变成 `A_watch`，合并后把数据中心电力从 L3 抬到 L2。另外 `universe` 写死为 `pool`，BAC、LQDA、MMED、PGR、U 被算进池内。
- 现在两种模式都用同一套日线重算篮子。广域只取不在 `config/universe.yaml` 和篮子成员里的 `marketstate.daily`。行业和风格 ETF 只参与轮动，不当作广域个股。2026-10-14 文件模式仍是 2 条池内（含 `A_linked`，数据中心电力仍是 L3）；补上当日广域日线后，这 5 只是 `universe = wide` 的 L4，池内两条不变。
- 一致性测试：`test_file_and_database_views_match`。本地 `make phase1-test`：122 passed，12 deselected。M7 blocking 12 个，`test_case_detection` 通过。
- AC-M7-07（`--source file`）四个数不变：非温和查全率 0.9459459459459459（70/74），样本外 0.9512195121951219（39/41），对照日篮子异常 0，平均每天对象 2.327445652173913（2208 日，5139 条）。
- 下一步：等这条 head 的 CI。绿了再写已完成，并删除本机 `/tmp/m7-export`。不要重做实现。

## B-007  已收到  2026-10-16 17:40 北京

- 任务：M7 再修。数据库模式和文件模式不一致，违反 Q-M7-8。在 PR #11 上按 `config/universe.yaml` 和篮子成员划分池内 / 广域，查明篮子层差异并消除，加一致性测试，合入最新 main，重跑文件模式 AC-M7-07。
- 依据：`origin/main` `d339bff`；`ops/control.md` 中 B 为「运行」。不改阈值，不改 M6，不连库，不改 `docs/`、golden、milestones，不合并。
- 下一步：读 `data/m7-export` 的 `stored-marketstate/`，对照 2026-10-14 的两种快照。

## B-006  已完成  2026-10-16 17:12 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `b529480`。没有合并。已合入 `origin/main` `3f5d476`，冲突只在 `MANIFEST.sha256` 和 `CHANGELOG.md`，两边都保留。没有改 `docs/`、golden、milestones，没有改 M6，没有连接或写入共用库。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38878632674 （PR，phase1-blocking，109 passed，9 deselected，32.69s）。同头 push：https://github.com/XuQingsong/inves-cog/actions/runs/38878624666 。本地 `make phase1-test` 同样 109 passed、9 deselected。M7 blocking 11 个（含别名测试），`test_case_detection` 通过。`test_anomaly_live_smoke` 仍等待 R5。
- Q-M7-15：路径 B 不再用 4 个百分点分支，`m7.yaml` 已去掉 `path_b_gap`。其余阈值没改。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 2.327（2208 个交易日，5139 条）。四项都过线。
- 别名表：`NAND/DRAM` → `memory`。写在复跑代码和报告 `summary.basket_aliases`。`sector:XLF` 没有改判成 KRE。2026-07-27、07-29 仍未命中，因为当天 2 条和 5 条异常里没有 `basket_id = memory`。2023-03-10、03-13 的 `sector:XLF` 仍未命中。
- AC-M7-03 已按新结果重出，在 `handoff/M7/ac-m7-03.json`。自测在 `handoff/M7/self-test.md`。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。
- 已自行决定：无。
- 下一步：无。不合并。不开始下一条。

## B-006  进行中  2026-10-16 17:10 北京

- 实现已推到 PR #11，head `b529480`（先合入 `origin/main` `3f5d476`，冲突只在 `MANIFEST.sha256` 和 `CHANGELOG.md`，两边都保留）。路径 B 不再用 4 个百分点分支，`m7.yaml` 已去掉 `path_b_gap`。别名表只有 `NAND/DRAM` → `memory`，写在复跑代码和 `handoff/M7/ac-m7-07.json` 的 `summary.basket_aliases`。`sector:XLF` 没有改判。
- 本地 `make phase1-test`：109 passed，9 deselected。M7 blocking 11 个，`test_case_detection` 通过。
- AC-M7-07（`--source file`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 2.327（2208 个交易日，5139 条）。四项都过线。2026-07-27 和 07-29 仍未命中 `basket:NAND/DRAM`：当天 2 条和 5 条异常里没有 `basket_id = memory`。XLF 两天仍未命中。
- 下一步：等这条 head 的 CI。绿了再写已完成，并删除本机 `/tmp/m7-export`。不要重做实现。

## B-006  已收到  2026-10-16 17:00 北京

- 任务：M7 验收修复。在 PR #11 的分支上删除路径 B 的 4 个百分点分支（Q-M7-15，`m7.yaml` 去掉 `path_b_gap`），复跑程序加验证集篮子别名表（至少 `NAND/DRAM` → `memory`，Q-M7-16），合入最新 main，重跑 blocking、`test_case_detection`、`--source file` 的 AC-M7-07 和最近 5 天清单。
- 依据：`origin/main` `3f5d476`；`ops/control.md` 中 B 为「运行」。B-005 验收不通过是因为每天 3.33 个对象。不改别的阈值，不改 M6，不连库，不改 `docs/`、golden、milestones，不合并。
- 下一步：先改 `test_path_b_relative`，让 4 个百分点不再命中，确认测试失败后再改实现。

## B-005  已完成  2026-10-16 14:48 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ea089ff`。标题改为「[M7] 提交验收」，已取消草稿。没有合并。没有改 `docs/`、golden、milestones，没有改 M6，没有连接或写入共用库。迁移文件 `migrations/phase1_m7_0001_anomalies.sql` 只在一次性测试库里应用过，共用库留给 A 线在合并后执行。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38863086547 （phase1-blocking，75 passed，9 deselected，31.51s）。本地 `make phase1-test` 同样 75 passed、9 deselected。M7 的 10 个 blocking 测试通过，`test_case_detection` 通过。`test_anomaly_live_smoke` 仍留在 `pending.txt`，等待 R5。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 3.328（2208 个交易日，7349 条）。前三项过线。3.328 高于每天 2.5 的上限。多出来的主要是路径 B 的 4 个百分点分支，约每天 1.3 条只因个股和主 L3 留一收益差达到 4 个百分点、自身涨跌达到 3%。阈值没有下调。
- AC-M7-03：最近 5 个交易日 2026-10-08、10-09、10-12、10-13、10-14 的收盘和盘后清单在 `handoff/M7/ac-m7-03.json`。AC-M7-05：盘后价只从 2026-10-07 起，序列只有 6 个交易日，自身 120 日 z 为空，没有合适的盘后例子，留给 A 线在合并后补。自测逐条写在 `handoff/M7/self-test.md`。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。四个案例窗口留在 `tests/fixtures/phase1/m7/`。
- 已自行决定：无新决定。HDD、CPU、2026-10-14 的收益 z 落在关注级，又和 `|resid_z|≥3` 或路径 B 成员合并，严重级别按规则成为 `alert`，入口仍保留 `A_watch`。这是按冻结阈值改期望，不是改阈值。
- 下一步：无。不合并。不开始下一条。

## B-005  进行中  2026-10-16 13:48 北京

- 测试先红：`8f0f7ed` 提交了失败的 blocking 测试和四个案例窗口夹具。检测代码还没写。

## B-005  已收到  2026-10-16 13:40 北京

- 任务：在 PR #11 上开发 M7。先红后绿。不连库，不执行迁移，不改 M6、`docs/`、golden、milestones，不合并。
- 依据：`origin/main` `344deab`；`ops/control.md` 中 B 为「运行」。M7 v8 已冻结。K01 只计 `close`+`pool` 合并后对象；K02 迁移只授予 `job_runs` 的 INSERT/UPDATE；K03 轮动按答复 A，主题轮动是 `alert`。
- 下一步：读 `data/m7-export` 的 README，先提交失败测试和四个案例夹具。

## B-004  已完成  2026-10-16 13:16 北京

- 草稿 PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ac7c252`。复述在 `handoff/M7/kickoff.md`。没有写实现，没有改 `docs/`、golden、milestones，没有改 M6，没有合并。
- 必须停，等答复后再写代码：
  1. AC-M7-07 每天的异常对象，我倾向只计 `close` 且 `universe = pool`、合并之后的对象。把盘后和广域算进去会超过每天 2.5 个。
  2. `role_perception` 对 `ingest.job_runs` 只有 SELECT。我倾向只给这张表补 INSERT，任务名 `anomaly_detect` 和 `premarket_review`。
  3. 轮动单独命中时的 `severity`。我倾向风格价差 `|z| ≥ 3` 为 `alert`，只有行业极差 ≥ 4 为 `watch`。
- 数据申请（不含凭证，不含新闻；导出放 PR 分支 `handoff/M7/export/`，合并前删除）：
  1. `ingest.bars_daily`：篮子成员加 SPY、QQQ、IWM、RSP、11 只行业 ETF、SMH、IGV、KRE、MTUM、VLUE；列 `ticker, trade_date, open, high, low, close, volume, post_close, adj_factor, source`；2017-01-03 至 2026-10-14。
  2. `ingest.macro_observations`：`VIX_CBOE`、`VIX3M_CBOE`、`VIXCLS`、`DGS2`、`DTWEXBGS`、`DCOILWTICO`；列 `series_id, observation_date, value, units, realtime_start`；同一日期。
  3. `graph.baskets` 全表，成员保留生效区间。
  4. `ingest.issuer_profiles` 的 `ticker, sic`，范围是日线里出现的代码。
  5. `ingest.short_interest`：池内代码，`publish_date` 2018-01-02 至 2026-10-14；缺的不要填 0。
  6. `graph.cluster_suggestions` 有行才导。
- 已自行决定：见复述第 6 节。没有连接工厂或阈值之外的新决定。
- 下一步：停下。不开始实现。

## B-004  已收到  2026-10-16 13:10 北京

- 任务：M7 开工复述。只写 `handoff/M7/kickoff.md`，开草稿 PR，分支 `phase1/m7-anomaly-detection`。提交后停下，不写实现。
- 依据：`origin/main` `4c92710`；`ops/control.md` 中 B 为「运行」。用户已于 2026-10-16 批准开工（G1）。B-003 已通过，PR #8 已合并（`38510bc`）。
- 下一步：读 T07、M7 v7、验证报告、golden 77 个事件，以及 M6 的输出表和 Q-M6-15、Q-M6-18。复述三条路径、数据接口、数据申请和 AC-M7-07 复跑方式。

## B-003  已完成  2026-10-16 12:26 北京

- 已把最新 `origin/main` `b0f5eb1`（含 M3 合并 `9bbf151`）合进 PR #8。head `c144899`。没有合并 PR。
- 冲突只动了三个文件。`pyproject.toml` 依赖取并集，保留 `scipy>=1.14,<2`，其余与 main 相同。`uv lock` 已按这份依赖重算，`uv.lock` 没有变化。`tests/fixtures/phase1/MANIFEST.sha256` 两边条目都保留，Harness `validate_frozen` 通过（162 条，无缺、无多余、无哈希不符）。`tests/harness/CHANGELOG.md` 只追加，M6 `draft.json` 与 M3 `timeline.json` 两行都在。
- blocking：本地 `make phase1-test` 65 passed，7 deselected，1 warning，19.43s，退出码 0。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38850453859 （PR，65 passed / 7 deselected / 22.15s）。push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38850448970 。
- 已自行决定：无。没有改 `docs/`、golden、milestones 里原有内容；main 带进来的文档和 M3 代码原样保留。
- 下一步：无。不开始 M7。

## B-003  已收到  2026-10-16 12:21 北京

- 任务：把最新 `origin/main` 再合进 PR #8。不合并 PR，不改别的文件。
- 依据：`ops/control.md` 中 B 为「运行」。B-003 写明 B-002 第 1–5 项已通过，第 6 项取消。
- 下一步：解决 `pyproject.toml`、`tests/fixtures/phase1/MANIFEST.sha256`、`tests/harness/CHANGELOG.md`，跑 blocking。

## B-002  已完成  2026-10-16 12:21 北京

- 需求方在 B-003 中确认第 1–5 项通过。第 6 项按 Q-M6-20 取消：B 线不写共用库，三天重算改由 A 线在 PR #8 合并后执行。
- 交付仍是 PR #8，head `d5d0587`，CI https://github.com/XuQingsong/inves-cog/actions/runs/38848165567
- 已自行决定：无。

## B-002  阻塞  2026-10-16 11:59 北京

- PR #8，head `d5d0587`。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38848165567 （push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38848160877）。本地 `make phase1-test`：53 passed，6 deselected，1 warning，19.53s，退出码 0。
- 新增测试：`test_l3_same_as_l2_drops_theme_factor`（相同成员 → `m+s`、`l3_same_as_l2`、`beta_t` 为空；不同 → `m+s+t`）、`test_sic_review_additions`、`test_draft_all_does_not_share_one_connection`（复现原来 3 个线程叠在一条连接上，修完后深度为 1；有连接工厂时每个线程一条新连接）。
- 冲突：`src/inves_cog/llm/transport.py` 按任务名分开保留。`segment_mapping_draft` 仍是 `max_tokens=4096`、`reasoning_effort=low`；`graph_seed_draft` 和 `exposure_draft` 仍是 `8192` 和 `low`。模型名没改。分支已合入 `origin/main` `0035c26`。
- 第 6 项：阻塞：等待数据库连接信息。要重算 2026-10-12、13、14 并写入共用库的 `marketstate`。这台环境到不了 Mac 上的 `127.0.0.1:25432`，现有 `inves_cog_review` 又只能读。需要一份能写 `marketstate`、不写 `ingest` / `fundamentals` / `trading` 的连接，放在未跟踪的 `.env`，不提交。
- 已自行决定：无。没有连接工厂时 `draft_all` 改为串行；命令行传入工厂后才并行，每个线程自己的连接。
- 变更：无新表、无新数据源。因子口径和 SIC 映射按已经写进文档的 Q-M6-18、Q-M6-19。
- 下一步：1–5 已在 PR #8，不合并。等连接到位后只做第 6 项，不重做前面的修复。

## B-002  已收到  2026-10-16 11:40 北京

- 任务：M6 合并前修复（PR #8，分支 `phase1/m6-graph-baskets-marketstate`）。不合并 PR。
- 依据：`origin/main` `0f6371f`；`ops/control.md` 中 B 为「运行」。验收报告有条件通过。
- 下一步：合入 main 并解决 `transport.py`；Q-M6-18 先红后绿；补 `sic_to_etf.yaml`；`draft_all` 每线程一条连接；跑 blocking。第 6 项重算共用库需要可写的 `marketstate` 连接，当前只有一份到不了的只读说明。

## B-001  已完成  2026-10-16 11:08 北京

- `make phase1-test`：在 `origin/main` `273be4a` 上退出码 0。**39 passed**，5 deselected，1 warning，**10.66s**。Python 3.11.17。用的是脚本自带的一次性 docker compose 库，没有连生产库。M6 还在 PR #8，不在这条 main 上，所以这 39 个是 M0–M2 的 blocking，不是 M6 的 11 个。
- 复述：B 线做感知和解释，顺序是 M6 验收后的修复、M7、M8。M7 在每个交易日收盘后发现个股、篮子、行业、大盘的异常，对应目标 A1。M8 给每个异常找候选原因、证据和置信度，对应目标 A2、A3。代码只写 `inves_cog.perception`（含 `graph`）和 `inves_cog.marketstate`；`ingest` 只读，例外只有 M6 文档已经授权的采集。不改 A 线的 `trading`、`valuation_v1`，不改 `docs/`、`golden/`、`milestones.txt`，不合并 PR（用户批准后由需求方合并）。必须停的情况：跨模块表结构或接口、golden、规则 A 或交易行为、新数据源或付费、key 或权限、不可逆删改数据，以及仓库里的定时服务和共用库迁移。一次只做信箱里还没「已完成」的最小编号；`ops/control.md` 里 B 为「暂停」就停。
- PR #8 印象（只读，head `acf4856`，分支 `phase1/m6-graph-baskets-marketstate`，没有改）：价格层在 `inves_cog.marketstate`，按留一篮子、含截距、信号日之前 120 日的 SVD 回归算剩余涨跌，轮动和 v5 警戒分开；图谱在 `inves_cog.perception.graph`，原文切片、无引用就丢、审核日志和已确认视图是分开的。schema 在 `migrations/phase1_m6_0001_graph_marketstate.sql`，授权的采集收在 `ingest/market_structure.py`。main 上这两个包仍只有空 `__init__.py`。风险大的地方：`draft_all` 默认 3 个线程共用一条数据库连接；同一 ticker 有多条 L2 时 `active_baskets` 后写覆盖先写；`draft_ticker` 把所有异常收成 degraded，和「没有年报」分不开；STX 单一业务和 SKHY 四季 TTM 写死在图谱服务里；`handoff/M6/` 里多份证据是单行 JSON，diff 不好看。
- 疑问：这台机器没有生产库 URL 和 API key。本次测试不需要，所以没有停。下次要读共用库或跑 live，需要用户把值给我，我放进未跟踪的 `.env`，不提交。文档和 M6 v6 没有要停下来的疑问。
- 用户决策 UD-B-01：用户说每次做完任务后开启定时任务，监控 `ops/inbox/B/` 里还没完成的任务，有就直接开始开发。打算照做，但只作为这个 agent 的唤醒：每 10 分钟看一次信箱（与 A 线 UD-A-01 同一间隔），仍按 README 第 3 节一次只做一条；B 为「暂停」就什么也不做。不在仓库里加定时服务，不改调度代码。复用同一个定时器，不在每次完成时再挂一个。
- 已自行决定：无。
- 下一步：没有下一条信箱任务。不碰 PR #8，等需求方发 B-002。

## B-001  已收到  2026-10-16 11:02 北京

- 任务：入门（搭环境、读文档、复述）。不写业务代码，不开 PR。
- 依据：当时的 `origin/main` `d4afbaa`；`ops/control.md` 中 B 为「运行」。
- 下一步：读任务书 §4、M6 v6、M7 验证报告、M2 验收报告；跑 `make phase1-test`；读 PR #8。
