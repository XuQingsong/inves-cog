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

## 翻译提示词修复已收到；准确版本CI失败，尚未部署

最新main `988eea070fa4545490d6d7d791e5013f4ff19a8f` 由需求方修订只读定稿提示词，输出改为{"titles":[...]}，翻译规则不变；这是针对已回报协议冲突的实质修复，不继续等待同一答复。生产仍为 `89fd55e85ba2be6271d4591432843c30b802aa59`，真实news_translate为STOPPED，无重复启动或新迁移/模型请求。

新准确SHA的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40364645068/job/121718924930) failure：883 passed、1 failed、33 deselected。唯一失败`tests/m10/test_b064.py::test_translate_payload_headlines_only`（424行），测试以贪婪`r"\[.*\]"`从整个user提示提取输入标题，新增输出格式示例的数组被一并捕获，触发JSONDecodeError；失败不是此前旧预算/读取身份问题，也不是Docker清理退出码所致。已完成有界定位，无需再运行付费请求验证这一离线错误。

需要需求方/B线修正输入标题提取测试，使其区分输出示例与实际输入数组，并在准确SHA完整CI通过后确认部署；A不跨线改B测试或只读定稿，不以旧PR86检查成功替代新版本失败。准备已齐：已知改动仅定稿4行、生产干净且唯一翻译已停，既有6次/5万预算保留；收到通过版本后沿原授权接续，不重复迁移/重启行情。A023收盘验证和A024下一交易日盘前窗口仍独立跟进。

## PR88翻译恢复 已收到／进行中

收到A-014补充三十九：PR88验收merge `81dad2f2899525426b7179c25901e4f4c3aa6841`统一定稿/解析为titles对象，修正输入标题测试，坏格式批次记账后丢弃。准确head `871a0ab6eddbd0230717fe2e24f089fa4243ce1f` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40365829547/job/121723134705) success，先前988eea0的唯一测试阻塞已解除，不再等待同一答复。

按授权快进该merge，仅重新启动已有news_translate，其他服务/配置不动、不重复迁移。接续前核查实际进程为0及当天剩余调用/token预算，保留此前失败1次/2279 token；不重置预算。不做额外手工模型测试，观察首轮自然任务真实记账/写入/候选未译数，失败则有界定位避免重复付费。收到真实结果前不称翻译恢复成功。

## PR88翻译恢复 已完成（实际写入及外部页面已验真）

生产已安装验收merge `81dad2f2899525426b7179c25901e4f4c3aa6841`（PR88，准确head `871a0ab6eddbd0230717fe2e24f089fa4243ce1f` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40365829547/job/121723134705) success）。仅启动既有news_translate，进程独立确认1个；其他所有运行PID、Supervisor配置及工作区保持，没有重复迁移、重启行情或手工模型测试。

17:22:43 UTC独立只读核验：恢复后的第一次真实调用17:22:19 UTC status=ok，input1279/output928、共2207 token；按真实写入时间范围独立统计该批50条。第二次17:22:27 UTC亦ok，input1172/output744、共1916 token，写入40条。恢复合计2次成功/4123 token/90条译文。包括此前失败1次/2279 token，当天累计3次/6402 token；usage无缺失、未重置预算，仍在6次/5万上限内。

当时页面候选90条、未译0条，翻译表90条。外部首页200，独立读HTML匹配到54条已写入中文译文（只输出数量，不输出新闻原文），确认实际展示有效，不把记账/进程存活当业务成功。上述是17:22时点快照，后续新增新闻可能等待下一自然批次，不能宣称未来始终未译0。部署/恢复、调用及页面验证私有收据已保存。

此前数组/对象协议及988eea0测试阻塞均已解除，不再提醒用户处理这些已解决事项；无新增用户决定、预算、权限或跨线代码修改。下一步沿既有交易日自然调度及日预算继续；A023两次收盘验证、A024下一交易日完整盘前首尾仍待各自窗口，自动化保持开启。

## A023首日收盘运行核验／A024与翻译日终核验 阻塞（2026-10-27 02:47 UTC起）

按已授权窗口，ET10-26收盘采集后开始独立只读核验。最新main/control仍A运行，已部署版本最后核实为`81dad2f2899525426b7179c25901e4f4c3aa6841`；没有新任务/迁移/模型授权变化。ET10-26 VIX、日历、新闻实际入库和零逐条新闻模型调用、翻译日终用量以及快照汇总均未获得本轮结果，不把未返回当作0/失败/通过。A022已由A023替代、取消旧首日费用回报，本轮不恢复该旧要求。

有界诊断证据：原55秒signal/查询10秒上限的只读核验未返回，本地SSH客户端后来仅精确结束PID94762，不宣称远端查询已退出；没有远端业务作业重跑。单独SSH读时钟成功；公开首页curl连接5秒/总10秒限制下HTTP000、exit28；本项目WEB最小登录只读数据库探测（连接/查询5秒、外层25秒）超时；Supervisor unix socket只读getAllProcessInfo在6秒内零字节返回、curl28。主机uptime负载22.93/21.96/20.67；内存7685MiB、available2671MiB、swap使用538MiB。只读本项目进程列表12秒超时，未取得可精确判断已退出/可安全重启的业务进程证据。以上显示页面、DB探测、监督接口响应异常，但未证实根因为CPU、IO、数据库或其他竞争，不将负载值直接当根因。

已做：保持现有部署、预算及业务数据，不追加模型调用、不重跑收盘采集、不盲目重启服务/共享数据库/主机；收盘核验查询未成功，旧17:22译文90条及6402 token只是已核验历史时点，不能冒称当前状态。诊断已收口，不无限重置批次。

用户受影响：公开页面本轮不可及时访问，首个交易日收盘与日终验收无法验真。需要需求方/服务器运维检查并恢复宿主机及本项目数据库、Supervisor响应；若需A执行共享数据库或主机受控恢复，须明确该新增运维授权范围（既有授权仅指定迁移、scheduler/pages/news_translate等定点部署，不包含主机/共享DB重启）。已在用户对话直接说明。恢复后先核对本项目真实进程/只读查询是否仍在，再读已有自然作业结果，不重跑/伪造收盘或重复付费。A024下一交易日盘前窗口仍保留，原自动化保持开启。

## 运行阻塞原因排查 进行中（UD-A-50）

用户在本对话直接要求“排查原因”。据此继续有界只读主机/本项目进程排查，不重启主机/共享DB、不修改业务数据或其他项目。已确认2个逻辑CPU、负载23.38；IO PSI最近10秒some99.17%/full56.30%，memory PSI some64.95%/full57.89%。页面、scheduler、supervisord及M9等均D状态/wchan=folio_wait_bit_common（等待文件页），不是已证实的数据库锁或单纯CPU满载。

03:12:36至03:12:39 UTC内核计数：pgmajfault增加5861，workingset_refault_file增加90827，swapin仅1页/swapout0；vda读取增加7585次、850096扇区（约138MiB/s），读累计耗时增加87569ms，队列27→31。当前存在大量文件页重复调入和磁盘读队列，直接解释页面及监督程序不及时响应；不能以历史累计值或swap已用538MiB误说正在大量换入换出。项目PSS较大者M9约1.41GiB、daily_modules约0.85GiB、scheduler约0.74GiB，尚不能仅凭占用量归咎某一任务。磁盘容量查询超时、内核日志无读取权限，底层盘故障/限速尚未排除；继续一次进程级计数差定位，不追加业务负载。

