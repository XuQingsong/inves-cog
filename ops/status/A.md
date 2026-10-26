# A 线回报

本文件仅记录非敏感交付状态。详细生产证据保留在项目私有运行目录和用户对话中；此前本文件历史保留在 Git 历史，不改动 B 线文件。

## A-021 已完成（只读诊断，等待需求方具体修复方案）

已完成请求构造分析和限定的只读对照，没有修改代码、权限、feed 或调度，也没有新增模型调用。完整诊断已在用户当前对话交付，生产原始响应不发布到公开仓库。

公开代码将盘前 SIP 截点设为任务执行附近的时间；[Alpaca 官方合同](https://docs.alpaca.markets/us/docs/market-data-faq)要求免费历史 SIP 截点至少早于当前15分钟。建议评估保留 SIP 并使用更早截点、明确标注滞后；或延后复核以保留计划截点。IEX 的单所覆盖不能直接等同全市场，付费方案需要另行决定。具体方案由需求方确认后再实施。

## A-018 进行中（代码已验收部署，恢复属于独立运维验证）

[PR73](https://github.com/XuQingsong/inves-cog/pull/73)，代码 head `02f05d7f611104d70e57e18404aa993283d5731d`，[准确CI](https://github.com/XuQingsong/inves-cog/actions/runs/40108363441/job/120914687276)通过。受控恢复正在核验，尚未宣称全部恢复；详细运行状态和费用仅向用户直接回报，不在公开文件发布。

## A-020 已完成

[PR70](https://github.com/XuQingsong/inves-cog/pull/70)与默认授权回归[PR71](https://github.com/XuQingsong/inves-cog/pull/71)已验收合并。代码交付、合并安装和首批验证已分别完成。后续采集进展按真实结果监测，不重复迁移或重启已有任务。

## 执行边界

按最新 ops/control 接单；原范围持续授权有效，自动化保持开启。一次只处理一个开发任务，不执行 B 线开发、不自动合并 PR。新增方案由需求方下发后执行，公开同步不包含生产进程、内部路径、账户响应、队列或费用明细。

## 用户决策 UD-A-49

用户在当前对话明确答复“允许预算内自动续批”：后续受控恢复可在既有累计预算及每日调用边界内自动续批，直到完成、触线或用户/控制暂停，无需逐批审批。每批保留远端期限，接续前核实前批实际结束，不重置累计费用或调用上限；结束后恢复非新闻处理。本决定不扩大来源、权限、跨线修改或合并范围，公开状态不披露生产明细。

## A-021 第二步 进行中

已收到需求方明确方案：保留SIP，所有分钟线请求end截到请求end与注入当前时间减16分钟的较早者。先提交离线失败测试，再实现；不改数据源、M7阈值或新建表。变更先记：采集结果增加请求/实际截止元数据；仅通过现有job诊断字段记录数据截止说明，M7输入按该截止过滤并携带实际行情时间，在复核结果中标注，不把请求时间冒称数据时点。若发现必须完整08:00数据的硬约束则停止回报。准确CI通过后送验，合并后按已有授权部署，周一自然运行另验。

## A-021 已完成（需求方关单）

最新 main 已明确需求方代做、合并 c6062b4 并部署，停止重复实现。周一 ET 08:00 自然运行单独核验。

## A-022 已收到／进行中

按 UD-COORD-38 实现重要新闻优先、低价值规则跳过、完整提取每日1500条与粗筛每日120次独立上限，保留150万token兜底及原补采边界。变更：仅 triage 与 repository 队列/已有使用统计及对应离线测试；不改数据源、权限、模型配置或数据库结构。先失败测试后实现，准确 head CI 后送验，不自动合并。

## A-022 已确认交接  2026-10-25 03:20 北京

已读完需求方 03:10 交接与 T1–T7 自验清单。确认 A-019、A-020、A-021 均已关单，不重做；当前唯一开发任务为 A-022。按授权只改新闻分级、现有使用统计/队列选择及测试，不改模型、提示词、数据源、权限、数据库结构或配置文件。生产补采看门与周一自然运行作为独立运维事项跟踪。

## A-022 代码已完成，等待需求方验收合并

[PR75](https://github.com/XuQingsong/inves-cog/pull/75)，准确 head `cb5a6f82cf37874280a98a0a09c6c666565c7090`，[准确 CI](https://github.com/XuQingsong/inves-cog/actions/runs/40125434716/job/120965725020) 通过（752 passed，21 deselected）。已保留先失败测试提交、后实现提交；实现覆盖 A/B/C 分级、C 级零模型、B 升 A、持仓优先、1500 条完整提取与 120 次粗筛独立 ET 日限额、150 万 token 兜底和 UD-COORD-36 边界。未自动合并或部署；合并后再按交接执行安装、确认新预算生效、停止临时看门程序，并在首个 ET 交易日回报分级与调用/费用汇总。

## B-059 部署运维 已收到／进行中

收到 main 补充三十：B-059 已验收合并，按 UD-A-47 快进含 merge `61bb37d` 的 main，只重启 pages 并验证三页外部状态码。已只读确认生产工作区干净，当前版本为已部署的 A-021；不占开发编号，A-022 继续等待需求方验收。变更：仅已合并代码安装与 pages 重启，无迁移、权限或配置变更。

## B-059 部署运维 已完成

生产已快进至 `f4cba95dcced3857243168512c6b785070991bf8`，包含已验收 merge `61bb37d`（PR74）。只重启 pages，其他原有运行服务 PID 保持，服务配置未改，工作区干净。外部 `/account`、`/`、`/s/MU` 均 HTTP 200，内部亦均 200/text/html。无迁移、手工业务补跑或操作触发模型调用。下一步：需求方页面走查后关单 B-059。

## A-022 进行中（需求方复核修订）

已收到 03:45 复核：T1/T3–T7 通过，T2 按需求方修订把 token 兜底改为每 ET 日 550 万，补 450 万 token 下第 1500 条放行、第 1501 条按条数延期的测试。现有 Pipeline 仍显式传入旧配置 150 万，将在 triage 内兼容映射为新常量，保留小额度测试注入，不改配置或其他逻辑；先失败测试后实现，同 PR75 送验。该修订来自 main 需求方复核，不扩大累计补采预算或调用上限。

复核修订已推送同 PR75，head `c637d015477ea18d02b6f9bf8643174846ef3207`。新增两例先失败，修复后目标/兼容回归 11 passed，静态检查通过。550 万 token 常量已兼容默认与现有 Pipeline 旧参数路径；完整提取第 1500 条在 450 万 token 下放行，第 1501 条按条数延期。准确 head CI 待完成，不沿用上一 head 的通过结论。

## A-022 复核修订 已完成，待验收合并

[PR75](https://github.com/XuQingsong/inves-cog/pull/75)，head `c637d015477ea18d02b6f9bf8643174846ef3207`，[准确 CI](https://github.com/XuQingsong/inves-cog/actions/runs/40126687106/job/120969540260) 通过：754 passed、21 deselected。T1/T3–T7 沿用需求方已接受行为并通过本次全量回归；T2 新增 `test_a022_4500000_tokens_allows_item_1500_then_defers_1501_by_count` 两条路径均通过，550 万 token 触线延期用例通过。已自行决定：仅按已记录方案兼容旧参数，无其他。下一步：需求方验收合并后安装，再核验真实运行和预算；当前未部署。

## A-022 / B-060 部署 已收到／进行中

收到 10:45 验收与补充三十一：A-022 merge `e53e991`、B-060 merge `5e83718` 已合并，按 UD-A-47 一次快进、仅重启 scheduler/pages，确认新预算后停止临时新闻看门程序。已只读确认生产仍为上次 B-059 部署版本且工作区干净；本轮执行安装、预算和外部页面验证，首个 ET 交易日统计另验。变更：仅上述已授权进程重启，无迁移、权限或配置变更。

部署进行中：已安装 `3a1b1c7f64b4806aa2f93f8b35b6bf8ce44bf698`，实际 Pipeline 构造确认 550 万 token /1500 条/120 次；临时看门已停止。独立验证发现 7764 条窗口新闻仍带前次 `bounded_window_ended` 的永久队列 hold（retry_at 年9999），并非正常日切延期；已确认旧受控 worker 为零。本次按既有补采接续授权，仅解除这组精确旧 hold，并因当前 ET 日旧用量已触线，将其顺延到下一 ET 日；保留 hold 审计与正文，不手工触发模型调用。

## A-022 / B-060 已合并安装，真实运行验证进行中

生产 head `3a1b1c7f64b4806aa2f93f8b35b6bf8ce44bf698`，包含 A-022 `e53e991` 与 B-060 `5e83718`。仅 scheduler/pages 重启，旧 enrich 已退出且只有一个新 enrich，其他原有运行服务 PID、配置保持，工作区干净。外部 `/account`、`/s/NFLX` 均 200。新代码按真实配置构造 Pipeline 验证 limits=5500000 tokens/1500 full/120 screen；临时看门进程精确终止1个，之后无该临时 worker/guard。

部署时 ET 当日旧累计为5501047 tokens、2449个完整提取 info_id、1次粗筛、4条 usage缺失，属于上线前用量，不冒称新版本结果。部署后核验未新增模型调用。精确恢复7764条旧永久hold后均改为 ET 10-25 00:00（北京12:00）日切重试，永久hold剩余0；正文与hold审计保留。下一步：日切核验分级实际落库及预算执行；10-26首个交易日回报A/B/C、完整提取、调用/token/费用。当前只确认代码安装和配置生效，未宣称首日业务验收完成。

## A-022 自然运行进行中（ET 10-25 日切后首轮）

北京12:04左右只读核验：自然 enrich 已开始，已落库 A级63条ok、B级1条ok，C级尚未落库；窗口pending由7764降至7700。ET当日 usage 为86个完整提取info_id、1次粗筛、172次新闻调用、237053 tokens（输入177985/输出59068），usage缺失0，按输入2/输出8元每百万估费0.83元。调用计数与已落库条数不同，存在进行中批次，不冒称全部完成。临时worker/guard为0，永久hold为0。下一步继续核验分级与限额收口；此为周日补采运行证据，10-26交易日统计仍待自然运行。

## B-061 部署运维 已收到／进行中

收到补充三十二：PR77 merge `02112ec` 已验收合并，按 UD-A-47 快进 main、仅重启 pages 并核验 `/account`、`/s/HD`、`/s/AVGO`。不占开发编号，A-022自然处理继续；变更仅已授权页面重启，无迁移或配置修改。

## B-061 部署运维 已完成

生产已快进至 `1d99894942f608a1fe29d219ae1c503237b898d8`，含 merge `02112ec`（PR77）。仅 pages 重启，其他原有服务PID及配置保持、工作区干净；`/account`、`/s/HD`、`/s/AVGO` 外部均200，内部均200/text/html。下一步需求方走查。

A-022 同轮只读进展：A级701条ok、B级3条ok；ET当日完整提取info_id705、粗筛2次，usage缺失0，仍在自然处理中，未触限；未重启新闻处理进程。

## A-022 限额自然触发（ET 10-25，验证继续）

北京12:55左右只读：完整提取1500个info_id、粗筛120次，均达到设定上限；3120次调用、4434110 tokens（输入3979878/输出454232），usage缺失0，估费11.59元。已观察超限条目标full_daily_limit/screen_daily_limit并顺延ET10-26 00:00。A=1500 ok/1070 pending，B=1348 ok/830 pending，C尚未处理到；fiscal.ai队列仍有4822条，不能宣称C级验证完成。

重要口径修正：上述A/B为所有info_items，不能全部叫“新闻”。拆分已完成完整提取1500条中，SEC 8-K为1115、news为385；当前news成功分级A385/B1348，另有此前旧版本ok。现有共享enrich会把SEC等也计入同一1500额度，观察到SEC568、news465因full_daily_limit顺延。已验证硬上限生效，但“新闻可完整处理1500条”的业务能力尚不能据此确认；需求方需评估是否另派精确修复将非新闻与新闻条数额度分开。本轮不擅自修改已验收预算规则，继续独立观察C级清理和调用停止。

## A-022 ET10-25周日补采阶段收口

北京13:25左右只读核验：可执行队列为空，news已按新规则落库A385/B1348/C4772共6505条ok；C均rules_only_low_value，清理期间调用仍固定3120次，未新增模型。窗口仍pending1259条（full_daily_limit515、screen_daily_limit744），均顺延至ET10-26 00:00（北京10-26 12:00），永久hold为0。所有kind的完整提取1500（其中SEC1115/news385）、粗筛120、4434110 tokens、usage缺失0、估费11.59元，限额后调用停止已连续核对。

此阶段已确认C级免模型清理及硬限额/顺延实际生效；SEC/宏观等共享新闻计数额度的限制仍待需求方处置，未伪称业务目标全满足。首个交易日10-26统计与周一自然任务仍按原交接跟进，不重复启动补采或更改预算。

## B-062 部署运维 已收到／进行中 2026-10-26 00:18 北京

收到 A-014 补充三十三：PR79 merge `8c10f8f` 已验收合并，已核对 main `82c72c8f7df7d01fb867bf62cf9fa5fa220dfa85` 包含该合并。按 UD-A-47 安装该 main，仅重启 pages，并核验指定7个页面及 investor.css/investor.js 外部状态码。变更仅已授权页面部署，无迁移、权限、配置或其他服务重启；不占 A-022 开发任务位。

## B-062 已安装，外部验证发现交接差异 2026-10-26 00:23 北京

生产 head `82c72c8f7df7d01fb867bf62cf9fa5fa220dfa85`，包含 [PR79](https://github.com/XuQingsong/inves-cog/pull/79) merge `8c10f8f630fc2119821ffbcca325bebef410c9c5`。准确 PR head `de26466cf0a9b7b20668bbb873641dd85615c86e` 的 [phase1-blocking CI](https://github.com/XuQingsong/inves-cog/actions/runs/40207944236/job/121212822458) success；nightly skipped，Bugbot neutral/额度耗尽，不冒称这些检查通过。仅 pages 重启，其他原有 supervisor 服务 PID 与配置逐项保持、工作区干净。

外部实际结果：`/`、`/stocks`、`/account?date=2026-10-22`、`/account?date=2026-10-23`、`/trust`、`/s/AVGO?date=2026-10-22`、`/s/LITE?date=2026-10-22` 均200/text/html；`/investor.js` 为200/text/javascript。`/investor.css` 为404，未满足交接中该路径200的预期。原因已核实：`web/api.py` 仅注册 JS 地址，`investor_html.py` 读取 CSS 后内嵌，生产账户页实际包含与部署 CSS 文件完全相同的样式内容，JS引用存在。因此该404不代表页面漏载样式，不能声称九项全200。

下一步：需求方线上走查并确认是否接受 CSS 内嵌形式，或安排增加独立 CSS 地址；本轮没有跨线修改页面接口。代码安装与八项外部访问已完成，九项全200及最终页面验收未宣称完成。A-022后续自然运行仍按既定窗口跟进。

## A-023 已收到／进行中 2026-10-26 10:20 北京

已读 main `22c3bacd8d5f120100b384da4ecf93ba7cdc4e78` 的任务及 info-system-v2 §2/3.6/3.7/4。A-022已由需求方关单并被本单替代，取消原首日费用回报。本单解决新闻被逐条模型阻塞、VIX无备用与财经日历缺口；范围仅授权 ingest、交易仓库VIX读取、迁移、调度配置及测试。变更：新增固定名称Yahoo VIX系列、两张日历表/ET06:00采集、逐源健康记录及新闻断档监控、默认关闭逐条新闻模型开关；保留模型调用代码。先提交失败测试再实现；合并前不部署/迁移、不手工触发生产模型，不改B线读取端。上线后两交易日核验按本单新标准执行，原周一其他自然作业继续跟进。

## A-023 进行中（实现已送 PR81，完整 CI 修订验证中）

[PR81](https://github.com/XuQingsong/inves-cog/pull/81)，当前 head `0c12cbc`（完整 SHA 待最终验证回报），先失败测试 `5071ad6`，后实现 `5d151e322fc1fba6a4803a53f283f5343caf9193`。已实现独立 CBOE/Yahoo VIX、固定日历接口/迁移、逐源健康与新闻断流监测、默认关闭新闻粗筛/提取及异步新闻嵌入；旧 pending 保留正文、时间与审计后转 rules_only，B064 调用路径保留。新日历以真实响应夹具验证，v18 冻结回放90笔交易及收益未变；隔离 PostgreSQL 的迁移与角色/队列合同验证通过。

新闻缺口已只读核实：生产 scheduler 的显式任务列表遗漏新闻采集，采集作业记录亦有相应缺口；费用与模型队列不能替代采集任务。遗漏如何发生尚无证据，不归因于某个操作者。上线时必须核对实际任务列表，不能只修改安装模板；合并前不改生产调度。

首轮准确实现 head 的 [CI](https://github.com/XuQingsong/inves-cog/actions/runs/40259924478/job/121369865980) 为794 passed/2 failed：两项旧测试固定原调度列表，未纳入本单明确授权新增项。已保留原任务时间窗及其他服务约束，仅更新新增任务预期，36项相关测试通过，正在等待新 head 完整 CI；不把旧 head 或局部通过当最终通过。尚未合并、部署或运行生产迁移。已自行决定：Alpha fallback 用一次批量CSV后本地筛持仓/股票池，持久化ET日请求上限；Nasdaq经济日历使用真实验证可用的 economicevents 路径。下一步完整CI通过后送需求方验收，合并安装后再按两交易日标准验真。

## A-023 代码已完成，待需求方验收合并

[PR81](https://github.com/XuQingsong/inves-cog/pull/81)，完整 head `0c12cbcb1d2bfc4058439620737f3f99137efcf1` 的 [phase1-blocking CI](https://github.com/XuQingsong/inves-cog/actions/runs/40260337734/job/121371141158) success：796 passed、21 deselected，另2项环境检查通过。先失败测试与后实现历史保留，静态检查和真实数据库合同亦通过。nightly 为 skipped，Bugbot neutral/额度耗尽，不冒称通过。上述新闻缺口诊断和已自行决定项不变，无新增范围。

当前仅完成代码交付，未自动合并、生产迁移或部署。下一步由需求方验收合并；之后 A 执行已授权迁移与安装，核对实际调度补齐新闻及本单五项任务、默认新闻模型关闭，保留其他服务配置，并核实旧作业退出以防并发。随后连续两个交易日验证 VIX 当日值/来源、日历及持仓覆盖、新闻入库和新闻模型调用数；这些真实运行指标尚未发生，不以 CI 代替。原周一其他自然作业核验继续，A线自动化保持开启。

## B-063 部署运维 已收到／进行中 2026-10-26 12:50 北京

收到 main `f0edbb2829da82240267e93b0ce1d5cdaebfb4eb` 的 A-014 补充三十四；已核对 main 包含已验收 merge `30729468f9a9cc3a128f8913e3ddacd4dbdbf0f9`（PR80）。变更仅该已合并版本安装、pages/scheduler 重启及外部七页/五标题验证，无迁移或配置修改，不占 A-023 开发位。已只读确认生产为上次 B-062 版本、工作区干净，原有服务状态已留作对照。自动审批最初误判为 B 开发越界，补交 A-014 明确部署授权证据后只读检查已获准；不绕过审批。下一步完成安装及独立外部验证；预览实例仅在确认属于本项目后停止。

## B-063 部署运维 已完成

生产已安装已验收 [PR80](https://github.com/XuQingsong/inves-cog/pull/80) merge `30729468f9a9cc3a128f8913e3ddacd4dbdbf0f9`。准确 PR head `a3efadfa74fe6664db282e05d1c6b6732e26aea5` 的 [phase1-blocking CI](https://github.com/XuQingsong/inves-cog/actions/runs/40269690523/job/121399606110) success；nightly skipped、Bugbot neutral/额度耗尽，不冒称通过。仅 pages/scheduler 重启，其他原有运行服务 PID 与配置逐项保持，工作区干净；无迁移、手工业务补跑或模型测试。

独立外部验证：`/?date=2026-10-22`、`/?date=2026-10-23`、`/stocks?date=2026-10-22`、`/account?date=2026-10-23`、`/trust`、`/s/AVGO?date=2026-10-22`、`/s/BE?date=2026-10-23` 全部200/text/html。10-22首页五个标题「持仓与标的异动」「热门主题新闻」「滚动新闻」「财报日历」「涨跌排行榜」全部存在。本项目8091预览已核实目录与命令后精确关闭，端口停止监听。审批授权误判经明确A任务证据重新审查已解决，无剩余权限阻塞。

下一步需求方线上走查；当前只确认安装、访问与标题合同，不代替内容验收。A-023 仍为 PR81 待验收合并，两张日历表尚未部署，日历数据缺口须待该单安装后验真；本轮不重复旧迁移或补采，不自动合并，自动化保持开启。

## A-023 进行中（复核一修订已收到）

收到 main `e7b96c0b4e6bf658249c0304e3b987e3434fdd8c` 的复核：恢复配置预算150万；日历成功日期按来源/日期原子刷新，删除该响应已不包含的记录，失败日期与其他来源保持；嵌入开关改由调用方传入；补新闻健康恢复测试。变更：按复核明确授权执行日历局部删除，不扩表/权限；Yahoo真实收盘回补使用观测日作为realtime_start，将使缺失历史日期可读，部署前只读列明受影响交易日，不伪造当时已采到。先补失败测试再实现，同PR81送验，合并前不部署、不改生产数据。

## A-023 进行中（复核五项修订已推送）

PR81 head `9132f323d10595d63a75abc700dc22bd0c4a3394`，先失败测试 `a38bdcb` 后实现。复核1：配置恢复150万；2：两种Nasdaq日历整日响应成功后按日期/来源原子刷新，空响应清旧行，失败日期不写，其他来源保留，单元测试及真实PG改期测试通过；3：embedding collect显式接收include_news，默认关闭，CLI显式传入，缓存计划按开关隔离以免重用旧含新闻计划，真实PG双向开关验证通过；5：新测试证实下一次成功采集由JobRunner恢复AlpacaNews为ok、失败计数归零。目标13项通过，扩展本地49项通过，另1项因无Docker未执行；真实PG合同独立验证已通过并回滚。当前head完整CI仍在运行，未沿用旧通过结果。

变更（复核4）：Yahoo回补realtime_start为观测日，历史读取事后获得真实收盘值，不代表当时已采到。部署前只读核实10-01至10-23：有效VIX从所有既定源均缺失转有值的交易日仅`2026-10-23`；其余日期已有CBOE/FRED，VIX3M全区间已有CBOE。两条Yahoo序列本身此前均为空，拟新增日期`2026-10-01, 10-02, 10-05, 10-06, 10-07, 10-08, 10-09, 10-12, 10-13, 10-14, 10-15, 10-16, 10-19, 10-20, 10-21, 10-22, 10-23`共17个交易日。以上为当前快照，安装前重核自然新增数据；尚未实际回补。

已自行决定：按显式开关隔离嵌入缓存，避免关闭后仍提交旧计划。其余按复核执行。下一步准确CI通过后送需求方复核，未合并、部署或改生产数据/权限。

## A-023 阻塞（五项修订完成；最新main集成夹具冲突需跨线授权或需求方修正）

[PR81](https://github.com/XuQingsong/inves-cog/pull/81) 当前已推送 head `9132f323d10595d63a75abc700dc22bd0c4a3394` 的[自身分支CI](https://github.com/XuQingsong/inves-cog/actions/runs/40282026433/job/121437222733) success：800 passed、21 deselected，另2项环境检查通过。但同head与最新main的[PR合并检查](https://github.com/XuQingsong/inves-cog/actions/runs/40282030427/job/121437234654) failure：802 passed、1 failed、33 deselected。唯一失败为`tests/m10/test_b055.py::test_b063_calendar_vix_and_earnings`，B-063夹具向A-023已规定主键的宏观表插入两条同日期/国家/事件名/来源记录，触发UniqueViolation。不得以分支成功代替集成成功。

已准备最小夹具草稿：保持A-023主键，将重复事件分属两个来源以保留页面去重断言，补齐夹具DDL主键，不改页面实现。自动审批明确拒绝提交/推送该文件，理由是B线测试超出A线范围；未绕过、未推送该草稿。已直接告知用户：需要用户授权这一处跨线测试修改，或需求方自行在B线修正。授权到达前不继续该修改。所有A-023授权修订及历史回补影响清单已推送，其他不依赖此冲突的工作已完成；没有生产迁移、回补或部署。

本地已合入main的恢复点为`054ad1df953559283793390696e2c3646b03a6e4`（未推送），夹具草稿为未提交修改，保留以便获得答复后接续，不重置。下一步需求方/用户解决上述唯一测试范围决定后重跑准确head完整CI，再验收合并；自动化保持开启。

## A-023 已完成（复核二通过，待需求方合并部署）

收到 main `3f9f9ad347a4651be9c2aff146f9724824dfc342` 的复核二：五项修订全部通过；需求方通过PR82 merge `2beeb98`修正B测试，再更新PR81分支。现以远端完整 head `c447aeb1889dcb232488bd3add7d053dc02f6ab7` 为准，[PR合并phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40293718315/job/121474583908) success，[分支CI](https://github.com/XuQingsong/inves-cog/actions/runs/40293712868/job/121474565030) success（803 passed、33 deselected，另2项环境检查通过）。nightly skipped、Bugbot neutral/额度耗尽不冒称通过。此前唯一集成阻塞已解除，无需用户再授权本地夹具修改。

按审批要求先保存旧提交/草稿到本地备份分支与stash后，已同步远端提交、工作区干净；旧恢复点和草稿不再作为交付、不推送、不恢复执行，未绕过跨线拒绝。无新增业务决定；接受需求方明确的成功空数组清空同日期/来源行为，上线若发现偶发空响应按source_health证据回报，不自行改规则。

当前完成代码及离线集成验收，尚未合并、生产迁移、安装或真实回补。下一步需求方合并并追加A-014部署补充后，A再执行部署与两交易日真实运行验收，实际调度、VIX值/来源、日历覆盖、新闻入库及零逐条新闻模型调用仍须验真。自动化保持开启。

## A-023 部署 已收到／进行中

收到 A-014 补充三十五，已核对 main `2230398baabe6e069436a7461e8750f773835d40` 包含已验收 merge `221e3ed62c696cedbd4fcd6d9e1e7e387df301a7`。变更：仅执行本单两张日历表迁移、补齐生产scheduler现有列表中的news_poll/news_watchdog/vix_daily/earnings_calendar/econ_calendar，重启scheduler与独立ingest看门服务；按明确授权各运行一次三项新采集，并把旧新闻pending按规则收口，不调用模型。迁移管理员仅用于DDL，业务采集使用现有role_ingest，不改角色或其他服务配置。部署前已确认生产干净、仍为B063版本，真实进程清单已留作对照；先核查旧作业退出和重复运行凭据，远端有界执行并保留阶段进度。真实数据、外部页面及两交易日观察未验证前不宣称业务完成。

## A-023 部署及首轮真实采集已完成；连续两交易日验证进行中

已安装验收 merge `221e3ed62c696cedbd4fcd6d9e1e7e387df301a7`（PR81）。准确PR head `c447aeb1889dcb232488bd3add7d053dc02f6ab7` 的[PR合并CI](https://github.com/XuQingsong/inves-cog/actions/runs/40293718315/job/121474583908) success。指定日历迁移已提交一次；业务采集身份核实为现有最小登录`inves_cog_ingest`，管理员只用于DDL。仅scheduler及独立ingest看门服务重启，旧采集/处理进程确认退出，新enrich仅1个；其他原有运行服务PID、其他配置和生产工作区保持。

实际进程参数核验的scheduler任务列表：`bars_prefill bars_full wide_universe sec_submissions sec_index sec_atom m6_market_inputs issuer_profiles fred cboe finra fed_news news_poll news_watchdog vix_daily earnings_calendar econ_calendar`。原12项全部保留、追加5项；真实配置`news_llm_enabled=false`、`llm_daily_token_budget=1500000`。没有重跑旧迁移/补采或手工模型调用，手工三项新采集各运行一次，均已结束，无对应运行中作业。

首轮真实结果（2026-10-26 09:10:37 UTC独立只读核验）：VIX_CBOE及VIX_YAHOO的10-23值均为19.45（Yahoo原始浮点19.450000762939453）；VIX3M_YAHOO共17条，四个VIX系列本次各17条、合计68条成功。财报日历2512条；宏观日历响应134条、按规定主键去重后128条。未来10个交易日中财报覆盖持仓5个代码、股票池28个代码，具体代码清单存项目私有运行收据，不公开持仓明细。

逐源source_health：VIX_CBOE/VIX3M_CBOE/VIX_YAHOO/VIX3M_YAHOO均ok、各17条、最新数据2026-10-23；NasdaqEarnings ok、2512条、最新2026-11-06；NasdaqEconomic ok、134条、最新2026-11-07；AlpacaNews ok、首轮2645条、最新入库09:07:30 UTC，后续轮询374条亦ok。全部consecutive_failures=0、无错误摘要。Alpha备用本次未触发，不能冒称其真实调用通过。日历空响应按已验收规则处理，没有改为空响应保留。

新闻自然轮询已恢复。上线后实际新插入739条（不同于含重复项的轮询processed_count），新闻模型调用0次；10805条上线前旧新闻已标rules_only，剩余news pending=0，正文/时间/旧审计保留。指定外部`/?date=2026-10-23`、`/s/GOOGL?date=2026-10-23`、`/trust`均200/text/html。

私有部署、采集、独立验证收据已保存，可核对开始/结束/迁移摘要与覆盖清单；本轮已完成安装与首轮真实结果，未把进程存活当业务成功。下一步连续ET10-26与10-27两个交易日，在当日收盘数据采集后回报VIX当日值/来源、日历及覆盖、新闻实际入库与新闻模型调用。当前仍为10-26盘前，不能提前宣称两交易日完成；其他已授权自然作业继续，自动化保持开启。

## A-023 部署验收通过，待两个交易日自然运行

已收到 main `3746348375cac7a23bb38c98076460e99f4c982f` 复核三：需求方独立页面走查确认VIX19.45、财报日历及GOOGL财报信息，与首轮采集/新闻收口证据一致，部署和首轮真实采集验收通过。尚未关单；剩余仅ET10-26、10-27各在收盘采集后回报当日VIX值/来源、日历条数及覆盖、新闻实际入库和新闻模型调用。沿用已部署版本、实际调度和私有收据，不重启或重复手工采集；当前未到验收窗口。无新增决定或变更，自动化保持开启。

## A-024 已收到／进行中

收到 main `c22f7330cc466543c65c85f683f02ee7a37d1080` 的A-024：只为看盘接入盘前/盘中/盘后快照，不进入规则A。A-023后续两交易日观察保留为独立运维项。变更：新增固定接口intraday_snapshots、按交易日三时段频率调度及30天清理；范围仅ingest/迁移/调度及对应测试。先核实现有Alpaca免费权限可用feed、盘前成交和官方延迟口径，再按已核实接口实现；核实不清不猜测。只做有界只读行情探测，不改生产库、不触发模型、不换key/套餐。先失败夹具测试后实现，准确CI后送验，合并前不部署。

## A-024 进行中（数据源与延迟已核实）

有界只读实测同一现有key：SPY snapshots feed=sip为403（无最近SIP订阅），iex为200且有盘前成交，delayed_sip为200且有盘前成交；截止当前减16分钟的历史SIP分钟线为200，04:00 ET起有成交。本次共5次请求（含1次上一交易日日线复权验证），无重试、无模型调用、无业务库写入。官方说明：[snapshots](https://docs.alpaca.markets/us/reference/stocksnapshots-1)将delayed_sip定义为15分钟延迟；[FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)确认免费IEX与SIP历史15分钟限制；[历史bars](https://docs.alpaca.markets/us/reference/stockbars)支持all复权及asof日期。

变更/已自行决定：本单使用已验证delayed_sip全市场快照，不采用IEX作为全市场替代；as_of取latestTrade原时间，delay_minutes按注入采集时间减实际成交时间向上取整、且不低于已核实的15分钟套餐延迟，不把陈旧成交写成零延迟。仅存当日04–20时段真实成交，不将前一日成交伪装成盘前新行情；prev_close另取上一交易日历史日线all复权、asof当天，与当天原始成交处于同一当前股数/除息口径。真实SPY快照及日线响应保存为离线夹具。频率及30天清理按原任务，不改交易/页面或A023运维观察。下一步先失败测试后实现，同一A024分支交付。

## A-024 进行中（PR83已送验，完整CI运行中）

[PR83](https://github.com/XuQingsong/inves-cog/pull/83)，完整head `e6dc3ed275e702ca8b3cdb9139e358470d2bb0c6`。先失败测试`cd13dd0`（15 failed/7 passed），再实现；实际配置股票池59只，采集并集包含SPY/QQQ/IWM与池外持仓，不漏重复代码。真实SPY快照/前日all复权响应已作夹具。时间取原成交时间、延迟实际向上取整且至少15分钟、前日陈旧成交不入本日快照；缺前收盘留NULL并标记健康降级，失败不重试同槽。按三时段频率与交易日运行，30天清理仅限新表，不改规则A或页面。

目标与兼容回归61 passed，静态检查通过；真实本地隔离PostgreSQL已验证新表迁移、role_ingest写/role_web只读和严格早于30天清理，测试数据已回滚且测试库已停。准确head的phase1-blocking仍在运行，不冒称通过。下一步CI通过后送需求方验收，未合并、迁移生产或部署；首个交易日盘前首尾/条数及SPY公开报价对照待安装后自然验真。A023两日收盘观察继续，不重复启动。

## A-024 已完成（代码交付，待需求方验收合并）

[PR83](https://github.com/XuQingsong/inves-cog/pull/83)，准确完整head `e6dc3ed275e702ca8b3cdb9139e358470d2bb0c6` 的[PR合并phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40321185092/job/121566217489)与[分支CI](https://github.com/XuQingsong/inves-cog/actions/runs/40321096329/job/121565929968)均success：826 passed、33 deselected，另2项环境检查通过；nightly为skipped不冒称通过。先失败测试提交`cd13dd0`、后实现提交已保留。真实SPY响应夹具、交易日/假日/DST、三个时段频率、成交原时间与实际延迟、池外持仓并集、全市场delayed_sip及一致复权、无同槽重试、来源健康和真实PG30天清理/最小角色合同全部通过。

已自行决定项沿用先前已记录的已核实delayed_sip及真实延迟/复权口径，无新增范围。只读核实不等于生产安装或首日验收；当前未合并、未在生产建表或注册采集。下一步需求方验收合并并下发部署后安装，首个真实交易日核验盘前首尾时间/条数、SPY涨跌与Google/券商公开数据对照，保留各时点原行情时间、不伪造完整盘前覆盖。A023两个收盘运行窗口仍独立跟进，自动化保持开启。

## B-064 部署 已收到／进行中；翻译启动前预算阻塞

收到A-014补充三十六，核实PR84已合并，merge `a37acfd82a8e36de351ce34667ce614538214651`；准确head `040615c08d6b43658ec4d7b48e5d75e9a9a4139f` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40335211811/job/121614818457) success。变更：安装该版本、指定news_translations迁移、仅重启pages；管理员仅DDL，业务用现有最小角色。

启动前发现预算未闭环：translate_day的tokens只取初始值、循环不更新；calls按client.call累计，但Client每次可重试2次，真实尝试/记账次数可超过6；Client本身没有该任务日限额。先完成不依赖模型的安装/表/页面核验，news_translate暂不启动，不扩大预算、不修改B代码。需需求方/B线修正真实尝试计数和token硬限额后验收合并，A继续启动。

## A-024 追加范围 已收到／进行中

收到复核一：原实现通过，同一PR83追加15只ETF及13个Yahoo宏观代码。变更：两来源独立健康及失败隔离，保持美股三时段、同表/30天清理；先核实收益率单位，真实响应夹具先失败测试后实现。不采2年期、不改FRED/页面。原迁移无GRANT，role_ingest写/role_web只读继承M0 schema默认权限，真实隔离PG已验证。未合并前不部署A024。

## B-064 页面部署已完成；翻译启动阻塞

实际生产head `a37acfd82a8e36de351ce34667ce614538214651`，指定迁移已提交（SHA256 a98d6f7bcb1b2328bbc671a281f418745b93a9b7c79df829a32b7181865e6399），现有perception登录非管理员且具备新表读写。仅pages重启；其他运行PID与Supervisor配置保持，news_translate没有启动。15:26 UTC独立核验四个指定外部页面均200；今天首页日期2026-10-26并有“沿用…收盘”标注，数据区显示而非整页暂缺。部分栏目仍明示暂缺，不冒称全字段齐全。

翻译调用0、token0、翻译表0条；按页面候选逻辑只读统计80条、未译80条。另核实默认ingest登录调用page_candidates会在marketstate.rotation报InsufficientPrivilege；该服务按现有实现启动亦不能完成。未扩权或改B代码。需要需求方/B线修复读取身份（利用既有最小只读身份）及真实尝试次数/token硬限额，验收合并后A接续注册启动。页面/表部署真实收据与权限失败证据已保留；不能将本项标为翻译运行成功。

## A-024 进行中（追加来源取证）

13个指定Yahoo chart各一次请求均200，无重试/模型/业务库写入，真实响应保存作夹具。Yahoo原始5/10/30年当前分别4.814、4.980、5.298，前收4.805、4.988、5.315；Yahoo自身收益率报道与美国财政部同量级日收益率互证，这是直接百分比，不按CBOE期权标的的10倍指数口径再除10；基点变化=(last-prev_close)*100。下一步离线覆盖原时间、单位、实际延迟、前收以及异常响应。为来源失败隔离，同一scheduler新增内部任务yahoo_intraday，频率/窗口与intraday_snapshots一致，分别记录YahooIntraday/AlpacaIntraday健康；不新增常驻服务或时窗。原迁移权限不变。

## A-024 进行中（追加已推送，完整CI待返回）

PR83追加完整head `d912a6dbeba07f1fd99f5efd7787ac5d86ce3e87`。先失败测试`e8da608`（30 failed/4 passed）后实现；98项目标/兼容回归及静态检查通过。13个真实Yahoo响应原样入夹具，单位证据包含Yahoo收益率报道与财政部利率表，明确仅验证百分比量纲、不把不同产品/时间的数值说成价格一致。新任务yahoo_intraday同频率同窗口，逐代码错误继续，整源失败不影响Alpaca，HTTP无重试、持久开始时间避免同槽重试。原股票池/池外持仓并集保留并加15ETF；不改表/权限/规则A/页面。准确head CI仍在运行，原head成功不能替代；未生产部署。

## B-064 后续页面修复部署 已收到／进行中

收到A-014补充三十七（main `8cdfe7a016e4db20c8180535f3dcc7ce78146160`），PR85 merge `469f16a27ce35f27a9b522e7799ee7c5598c20ea` 已验收。按授权快进并仅重启pages，核验/与/stocks；不重复上次迁移，不启动尚有预算/读取身份缺口的翻译服务，其他运行服务保持。

## B-064 后续页面修复部署已完成

生产快进至PR85验收merge `469f16a27ce35f27a9b522e7799ee7c5598c20ea`，准确head `5efc16feadacc590956991435f96944168566a6d` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40347548455/job/121658403663) success。仅pages重启、其他运行PID和配置保持、工作区干净；服务器外部/与/stocks均200。未重跑迁移，翻译仍未启动，预算及读取身份两项缺陷仍待需求方/B线修复，不能把页面修复算作翻译问题已解决。

## A-024 已完成（追加代码交付，待需求方验收合并）

PR83准确完整head `d912a6dbeba07f1fd99f5efd7787ac5d86ce3e87` 的[PR合并phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40350168656/job/121667735576) success：881 passed、33 deselected，另2项环境检查通过。分支CI此刻仍在运行，不冒称通过；nightly skipped、Bugbot neutral。追加先失败测试`e8da608d7daee98dbd92407206a66a140d0f4073`后实现历史保留；目标及兼容98 passed、静态检查通过。逐项：15 ETF追加保留原池/持仓并集；13 Yahoo原始代码/source=Yahoo；真实响应夹具覆盖原时间、实际延迟、前收/缺前收、分钟线成对回退、错代码/未来/陈旧值拒收；三收益率百分比及基点换算验证；无2年期/无FRED变更；两来源健康/失败隔离、逐代码继续、无HTTP重试；同交易日三时段/假日/DST/持久开始时间避免同槽重试。表结构/30天清理不变，M0默认最小权限原真实PG结果继续适用。

单位证据：[Yahoo收益率报道](https://sg.finance.yahoo.com/news/ai-trade-rout-sparks-flight-to-treasurys-bond-yields-sink-chart-of-the-day-151821305.html/)直接将TNX标为5.05%；[财政部日收益率](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&field_tdr_date_value_month=202610&type=daily_treasury_yield_curve)提供同百分比量纲交叉核对。夹具记录4.980与前收4.988，对应-0.8基点，不缩放10倍。来源/时间不同，不声称两者价格完全一致。

已自行决定的内部Yahoo独立调度/延迟口径已先记录，无新增预算/权限。当前仅代码交付；A024未合并、未生产迁移或安装，盘前首尾/首日公开报价对照仍待合并部署后的真实交易日，不伪造完整覆盖。A023两交易日收盘观察继续，当前未到收盘窗口；自动化保持开启。

## B-064 翻译启动阻塞补证（离线，无真实模型请求）

用真实Client重试/记账逻辑及计数transport模拟：初始当日5次、49990 token，前两次Timeout后第三次成功，translate_day返回calls=6；实际transport和记账各3次，累计真实尝试8次，已知token50190，确认突破6次/5万授权上限。零真实模型/网络请求、未改B源码。另默认ingest读取marketstate.rotation权限失败已实测。需要需求方/B线修复并验收合并；A已完成独立的表/页面及后续页面修复部署，无需用户重复原授权。

A-024 CI收口：同一完整head `d912a6dbeba07f1fd99f5efd7787ac5d86ce3e87` 的[分支phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40350160852/job/121667704954)也已success（5m16s），与PR合并检查均通过。代码可供需求方最终复核；不自动合并、未生产部署。

## A-024 与翻译修复部署 已收到／进行中

收到A-014补充三十八，main `1af17152e093f7bc066fc8d3dbcb471c41ce0254` 包含A024验收merge `89fd55e85ba2be6271d4591432843c30b802aa59`与PR86翻译修复merge `b67661e14cde8732e0f47bec9ec98296db1d2f96`。PR86准确head `6e7a95357b890a7a5fa467018072bc734bf333d3` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40351762587/job/121673407804) success。已核实读取改为现有WEB登录、写用perception、重试0、每次请求前重读实际用量并预留估算，与新验收授权一致，不再等待同一问题答复。

变更：安装已验收版本、仅执行A024指定表迁移；scheduler现有任务只追加intraday_snapshots/yahoo_intraday；按安装模板只增news_translate程序，重启scheduler与pages并启动唯一翻译进程，其他服务/角色保持。管理员只DDL，业务仍用既有最小登录；不重跑B064表迁移/旧补采。今天已过盘前，真实首日只能报告部署后覆盖，完整盘前首尾待下一交易日自然运行，不伪造。先核查进程/表/已有收据，有界部署和真实采集用量核验后回报。

## A-024 部署及首轮真实行情已完成；盘前首尾待自然窗口

生产head `89fd55e85ba2be6271d4591432843c30b802aa59`，A024/PR86均已验收合并后安装。指定迁移SHA256 `3eb645a5a981d713c5f8261cc80311b398f81ff700b40e409870f281e51be820`已提交一次，既有最小登录权限独立核验通过，无角色/额外授权变更。只重启scheduler/pages并注册news_translate；其他运行PID与原配置字段保持。实际scheduler原17任务全部保留，仅追加intraday_snapshots/yahoo_intraday，旧scheduler确认退出。

16:02:41 UTC独立只读核验：Alpaca自然采集77条/77代码，原成交时间15:46:11.570021至15:46:25.289620 UTC；Yahoo13条/13代码，原报价时间15:46:22至16:01:29 UTC。两任务均已结束status=ok，两个source_health均ok、consecutive_failures=0、缺当前成交/前收均0。不是把命令发出或存活当数据成功。四个外部页面均200。

首次公开样本：SPY766.5658/前收759.97，as_of15:46:25 UTC，delay16；TNX4.984/4.988，as_of15:46:22，delay16；CL=F102.49/103.27，as_of15:51:29，delay11；GC=F4030.6/4007.9，as_of15:51:28，delay11。今日盘前0条，因为部署在ET12:01以后，不能补造盘前覆盖；下一交易日ET04–09:30自然首尾与收盘后汇总继续，A024尚未关单。

## 新闻翻译真实运行失败／已停止重复付费；需要需求方/B线修复协议

按PR86已验收修复启动后，唯一进程及WEB读取/perception写入身份均已核实；首个真实请求失败（llm_calls status=failed），input1328/output951，总2279 token，usage无缺失；译文表0条、当前候选80/未译80。PR86原先预算和读权限缺陷已解除，不重提旧授权。新阻塞：定稿提示词要求“只输出JSON数组”，但共享transport强制response_format=json_object并在返回后拒绝非dict，Client也只接受dict，translate_day又只读titles/items字段；协议互不兼容。没有保存/输出模型原文，不能断言未记录的原始返回具体形态；已确认代码合同矛盾与首个真实失败一致，继续仅做离线复现，不追加付费诊断。

已仅停止news_translate并确认进程0；行情scheduler/pages及其他服务继续，无额外真实模型调用。需要需求方/B线提交并验收统一提示词/调用器/返回解析合同的修复（提示词只读，A不改B代码），合并并下发后A立即接续启动与真实写入验证。不能将已记账调用或部署成功当翻译业务成功。

## A-024 首轮公开报价对照／翻译离线补证

Google公开页面本轮读到：SPY766.55、+0.87%（10-26 11:30:06 GMT-4）；Google TNX49.84（10:24:52 GMT-5，指数为收益率10倍，折为4.984%）；CLW00 100.94/前结算103.27（14:21:26 UTC）；GCW00 4034.30/4007.90（15:23:55 UTC）。链接：[SPY](https://www.google.com/finance/quote/SPY:NYSEARCA?hl=en)、[TNX](https://www.google.com/finance/quote/TNX:INDEXCBOE?hl=en)、[WTI](https://www.google.com/finance/quote/CLW00:NYMEX?hl=en)、[黄金](https://www.google.com/finance/quote/GCW00:COMEX?hl=en)。

与本库首批对照：SPY766.5658、约+0.868%，前收与Google涨跌相符，两个报价相隔约16分钟；TNX本库4.984%与Google49.84/10一致，前收4.988%，即-0.4基点，不能把49.84直接与4.984相减。WTI本库102.49，Google100.94，相差1.55，但Google报价比本库早约90分钟；黄金4030.6对4034.30，相差-3.7、时间差约28分钟。两商品前结算分别103.27与4007.90一致；Google连续合约与Yahoo当前12月合约的逐笔同合约/同时间对齐未取得，不能把量级/方向对照冒称精确同刻价格验收。一次直读较新页面能取得原报价时间但未解析到价格，工具重取不可访问，已收口不继续增加诊断；下一自然验收窗口保留明确时间/合约限制。

翻译离线补证：注入HTTP响应为定稿要求的1条JSON数组，transport实际发送response_format=json_object，抛“Dialogue response lacks a valid JSON object”；1次纯离线transport执行、0真实网络/模型请求，未修改B代码或定稿文档。新协议阻塞已明确同步，不再把预算/读身份已修复项当阻塞。翻译保持stopped，真实累计仅失败1次/2279 token、译文0/候选未译80，等待需求方统一合同修复并验收合并。行情和页面不受此局部停止影响。