## 运行阻塞原因已定位，恢复尚未执行／待账号级限额变更确认

UD-A-50排查结果：inves-cog服务自身memory.high/max均max；限制来自父级user-1002.slice：memory.high=4294967296（4GiB），memory.max=5368709120（5GiB），cpu.max=150000/100000（1.5核）。父级memory.current=4307492864（约4.01GiB），服务memory.current=4103647232（约3.82GiB），父级memory.events high=46320508、历史oom/oom_kill各1。结合当前IO/memory PSI和3秒大量文件页refault/主缺页/磁盘队列，已定位账号级软限额持续内存回收造成文件页抖动及全组响应阻塞；主机仍有约2.6GiB可用，不是简单物理内存耗尽。CPU限额是附加约束，不将其当主要IO阻塞原因。此前PSS数值为kB：M9约1.35GiB、daily_modules约0.81GiB、scheduler约0.71GiB，修正此前近似单位表述。

同时精确识别上一轮遗留只读诊断PID3531419（服务器10:49:15启动）、3533211（10:52:48启动），均PPID1/python stdin，与本任务两次查询对应。清理命令也受阻超时，尚未独立确认这两进程已退出，不能把本地SSH断开或信号命令发出当退出。它们增加读盘，属于本轮应清理的自身遗留；不据此认定它们是最初触发原因。

用户追问“问题解决了吗？”：明确答复尚未解决，未修改账号限额、未重启共享DB/主机、尚无页面恢复证据。可审阅的最小恢复方案：只把父级MemoryHigh由4GiB提高到5GiB，MemoryMax仍5GiB、CPU仍1.5核；不新增云资源费用，先解除软限额回收，再确认遗留诊断退出、页面/DB/Supervisor响应及自然任务结果。若效果不足再据证据另议，不先扩大硬上限。该设置影响整个服务账号，超出现有定点部署范围，需用户明确确认；没有把排查授权当成账号级资源变更授权。原自动化保持开启，等待确认期间不重置诊断批次或重跑业务。

## 账号资源限额恢复 已收到／进行中（UD-A-51）

用户在本对话明确授权：“需要改的就直接改，之前的限额可以直接去掉了。”据此解除本次已定位父级user-1002.slice的MemoryHigh=4GiB、MemoryMax=5GiB及CPUQuota=150%限制，改为无限制；不扩到未核实的其他资源配置，不改模型6次/5万token及其他模型预算、不改DB角色或数据。先保留当前设置及持久配置来源证据，执行账号级限额解除，再核验内核实际值、PSI/读盘、清理本轮已识别只读诊断残留、验证本机和外部页面/DB/Supervisor及自然作业。用户已授权，无需再次确认，不把命令发出当恢复成功。

UD-A-51恢复阶段：systemctl读取备份15秒超时，未执行属性修改；普通账号sudo直接写memory.high的40秒外层亦未确认完成，不能视为限额已解除。现有root SSH认证明确失败，未改认证或寻找其他凭据。继续用户已授权范围内最小恢复：精确核对并临时SIGSTOP本项目M9/daily_modules/scheduler三个大进程，降低文件页抢读；先清理自身两个已核实只读残留，再通过既有sudo解除内核限额并持久化。执行链设超时与EXIT/HUP/TERM恢复CONT，不停共享DB、不改模型预算；若命令失败也恢复三进程并如实回报，不把信号发出当退出或业务成功。

UD-A-51恢复推进：短暂SIGSTOP三任务后root sudo仍D状态、25秒强制超时；三个业务进程已发送CONT，内核限额仍旧值，未伪称成功。已核实sudo为/usr/bin/sudo，旧恢复sudo进程取得root身份后阻塞于IO，问题不是新授权不足。进一步最小恢复：仅临时SIGSTOP本项目supervisord阻止自动拉起，终止占用最大的本项目M9进程释放约1.35GiB，然后执行同一已授权限额解除并CONT监督进程，让其按原配置恢复唯一M9。设置超时及EXIT/HUP恢复监督进程，不停DB或其他项目，不手工补跑M9/模型；恢复后核对旧PID退出、唯一新PID及真实提交/作业前缀，不把自动拉起当业务成功。

UD-A-51恢复实况：仅重启M9后其旧PID807430已Z/释放内存，账号memory.current降至2612703232；sudo不再挂起，返回明确“a password is required”，说明现有SSH账号没有免密管理员操作能力（先前sudo进程显示root不等于认证已通过）。限额未修改。监督进程已CONT后M9自动拉起，memory.current又回升至4296028160、页面核验仍超时。现有root SSH认证失败；已连接Desktop Commander只有离线Mac，无服务器管理员通道，未绕过认证或改密钥。继续最小可行缓解：仅将本项目M9在Supervisor中暂时STOPPED，防止内存再抖动；保留页面/新闻/行情等服务，待管理员完成一次账号限额解除后再恢复M9。用户已经授权，不再索取同一授权；所缺是有效管理员执行通道。清理两个自身诊断已发KILL，待恢复后独立确认。

## UD-A-51 可用性已缓解；账号限额解除仍被管理员认证阻塞

本项目唯一M9已在Supervisor中STOPPED；旧/重启大进程均回收，父监督2695828已恢复Ss，页面3178296 Sl、scheduler3178027 Rl。两个自身遗留诊断3531419/3533211经独立ps确认均不在；未将断开SSH当退出。其余服务均RUNNING（原embedding本就EXITED）；watchdog现为3578688，其原进程在压力期间发生自动更换，未手工重启该服务。未恢复M9以免再次触发全组抖动；已提交的ET10-26 m9_overlay=ok、m9_shadow=degraded均有ended_at且12:35 UTC前结束，无运行中前缀，不补跑/改审计。

独立恢复证据：memory.current从约4.0GiB降至2178138112（约2.03GiB）；IO PSI avg10 some0.19%/full0.00%，memory PSI avg10 some/full均0.00%。本机首页200/6.28秒，外部首页200/4.87秒；数据库只读查询成功取得收盘结果。恢复的是网页/数据库及监督响应，不冒称所有自然调度已追平；AlpacaNews最后成功仍00:41 UTC，需后续确认新轮询推进，不能用进程RUNNING替代。

账号实际MemoryHigh仍4GiB、MemoryMax5GiB、CPUQuota1.5核。释放内存后，sudo -n -l及准确的sudo -n systemctl set-property命令均明确返回“a password is required”，root SSH现有密钥认证失败，Desktop Commander没有在线服务器设备。用户已明确授权，并非等待重复批准；缺的是有效管理员认证/控制台执行通道，没有绕过认证、读取密码或更改密钥。需要服务器管理员在已认证终端执行一次：`sudo systemctl set-property user-1002.slice MemoryHigh=infinity MemoryMax=infinity CPUQuota=infinity`。之后A读取内核值、恢复唯一M9并核验稳定性。当前不能声称限额已删除或完全解决；模型调用预算未改。原自动化保持开启。

## A-023 第一交易日收盘核验已完成（ET2026-10-26）；第二日待自然窗口

页面/DB响应缓解后，于2026-10-27 04:33:43 UTC独立读取自然作业已有结果，未重跑采集/模型。生产head仍`81dad2f2899525426b7179c25901e4f4c3aa6841`。VIX当日18.389999389648438（展示18.39），来源VIX_YAHOO；CBOE当日VIX缺记录、其接口成功但latest_data_at仍10-23，不能把health=ok当新鲜。当日VIX3M_CBOE19.94，Yahoo19.940000534057617。自然vix_daily在00:45:29–31 UTC完成ok/71条，bars_full在00:20–00:29完成ok/226540条。财报日历2512条，宏观日历128条（响应134按主键去重）；两Nasdaq来源均ok，最后10:00–10:01 UTC完成。新闻ET00:00–次日00:00实际新入库2935条，均rules_only/ok；A023安装后逐条新闻模型调用0。

完整ET日旧调用另有1473次（粗筛47、提取713、news_card713），合计1919703 token，全部早于A023安装，不能说该日从午夜起0，也不能算作本次恢复新增费用。A022旧首日费用回报已取消，不恢复旧要求。第二个交易日ET10-27收盘后仍须同口径核验，当前未到窗口。

## A-024与翻译首日自然结果（覆盖范围如实保留）

A024盘前0条（中午才部署）；regular/post已存Alpaca693/223条、Yahoo113/29条，两源最后23:00 UTC采集ok，缺前收0；相同原时间重复采集按主键更新，不将批次processed_count直接当新增行。下一交易日盘前首尾仍待ET04–09:30自然运行，尚未关单。

翻译ET10-26自然调用累计6次、9523 token（1失败+5成功），译文143条，达到6次上限但未达5万token；按当时page_candidates函数窗口ET04–次日04读取候选101条，其中未译49，后续新增新闻仍保留英文，属于预算上限后的已知覆盖限制，不伪称全天未译0。上述窗口与新闻入库ET午夜日统计明确区分；本次核验没有新模型调用。

## B-065页面部署 已收到／进行中

收到最新main `efe01928308a4bc3511cde710e65a12b451edd1a` 的A014补充四十，PR87 merge `f7a361822b94e45b91bd08d7537eb0d569aea22a`已验收，范围仅web页面。按授权快进并仅重启pages，核验/与/stocks外部状态及ES=F/^TNX/CL=F/GC=F今日快照展示；不重复迁移/模型任务，不恢复仍因账号限额暂缓的M9。最新合并规则由需求方验收后直接合并、A仍不得合并，已读并遵循；不将B065部署当作UD-A-51账号限额已解除。

UD-A-51命令纠正：用户截图显示此前提供的CPUQuota=infinity被systemd拒绝；这是A给出的参数错误，不能把该命令当已生效。已核对systemd官方resource-control手册：CPUQuota置空用于清除配额。正确管理员命令为`sudo systemctl set-property user-1002.slice MemoryHigh=infinity MemoryMax=infinity CPUQuota=`，两内存参数仍infinity。已在用户对话更正，所有本地待执行恢复脚本同步替换错误参数；实际值仍须读取核验，未重复执行需密码的命令。用户既有UD-A-51授权持续有效，不再索取。

## UD-A-51 管理员执行已核验，恢复M9进行中

用户再次截图显示已在管理员终端成功执行正确命令（CPUQuota置空），未报错。A独立读取内核实际值已确认MemoryHigh=max、MemoryMax=max、cpu.max=max 100000，原4GiB/5GiB/1.5核限制均已解除；不是只凭截图或命令发出宣称成功。用户既有授权不重复索取，模型预算保持。沿此前已核实M9作业已结束前缀，仅恢复唯一M9，不手工补跑历史/模型；核验账号内存/PSI、页面/DB/Supervisor稳定后回报完整恢复。同时接续已收到的B065仅页面部署。

## UD-A-51 已完成（限额已解除，M9及可用性恢复已独立核验）

管理员执行正确命令后，05:08:39 UTC独立核验：memory.high=max、memory.max=max、cpu.max=max 100000；M9唯一实例3599229已恢复，无重复进程、运行中M9/其他非enrich作业前缀为空。memory.current=2850353152（约2.65GiB）；IO PSI avg10 some/full均0.00%，memory PSI avg10 some/full均0.00%。两项自身遗留只读诊断已消失；监督服务正常，不再处于D状态。

用户可见核验：外部首页与/stocks均200，数据库只读查询成功；AlpacaNews已自然推进到05:00:28 UTC、health=ok，表明新闻轮询重新推进，不只看PID。未手工重跑业务/模型/补采，无DB/角色/规则A修改，全部原模型预算保持；之前资源认证、命令参数及账号限额阻塞均已解除，不再让用户处理已完成事项。持续接单授权和自动化不变。

## B-065 部署已完成（真实展示已核验，新交易日采集尚未到窗口）

生产已安装PR87验收merge `f7a361822b94e45b91bd08d7537eb0d569aea22a`。准确head `0e924e0f7e9ad16ffe308ba1b947e98efa932bf1` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40363180265/job/121713758622) success。只重启pages，其余当时运行PID和配置保持、工作区干净，无迁移或模型调用。

外部/和/stocks均200。今日ET10-27 01:08默认首页顶部行情条存在，ES/^TNX/CL/GC均为“—”：数据库只有10-26快照，当前尚未到ET04:00采集窗口，不将昨日伪装成今日。显式10-26页的四项实际显示：标普期货7718.00、美债10年4.99%、WTI101.33、黄金4027.30；分别与表中原值7718、4.986、101.33、4027.3的显示格式一致。Yahoo原时间：ES/CL22:50:43 UTC、GC22:50:22 UTC、TNX18:59:52 UTC；没有改原时间或延迟。B065页面部署及已有日快照展示已通过，今日首批数值/完整盘前首尾仍待ET04–09:30自然窗口，仍跟进A024，不提前宣称当日采集通过。

## 用户报线上新闻为空：原因已核实为页面跨日窗口（非token耗尽）

用户在本对话询问“线上新闻为空，是不是llm的token用完了？”已于2026-10-27 07:22:55 UTC（北京15:22:55、美东03:22:55）完成只读核验，生产head仍`f7a361822b94e45b91bd08d7537eb0d569aea22a`。AlpacaNews健康ok，最近采集07:20:03–32 UTC完成、processed_count2466（含重复，不冒称新增）；最新published07:16:30 UTC、最新first_seen07:20:31。美东今日午夜后发布52条（00时6、01时14、02时16、03时16），今日首次入库91条。采集并非空/停摆。

页面`web/brief.py::_day_window`固定从所选日ET04:00至次日04:00，`_day_news`直接以该窗口过滤published_at。默认今天已是10-27，但当前只有03:22 ET；窗口起点尚在未来08:00 UTC/北京时间16:00，符合窗口0条。因此今天页面把已有52条凌晨新闻全部排除，是跨日/盘前前段展示窗口缺陷，不能当“没有新闻”或归因LLM token。根因证据为线上计数及准确已部署源码，不调用模型或采集重试。

预算核验：今日尚无news_translate调用/写入，翻译计划ET04:00后才开始；其他任务已知当日token489687（另7次failed_usage_missing未知用量，不伪称精确剩余额度），没有token触顶导致原始新闻不可见的证据。原始新闻走rules_only、页面能保留英文；昨日翻译达到6次调用上限/9523 token也只影响译文覆盖，不会删掉新闻。

已直接向用户说明原因。页面层由需求方/B线处理，A不跨线改web、不擅自改变新闻日界或分配B任务编号；建议需求方明确并修正“今天在ET00–04应承接前窗或显示午夜以来新闻”的展示行为，保留真实发布时间及跨日标注。采集时段/模型预算无需因此扩大。问题与此前已解除的账号限额不同，不重新索取恢复或预算批准；未把该页面缺陷说成已经修复。

## A-025 已收到／进行中（紧急，全局费用上限与隔夜宏观）

收到main `466f0cd9a8f5ef710a70f2aa342e1fe0c88280be`紧急A025，优先当前A线开发；A023第二日收盘/A024盘前首尾保留自然运维观察。范围按明确授权仅llm/ingest/config/迁移/调度/测试，不改web或trading。变更：移除配置150万被5.5M替换，全共享调用层跨task美东自然日30万硬上限（失败/缺usage预估计入，发请求前检查、超限defer）、非新闻默认rules-only保留审计、模型脚本显式allow/max参数、全测试禁真实模型、Yahoo宏观隔夜小时采集及overnight CHECK；股票时段不变。

先只读核实现有全调用链、用量记录和脚本入口，保留先失败夹具/测试提交再实现；不触发真实模型、生产迁移或历史补算。费用预算是本次用户经需求方新授权，不沿用先前扩大上限；翻译6次/5万仍同时生效。共享全局上限需防并发和失败漏记，设计后先在status记录新增合同/表再实现。紧急止损截止ET10-27 23:30（北京10-28 11:30）：若仍未部署，先证明enrich停止对新闻rules-only显示的影响，再按任务条件处理，不提前盲停。代码准确CI通过并经需求方合并后才部署，无新增自行决定范围。

## A-025 第二版已收到／进行中（替代首版，全部模型改动暂缓）

最新main `89b0107390f83d15160bf5f92873ae7645d973ed`任务明确替代第一版：本单不修改任何llm、token预算、非新闻处理或模型脚本。此前ACK仅记录首版，未实现模型改动，立即转为分钟级行情。变更：Alpaca股票ETF交易日04–20每分钟；Yahoo白天每分钟、交易日前夜每15分钟及周末BTC例外；wide池09:30–16每5分钟新表ingest.wide_snapshots；intraday CHECK增加overnight；同原时间DO NOTHING；健康15分钟汇总、Yahoo连续失败指数退避最长15分钟并持久化；7天后按每代码/源/半小时保留原始观测、30天清理，wide只留当日与上一交易日。不改web/trading/日终任务，不提前生产DDL。

限频已核对Alpaca官方文档 https://docs.alpaca.markets/us/docs/about-market-data-api ：Basic历史REST200请求/分钟，支持批量snapshots。分钟股票1次批量、wide每5分钟分批及前收日缓存，远低于200；必须识别429并停止该Alpaca采集路径，记录明确限频阻塞，不擅自降频。现有源权限沿用delayed_sip，不购新套餐。Yahoo没有已承诺免费频率，按任务频率且失败退避，不宣称保证约15分钟延迟；原始as_of和实际延迟如实保存，尤其收益率并非持续交易。

## A-025 第二版进行中：PR90已提交，准确head CI待完成

PR https://github.com/XuQingsong/inves-cog/pull/90 ，head `20937bdbb8a601c40da8e93d22818f88209d2ba6`；先失败测试提交`530de79`（11失败），后实现`8099920`及导入排序修正。准确PR CI https://github.com/XuQingsong/inves-cog/actions/runs/40470763936/job/122077059496 当前pending，不能当通过。

实现按第二版：股票/宏观/宽池各自独立Supervisor程序，避免日终/SEC长任务阻塞分钟更新；行情专用调度不会拉起enrich，按下一分钟边界唤醒，原日终程序保持。范围不变的批量股票与ETF、白天每分钟/隔夜每15分钟Yahoo、宽池每5分钟；休市BTC例外，原始报价时段overnight。前收按交易日/批次缓存，缺值也缓存空值不每分钟重复查询；Yahoo整源连续失败1/2/4/8/15分钟退避，部分代码失败不拖停正常代码。重启保留退避/健康计数、任务数据库锁防并发；Alpaca429持久化停两条快照路径并待操作处理，不降频。复用source_cursors保存状态，无额外状态表/角色。15分钟source_health汇总成功失败数/最新as_of/退避。新迁移0008仅overnight CHECK及wide_snapshots表；同原时间DO NOTHING；7天后半小时首条原始观测（UTC半小时桶避免夏令时重叠小时合并），30天清理；宽池只留当日和上一交易日。

本地证据：相关M1/服务配置/A016回归159 passed；新增专项最终23 passed（不含容器PG入口）。独立临时PG:55423真实应用0008并通过重复键不覆盖、7/30天压缩、宽池两日清理、role_ingest写/role_web只读；数据回滚。ruff及diff检查通过。本机直接全套pytest缺容器环境/依赖导致大量环境失败，另发现服务列表旧断言已按授权配置改动更新并经相关回归通过，不冒称全套本机通过。正式准确headCI仍待返回。

没有模型预算/非新闻处理/脚本改动，没有真实模型调用、历史补采或生产DDL/安装。下一步检查正式CI、失败则修复，交需求方验收合并后部署并采首交易日真实证据；Yahoo收益率等非持续交易，不承诺伪造15分钟新鲜报价。持续自动化保持。

## A-025 第二版 已完成（代码交付；待需求方验收合并，尚未部署）

PR https://github.com/XuQingsong/inves-cog/pull/90 ，完整head `20937bdbb8a601c40da8e93d22818f88209d2ba6`。该SHA的PR [phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40470763936/job/122077059496) success；同SHA分支检查 https://github.com/XuQingsong/inves-cog/actions/runs/40470738209/job/122076976760 success，正式干净容器918 passed/33 deselected，另2项CI断言通过。此前本机完整环境缺失已由正式容器CI验证收口，不遗留为代码阻塞。

按第二版1–6自验：1) 股票ETF04–20每分钟批量+日缓存前收，官方Basic200/min已核对，429持久停两个Alpaca快照任务；测试test_no_http_after_actual_alpaca_limit_response。2) Yahoo白天1分钟、夜间15分钟/周末BTC例外、真实overnight及重启退避；test_schedule_each_minute_and_overnight_quarter_hour、test_future_closure_holiday_and_fall_back、test_persisted_failure_backoff_recovery_and_quarter_hour_health。3) wide交易日09:30–16每5分钟，included宽池200代码分批，独立新表；test_wide_scope_and_duplicate_insert_contract。4) 重复原始as_of跳过，15分钟健康汇总，test_success_health_one_aggregate_each_fifteen_minutes、test_minute_collections_never_overwrite_original_snapshot及真实PG重复键测试。5) 7天保分钟/其后半小时原观测/总30天、wide当日与前交易日及继承权限，test_a025_real_pg_dedup_retention_and_roles正式CI通过。6) 原日终任务/其他程序保持，新增三个独立无enrich行情worker；A018配置测试、A016程序集合及test_dedicated_scheduler_does_not_spawn_model_enrichment通过。

自行实现细节已记录：利用已有source_cursors持久化轮询/前收缓存，不另建状态表；独立三个进程避免长任务阻塞；UTC半小时桶保留夏令时重叠小时；Yahoo部分失败不拖停仍有效代码，整源连续失败才退避；未获取真实延迟保证的代码如实标旧。未改任何模型策略、预算、web/trading/docs/golden，无真实模型调用/历史补采/生产DDL。A不合并PR；下一步需求方验收合并并下发部署后，安装0008和对应服务配置，仅 then 采集首交易日所需真实证据。未将代码完成说成线上行情已变为分钟级。

OPS-A024盘前观察：2026-10-27 08:04:57 UTC（ET04:04）只读核验，今日pre共Yahoo1条，原as_of08:00:36、fetched08:00:42；Alpaca04:00批次0条，两来源degraded。此时delayed SIP尚不足以返回ET04:00后的15分钟延迟成交，Yahoo四公开样例当日0，不用旧日替代或提前认作全盘前验证完成；保留ET04–09:30自然窗口结束再回报首尾。未手动补采或模型重试。

## A-014 补充四十一 已收到／进行中：部署B-066

收到main `33d4db736c4ea362c38a4d3d024d8f28f0864f07`部署指令。PR89 head `1e171b7d5ee2226745c19fa8e8987ad103106150` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40479506220/job/122105958683) success，验收merge `85adfbeb00dcc0f47b39b3c3f7313dda2647e60b`已在main。先核对生产工作区/实际进程/版本，按授权快进到该merge只重启pages；核验/、/stocks、/account、/trust以及首页“数据更新至”与最近24小时新闻，再精确识别停止8091的/tmp/b063_serve.py和b062-preview预览进程并确认实际退出。变更仅页面安装和指定预览下线，无迁移、模型/补采或其他业务重启；A025仍未合并，不提前安装0008或新行情服务。

## A-014 补充四十一 已完成：B-066已上线，新闻展示恢复

生产完整head `85adfbeb00dcc0f47b39b3c3f7313dda2647e60b`（PR89 merge），准确开发head `1e171b7d5ee2226745c19fa8e8987ad103106150` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40479506220/job/122105958683) success。生产工作区干净，快进到已验收merge；仅pages PID变更，其他所有当时运行PID保持、Supervisor配置字节保持，无迁移或模型/采集补跑。

09:38:30 UTC独立外部核验：`/`、`/stocks`、`/account`、`/trust`全部200；首页顶部实际文字“数据更新至 北京 17:30（美东 05:30）”。首页显示“最近24小时”，实际新闻DOM行74（含折叠/分组，不等同库内总新闻条数），首页refresh-today标记开启。其余三页该刷新标记未开启，未据此宣称所有页面均每分钟刷新。只读库内最近24小时2546条，最新发布时间09:23:44 UTC；此前ET00–04窗口排除新闻的用户问题已通过新窗口代码及真实非空页面核验恢复，不归因模型token耗尽。

真实公开报价仍保留原始时间：SPY765.75，as_of09:14:39 UTC、09:30:33采集；ES7721.25、WTI102.1、黄金4009.2原时间09:20:32、09:30采集；10年收益率4.986%最近仍10-26 18:59:52 UTC，不伪造新日新报价。顶部17:30为所用快照最新采集时点，不等于各代码原报价时间；A025仍待验收合并，线上采集没有擅自改成分钟频率。

按明确任务停止预览：部署前核实8091监听的唯一/tmp/b063_serve.py PID3794194，部署并核验页面成功后仅向该匹配且同账号预览发TERM；独立ps确认相关b063/b062-preview活动进程0，ss确认8091不再监听，未把SSH结束当退出。证据生产`/home/claudeuser/inves-cog-data/ops/b066-verification-20261027.json`，无私有页面内容/持仓/密钥输出。

下一步需求方线上走查；A025继续待验收合并与部署指令，A024盘前首尾和A023第二日收盘按自然窗口继续，不重复执行已完成安装或模型调用。

## A-025追加IEX 已收到／进行中

最新main `aac8f6cd8de2994bc47e8cc2153eef60605e72ac`明确追加用户IEX要求，沿用PR90现有提交，不重启任务；原第二版无模型变更继续有效。变更：同股票/ETF范围、ET04–20每分钟额外一次批量GET `/v2/stocks/trades/latest?feed=iex`，写原表独立source=Alpaca:iex/as_of原成交/delay_minutes=0，prev_close复用SIP同日调整全市场前收缓存；主键重复跳过，不新增schema/角色、不改web/trading。IEX与SIP分开来源健康，单源非429失败不阻断另一源；429仍停止Alpaca新快照路径并报告，不擅降频。核实官方免费权限与IEX系统时段后明确哪些时段无新成交，不用当前时间伪装陈旧成交；先失败测试再实现，准确新head CI重跑。新增接口沿既有Alpaca凭据，不购套餐，不调用模型。

## A-025 IEX追加进行中：真实免费接口核验/离线实现完成，新head CI待完成

沿原PR90，完整新head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6`；已合入main继承B066及最新任务，无自行修改web/docs。IEX先失败提交`fca7727`（真实响应夹具、10失败3通过），再实现`ebd1df2`；准确新PR CI https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527 当前pending，不沿用旧20937bd成功结果。

免费接口实际证据：2026-10-27 10:24:46.890580 UTC，本项目原Alpaca免费凭据一次GET批量SPY/NVDA/IWM、feed=iex，HTTP200；X-RateLimit-Limit200/Remaining199。真实公开响应写只读证据及测试fixture，不写业务数据，不调模型。此时ET06:24，SPY最近为昨日15:59:59，NVDA昨日16:30:59，IWM昨日16:49:51；说明无套餐延迟不是成交刚发生，不伪造今日或当前时点。最初一次工具自动审查超时未执行、随后本地脚本缺失未发请求，修正后才有上述唯一真实请求，未重复请求或绕过审查。

官方核对：Alpaca https://docs.alpaca.markets/us/reference/stocklatesttrades-1 批量latest trades支持feed=iex、免费默认iex；https://docs.alpaca.markets/us/docs/market-data-faq 说明免费IEX仅单交易所，非全市场；IEX https://www.iex.io/resources/trading/trading-hours-holidays 股票盘前ET08–09:30、常规09:30–16、盘后16–17。按任务仍ET04–20每分钟轮询，时段外可能返回旧成交，保留真实as_of/session；latest接口排除不更新价格条件包括odd lots，不宣称全市场最后任意一笔成交。

变更细节：追加独立iex_snapshots无enrich进程，task=iex_intraday、source_health=AlpacaIEX，和SIP相同完整scope/同一个已缓存调整全市场前收；source=Alpaca:iex、delay_minutes=0，健康另记max_trade_age_seconds区分实际陈旧。无schema/角色新增；重复成交PK DO NOTHING，IEX与SIP同时间因source不同可共存；429共用Alpaca停止标记（现含SIP/IEX/wide三路），其他源互不拖停。

离线相关M1/服务配置/A016回归174 passed；额外IEX/Yahoo调度不启动enrich两参数通过，ruff/diff通过。独立临时PG实测IEX/SIP同时间独立记录、重复成交不改首次fetched_at、前收同口径通过并回滚，临时PG已停。证据测试tests/m1/test_a025_iex.py与fixtures/a025/，生产公开探测证据inves-cog-data/ops/a025-iex-public-probe-20261027.json。下一步收口准确CI并交需求方验收，不提前部署或把请求发出当业务采集成功；所有模型改动仍暂缓。

## A-025（含IEX追加）已完成：准确新head正式CI通过，待验收合并部署

原PR90 https://github.com/XuQingsong/inves-cog/pull/90 ，完整最终head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6`。[准确PR phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527) success；同SHA分支CI https://github.com/XuQingsong/inves-cog/actions/runs/40490315343/job/122142310498 success。干净容器946 passed/33 deselected，另2项CI断言通过，含真实临时PG的IEX/SIP主键、重复成交不覆盖、同口径前收测试；不是旧head的通过结果。最终再次fetch确认main仍`aac8f6cd8de2994bc47e8cc2153eef60605e72ac`，无新修订或暂停。

追加验收逐项：免费账户权限/限频及IEX盘前盘后时段的真实和官方证据见上一条及PR；ET04–20每分钟与SIP同scope，独立无enrich进程与AlpacaIEX健康；test_iex_polls_same_minute_windows_as_sip_even_when_exchange_closed、test_pipeline_registers_iex_with_independent_source_health及服务配置集合测试通过。source=Alpaca:iex/delay_minutes=0/as_of原成交/session原时段/prev_close全市场同缓存，test_iex_last_print_may_be_previous_day_without_fabricating_freshness、test_iex_batch_scope_uses_same_sip_previous_cache_and_never_updates_duplicate通过。test_iex_real_pg_separate_source_and_duplicate_trade_time核验同成交时间重采不改首次fetched_at、IEX/SIP同时间独立两行；不把零feed延迟当刚发生，缺/陈旧/未来/错误交易所样本均有测试。原第二版调度、保留清理、退避、健康汇总和角色权限回归仍通过。

所有代码已推送；未部署、未运行新增生产轮询或迁移。唯一真实请求只是明确要求的免费接口核实，未写业务表，无模型调用/历史补算。下一步由需求方验收合并并下发安装；A届时先核实main包含已验收merge再部署，不自动合并。首交易日IEX三类标的时间差/与SIP价差以及原分钟行情全天证据仍待实际安装和自然窗口，未提前认作完成。自动化持续开启。

## A-014 补充四十二 已收到／进行中：安装A025

收到main `2582cbd61f18a8372b8a64c10c934846e8999a6c`部署任务；PR90已验收merge `0f3912fa80652dc6b1542c701df2ba4c4ac4037e`在main，准确head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527) success。先核对远端工作区、receipt/表状态、监督/实际进程及运行中作业，避免重复DDL与轮询。按授权只快进该merge、安装0008，基于当前完整服务配置仅移除主scheduler两行情任务并新增四个独立行情程序；先停止旧scheduler及其唯一enrich子进程并确认退出，再启动新scheduler及四程序，保持enrich只有1个、不手动调模型。模型参数hash、其他原有任务/业务进程保持；迁移仅已批准新表/CHECK、使用既有迁移账号，不以管理员跑业务。10分钟内读真实各source最新时间/进程/Alpaca停止标记，首日长期观察不冒充已完成。

## A-014 补充四十二 安装与10分钟内核验已完成（首交易日观察进行中）

生产已安装验收merge `0f3912fa80652dc6b1542c701df2ba4c4ac4037e`，准确PR head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527) success。迁移0008仅执行一次，SHA256 `3deb0089b08c0326f71b91cd67f1c6f76db0a6e79cbd327f970cfd161473b7f7`；新表/CHECK和业务role_ingest写、role_web只读已实际核验，业务账号无管理员成员身份。工作区干净、模型两个配置hash前后相同。

安装结束11:42:41 UTC，11:48:02 UTC（5分21秒内）独立读取真实证据：stock_snapshots PID3866080、iex_snapshots3866078、macro_snapshots3866079、wide_snapshots3866081均RUNNING且各仅1个；主scheduler3866077保留原17项其他任务，仅移除intraday_snapshots/yahoo_intraday；旧scheduler3178027及enrich3178249均已退出，新enrich仅3866087一个。其他所有业务PID保持（含pages、news_translate、M9），未手工调用模型、未改变模型参数/预算。部署前无运行中job，未中断业务提交前缀。初次状态推送TLS中断后已成功补推；初次preflight审批超时未执行，按工具允许一次重试后通过，没有绕过审批或在未知状态重跑部署。

各source最新时间（均UTC，max分别汇总，不伪称同一条）：Alpaca:delayed_sip最新as_of11:32:59.758659、最新fetched_at11:48:00.903325；Alpaca:iex最新as_of昨日10-26 20:58:58.926954、首次/最新fetched11:42:42.762624（08ET前只有旧成交，重复不更新首次时间）；Yahoo最新as_of11:47:53、最新fetched11:48:00.494484。snapshot-alpaca-halted不存在。安装后实际新增行SIP292、IEX77、Yahoo70；不能把每批processed_count当新增行。11:43–11:48真实job均逐分钟完成，SIP每批76有效成交/IEX77/Yahoo10；IEX ok，SIP degraded因1代码无当日成交，Yahoo degraded因3个收益率代码尚无当日报价，不把部分缺失当全源成功。wide进程已运行，但当前ET07:48未到09:30，尚无该任务运行/行，不冒称已验证盘中宽池。

公开样本：SPY SIP767.47、原成交11:32:44.225339/采集11:48:00.903325（约15分16.7秒），IEX765.225仍昨日19:59:59.950174；NVDA SIP217.23、IEX216.18仍昨日20:30:59；IWM SIP277.91、IEX276.78仍昨日20:49:51，两源前收分别对齐765.37/216/276.99。TNX最近仍昨日18:59:52/4.986%，不凑“约15分钟”达标证据；昨日旧值由B066显示并保留原时间。外部/和/stocks均200。

真实receipt：生产inves-cog-data/ops/a025-deploy-20261027.json、a025-initial-verification-20261027.json，配置备份a025-supervisord-before.conf。后续只读跟进自然08ET后IEX新成交、盘前/盘中各3时点SPY/TNX和SPY/NVDA/小盘IEX年龄及价差、全天行数/429、09:30宽池首批、夜间宏观；不为证据手动补采或调用模型。安装完成与首交易日验收明确分开，自动化持续开启。

## OPS-A025 首交易日盘前样本1（ET08:02，进行中）

2026-10-27 12:02:10 UTC只读自然已入库结果，无数据源请求/模型调用。证据生产ops/a025-natural-20261027T120210Z.json。SPY延迟SIP原11:46:11.753336、采集12:02:00.857239，差949.10秒（15分49.1秒）；NVDA923.74秒、SMCI910.88秒，均保留真实原成交。TNX仍昨日18:59:52，观察时已61338秒旧，不能当“15分钟以内”通过。IEX当日仅1个新成交时间12:00:01.668858（表总计，不是SPY/NVDA/SMCI）；这三只仍昨日成交，实际观察年龄约57730/55871/57731秒，delay_minutes=0仅feed延迟，不是新鲜度。三者IEX减SIP价差分别-1.8212/-1.17/-0.65，成交时点相差约16小时，不能作同时间价格偏差结论。

追加样本范围核实：从本来59只公开授权池与最新wide_universe交集按已存mktcap选择最小可得为SMCI，23506221439.52；仅称“池内相对小市值样本”，不将其伪称严格小盘股或IWM ETF当小盘个股。没有为样本扩展采集范围。后续验收报告保留这个范围限制，其他观察照常继续。

三个分钟任务均已自然推进12:02并完成、近10分钟failed job数0（仍有前述局部缺价degraded）；Alpaca停止标记不存在。后续盘前样本2/3按下一次08:30后及09:00后自然观察，盘中3时点与09:30宽池、全天/夜间尚未到窗口，不每次唤醒重复取样或伪造未来结果。

## OPS-A025 盘前样本2（ET08:31，进行中）

2026-10-27 12:31:37 UTC只读既有自然结果，证据ops/a025-natural-20261027T123137Z.json。SPY SIP767.73：as_of12:15:57.216462、fetched12:31:00.902199，差903.69秒（15分3.69秒）；IEX768.45：as_of12:30:34.618915、fetched12:31:00.692780，差26.07秒，实际观察年龄62.40秒。IEX减SIP=+0.72，但原成交相隔约14分37秒，不作为同时间价差异常。IEX已开始自然取得新日成交，全池当日去重39行，最新原成交12:30:57，不以PID或HTTP200代替该证据。

NVDA SIP时间差914.12秒、SMCI932.48秒；两者IEX仍昨日成交，观察年龄57637.80/59497.50秒，对应IEX减SIP=-1.35/-0.59，保留“旧成交”限制，不强凑新鲜。TNX仍昨日，观察年龄63105.01秒，不算15分钟标准通过。近10分钟三个分钟任务failed=0，均自然推进12:31；Alpaca停止标记不存在，无手工采集/模型/范围修改。下一盘前样本3为09ET后，09:30宽池首批及盘中/全天仍待自然窗口。

## OPS-A025 盘前样本3（ET09:01）；三次盘前观察已记录，非全部指标通过

2026-10-27 13:01:58 UTC只读已入库自然结果，证据ops/a025-natural-20261027T130158Z.json。SPY SIP原12:45:56.049453、采集13:01:00.902067，差904.85秒（15分4.85秒）；TNX当日新值4.99%，原12:45:54、采集13:01:00.430895，差906.43秒（15分6.43秒），本样本两项在15分钟加1分钟内。前两次TNX尚旧，不能把本次新鲜倒推为三次全部通过。

SPY IEX768.17原12:47:57.054072、首次采集12:48:00.675203，首次到达差3.62秒；但本次观察时已841.17秒（14分1秒）无更新，不能只报3.62秒掩盖当前陈旧。IEX减SIP=+0.21，两笔原时间差2分1秒。NVDA/池内相对小市值SMCI的IEX仍昨日成交，观察年龄59459.02/61318.71秒，价差-2.11/-0.7612不具有同时间比较意义；SIP年龄900.69/924.77秒。IEX全池当日去重86行、最新13:00:58；来源部分代码真实有新成交不等于全部代码新鲜。

三个分钟作业已自然推进并完成13:01，近10分钟failed=0，Alpaca停止标记不存在；未手工补采/模型/改角色或范围。盘前3个观察点08:02/08:31/09:01已如实存证，首日完整验收仍有IEX个股陈旧及样本范围限制。接续09:30后宽池首批与A024盘前首尾（窗口结束后）、盘中3时点/全日限频行数及隔夜；不把“采样完成”当全部业务通过。

## A-026 已收到（仅部署，等待实现验收合并）

收到main `6a3638d0d62be4dffff9696b61f7535c9ecb92cd`新任务：本单明确由需求方SWE-2实现，A只负责部署；不自行开发、不分配其他线任务、不提前改生产模型参数或待处理队列。已读取7项要求及验收：仅相关公告news_card、停info_fields/公告entity_tagging、结构化非新闻与无关公告rules-only/保留审计、模型脚本显式allow/max与测试真实网络保护；保留归因/翻译/图谱，不设全局上限。与此前A025暂缓模型的旧要求不同，按本单部署范围接收，仍不把授权解释成未合并前安装。

当前main最新仅派单，A014尚无A026验收merge/安装指令；待准确head CI成功、需求方验收合并及明确部署答复后，核对真实队列/进程和一次性转换审计再执行，不提前调用真实模型验证。部署后按完整美东自然日连续两天分task回报calls/token，并分别列安装当日旧行为，避免把旧调用计作新版本失败或冒称全天零。A025已安装的首日自然运维仍按09:30宽池/盘中/全天与隔夜窗口继续，局部等待不停止其他已授权观察。

## OPS-A025 宽池已自然启动；盘中样本1（ET09:40）

2026-10-27 13:40:08 UTC只读核验，生产head仍`0f3912fa80652dc6b1542c701df2ba4c4ac4037e`，证据ops/a025-natural-20261027T134008Z.json。wide_snapshots真实自然作业09:30/09:35/09:40启动且均结束，耗时24.46/7.30/7.39秒，processed813/822/836；已入库去重1321行/836代码、前收NULL0。应采included池1270，所以仍degraded，不能称完整宽池通过。09:40最新SIP原成交仍09:25（15分钟延迟），尚未读到09:30开盘后的全池成交；先在09:45后核对覆盖是否随延迟开盘报价改善，不手动重跑、降频或伪造缺失。

盘中样本1：SPY SIP767.14，as_of13:25:00.440267/fetched13:40:00.899914，差900.46秒（15分0.46秒）；TNX4.995%，as_of13:24:54/fetched13:40:00.409409，差906.41秒。IEX的SPY/NVDA/SMCI这次都已自然取得新成交，首次采集距成交4.64/3.73/2.20秒，实际读取年龄12.13/11.22/9.70秒；IEX减SIP分别+1.025/+0.20/+0.69，原成交相差约15分钟，不作同时间异常价差判断。IEX全池今日去重926行，最新13:40:00.543183，克服此前样本中NVDA/SMCI一直旧值的自然覆盖限制，但不倒写盘前结果。

四类作业近10分钟failed=0，均自然推进13:40；wide仍degraded为缺成交覆盖、其他状态按实际保留，不拿failed=0当全部合格。Alpaca停止标记不存在。盘前完整尾部统计需等15分钟延迟尾部到齐（09:45后），下一轮与wide覆盖一起收口；盘中样本2/3在12ET和15ET后取现时已入库结果，全天/夜间和A023第二日收盘继续自然窗口。

## OPS-A025 宽池完整覆盖已核验；A024盘前首尾已收口（ET09:54）

2026-10-27 13:54:22 UTC只读自然结果，证据生产ops/a025-wide-preclose-20261027T135422Z.json。09:50宽池任务status=ok/processed1270，耗时7.33秒；表内3734去重行/1270代码、前收NULL0、应采代码未覆盖清单为空。对照09:30/09:35/09:40/09:45批次813/822/836/1222，证明覆盖不足随15分钟延迟的开盘成交到达而改善，09:50已全覆盖；不是手工补采或修改过滤口径。source_health仍degraded是15分钟窗口包含3次早期不全，note已显示requested1270/missing0；不以旧汇总状态否定最新job，也不将最新全覆盖倒推早期都全。

盘前首尾按原as_of在ET04–09:30且当日过滤，已等到SIP15分钟尾部到齐：SIP5430去重行/76代码，原时间首08:01:06.592904 UTC（ET04:01:06）、尾13:29:59.360233（ET09:29:59），首次采集08:30:48、尾部13:45:00；Yahoo1460行/13代码，原首08:00:36、尾13:29:59，采集首08:00:42、尾13:45:00；IEX146行/23代码，原首12:00:01.668858（ET08:00:01）、尾13:29:05.095237，首次12:01、尾13:30。04–07:42采用已部署A024旧频率，07:42后才是A025分钟制，不能称整个盘前都按新频率。

最后公开样本：SPY SIP768.0941原13:39:00/采集13:54:00，IEX766.02原13:54:00.282/采集13:54:00.662；TNX4.999%原13:38:54/采集13:54:00；WTI100.95原13:43:57、黄金4043.9原13:43:59，均原时点保留。Alpaca停止标记不存在。

A024公开页面交叉对照本轮有界结果：web工具四个Google Finance URL均不可访问；一次无登录HTTP回退四页均200，取得公开时点SPY13:52:55 UTC、TNX13:32:04、WTI13:42:22、黄金13:45:06，但现有解析未取得价格字段。没有把HTTP200或已有库内价格伪装成独立公开价对照通过；此项证据尚缺数值，保留为验证限制，不重复请求刷批次。读取输出本地/private/tmp/a024-public-compare-20261027.json，仅公开数值时间请求，无账号内容。主业务采集与完整宽池已真实通过，不因该单项对照限制停止其他已授权部署/观察；后续如需求方验收需精确同时间对照，再以明确可获得相同合约/时点的公开证据处理，不伪造相等。

## A-014 补充四十三 已收到／进行中：部署B067

收到main `81730db326b144359b0a6a763e917ab88bd7bb5a`明确指令，PR92已验收merge `c16d8549e6d48d23795b7d74ea8ef340a2ee5c63`在main。先核对准确head CI及生产工作区/进程，再快进该merge，只重启pages；核验/与SPY/QQQ行情单元格可见“IEX实时”或“延迟15分”、title实际来源及对应原始时间，识别并停止8091指定预览、确认真实退出。无迁移、模型参数/调用或四路行情进程重启；A026仍等需求方实现验收，不提前安装。已有A025自然盘中/全日观察保持。

## A-014 补充四十三 已完成：B067来源标签已上线并核验

生产head `c16d8549e6d48d23795b7d74ea8ef340a2ee5c63`（PR92验收merge），准确开发head `1710d06e989ee514ab97cb073121fc7c5d1e3434` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40522083470/job/122251572819) success。初次GraphQL读取unexpected EOF后，以该SHA的REST检查记录成功核实；未绕过检查。快进已验收merge，只重启pages，其他所有当时业务PID保持（含四路行情、主scheduler/enrich、翻译、M9），服务配置字节保持、工作区干净，无迁移/模型调用/参数变更。

14:51:48 UTC外部真实核验：首页/状态200（/stocks、/account、/trust亦200）；顶部“数据更新至 北京22:51（美东10:51）”。SPY实际行情单元为“标普767.85 +0.32% IEX 实时10:50:51”；QQQ为“纳指717.82 +0.79% IEX 实时10:50:49”。二者title均真实显示Alpaca IEX、原成交北京10-27 22:50、0分钟feed延迟，并分别显示另一源“Alpaca延迟SIP767.55于10:36”“Alpaca延迟SIP717.45于10:36”。只读DB的SPY原成交14:50:51.944829、首次采集14:51:00.680432，价格767.85，与可见标签同源同原时点；没有把采集时间当成交时间。首页最近24小时新闻非空，DOM新闻82行，刷新标记保持。

部署前识别8091唯一/tmp/b063_serve.py PID3946621；页面核验通过后仅对同账号该精确预览进程TERM，独立ps相关活动预览0、ss无8091监听，未把SSH结束当退出。证据生产inves-cog-data/ops/b067-verification-20261027.json。下一步需求方走查；A026仍待实现验收/安装指令，A025下一盘中样本12ET后、后续15ET、全天及隔夜按原窗口继续，不重复迁移或采集。

## A-014 补充四十四 已收到／进行中：安装A026与B067补充

收到main `1687841f1bd7ec2b41e45736a2d899b430654787`明确部署指令。目标 `dff926798ac76932b7ea110461982af6eb5f3b86` 包含A026 PR91 merge `e2340595f3f0e1c0b229e795752c687a9b3a13d5` 与B067补充PR93。准确head分别`49dc405ba20574a91d3869896f4d8d45b8f57508` [CI](https://github.com/XuQingsong/inves-cog/actions/runs/40528031606/job/122272829343)、`0f7fd294143eb9cff4019f7d822968bb177387c0` [CI](https://github.com/XuQingsong/inves-cog/actions/runs/40525380949/job/122263413965) 均success，且已合并main。将在ET10-27 23:30前安装；先读现有工作区/receipt/实际进程、运行作业、pending按kind及日志位置，停旧主scheduler连同唯一enrich、四个快照，确认退出后快进并原配置重启这些进程及pages，其余进程保持，无迁移、不改参数、不手动调模型或重复跑转换。

之后只读自然enrich首轮rules_only_structured及待处理按kind结果，相关公告匹配仅核对计数，不输出私有内容/持仓。若本来无积压且enrich未自然触发，明确说未产生首轮日志而非伪造条数。部署当日旧调用单列；ET10-28 01:00后读取从10-28午夜起分task用量，之后连续一天同口径，另保留完整自然日核验，不将代码安装说成费用收敛已经由未来日验证。A025盘中12ET/15ET及全天自然观察保持。

## A026部署进行中：自然首轮512；按本单要求补齐旧延后积压（纯规则、无模型）

15:41:23 UTC实际首轮日志rules_only_structured=512/processed513/statusok；已有2轮累计1024（macro1018、sec_8k6）。剩余macro742、sec_8k120；按现有发行人映射/标的与持仓仅1条相关、119条未匹配。重启后模型调用0、参数保持；行情四路自然正常。旧队列retry_at=10-28 04:00 UTC（ET午夜）、reason=daily_budget；has_pending_info经pending_info过滤future retry而跳过它们，只有新条目碰巧唤醒时才推进一批，不把偶发推进当积压已清。

按A026要求4“现有待处理的非相关公告、空头、宏观条目转为rules-only，审计保留”，本轮运维补齐明确授权的余量：复用已验收Repository.finish_pending_rules_only纯数据库方法（不运行triage/process/enrich、不建立模型客户端），现有业务role_ingest执行；用库内issuer_profiles/sec_filings CIK映射及当前标的/持仓确定保留公告，已有相关或holding标记保守跳过。先检查无进行中info_enrichment、当前head/唯一receipt，短事务锁定队列防止新相关公告并发插入被误转，受影响上限5000/30秒，保存0600原始提取审计副本并记录转换前后按kind数量；仅改变已批准目标的status/news_triage，保留原文、原发布时间/首次可见时间及其他审计字段，不动新闻、不补采、不调模型、不改参数/角色/代码。若相关性映射缺失或并发安全检查失败则不写，不越过范围。这里是首次补齐剩余未转换行，不重复转换已完成1024条；实际条数以执行时状态为准，首轮日志仍如实为自然512，不把人工纯规则数量冒称日志首轮。
