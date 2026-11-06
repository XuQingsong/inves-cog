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

## A-014 补充四十四 安装与积压核验已完成（两自然日费用观察进行中）

生产已于2026-10-27 15:27:52 UTC（ET11:27:52）安装目标 `dff926798ac76932b7ea110461982af6eb5f3b86`，早于ET10-27 23:30截止。包含PR91准确head `49dc405ba20574a91d3869896f4d8d45b8f57508` [CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40528031606/job/122272829343)及PR93准确head `0f7fd294143eb9cff4019f7d822968bb177387c0` [CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40525380949/job/122263413965)，均先验收合并后才安装。无迁移，m1/llm_tasks两个参数文件hash保持，Supervisor配置字节保持；业务非管理员账号核验通过。

实际进程：主scheduler3981483、唯一enrich3981485、stock_snapshots3981506、iex_snapshots3981533、macro_snapshots3981543、wide_snapshots3981583、pages3981611均RUNNING各1；对应旧PID均确认退出，其他业务（包括进行中的consensus）PID保持，没有将本地SSH结束当远端退出。15:50只读确认四路行情都已在新启动后自然完成作业，failed0，Alpaca停止标记无。外部/及/stocks均200。B067补充首页11条行内行情显示IEX标签、全部title明确Alpaca IEX，/stocks200（该页无此行内组件，不冒称11条属于stocks）；证据ops/b067-followup-verification-20261027.json。

自然enrich日志真实首轮：rules_only_structured=512，processed_count513，statusok，deferred/tagging_failed/embedding_failed均0；后续自然两轮累计rules_only_structured1024。旧每日预算延后元数据让纯规则积压在空闲门控中仍等待午夜，按A026要求4复用已验收纯规则方法补齐861（macro742、无关sec_8k119），不是手工模型/enrich/triage调用。业务账号短事务保护，相关公告保留；原文、原发布时间、首次可见时间等字段hash前后相同，所有旧提取源审计完整保存于0600文件`ops/a026-rules-only-backlog-audit-20261027.private.json`，SHA256 `946f4f3373c1313d62a50e342bc6b698671a0517438b9f11cfa111eb0ae69a73`；操作receipt `ops/a026-rules-only-backlog-completion-20261027.json` phasecommitted，不再重跑。

最终独立核验15:52:33 UTC：pending仅sec_8k1，macro=0、short_interest=0、form4=0；唯一保留项属于原清理审计的相关公告，现有CIK/ticker映射已匹配标的/持仓。15:50曾有另3条新pending，15:52已由自然循环自行处理，没有重复人工清理或把正常在途条目误判为长期阻塞。现有相关公告保持其原retry_at=10-28 04:00 UTC；纯规则清理没有提前触发它的模型调用。新版本安装至15:50按task用量查询为空，故目前info_fields_extraction/entity_tagging/news_card均0，但只证明这段自然运行，不冒称未来午夜批次或完整自然日已通过。

部署及核验receipt：ops/a026-deploy-20261027.json、a026-initial-verification-20261027.json、a026-pending-gate-diagnosis-20261027.json；均在生产本项目data目录，不输出私有正文/持仓/凭据。后续按任务：10-28 05:00 UTC（ET01）后报10-28午夜起calls/token及news_card关联范围；10-29同口径再报并单列完整10-28，10-30美东10-29结束后收口第二个完整自然日。旧安装前调用与新版本时段分开，不手工调模型验证。A025盘中12ET/15ET、全日及隔夜观察继续，原自动化保持ACTIVE。

## OPS-A025 进行中：盘中样本2（ET12:28）已完成

2026-10-27 16:28:24.920968 UTC只读自然入库结果；生产head仍`dff926798ac76932b7ea110461982af6eb5f3b86`，本轮fetch main仍`1687841f1bd7ec2b41e45736a2d899b430654787`，无新开发任务/部署指令。证据生产`ops/a025-natural-20261027T162824Z.json`。A025开发准确head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6`、[PR90](https://github.com/XuQingsong/inves-cog/pull/90)、[该head CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527)沿用已验收证据，本轮不重复测试或安装。

SPY SIP770.18，原16:12:57.925331、首次采集16:28:00.910291，差902.98秒（15分2.98秒）；TNX4.993%，原16:12:54、采集16:28:00.434107，差906.43秒（15分6.43秒），均在15分钟加1分钟内。观察年龄分别927.00/930.92秒，明确区分首次采集延迟与读取时年龄。

IEX SPY/NVDA/SMCI首次采集与成交差0.482/0.533/9.872秒；本次读取年龄24.699/24.751/34.090秒。原成交依次16:28:00.221580、16:28:00.170212、16:27:50.831094，首次采集均16:28:00.703260。IEX减SIP价差分别+0.08/+0.21/+0.015；两源原成交相隔约15分钟，不能视为同一时点价差错误。SMCI仍是池内相对小市值样本（已知市值235.06亿美元），不冒称严格小盘股，也未扩采样范围。IEX当日去重12662行、最新原成交16:28:00.221580；这不是全天最终行数。

三个分钟任务都已自然完成16:28批次，近10分钟failed=0，Alpaca停止标记不存在。仅查询业务只读数据并保存本项目证据，未补采/手工模型/改代码参数角色。已自行决定：无新增。下一步第三盘中样本ET15:00后（19:00 UTC）；A023次日收盘、A025全天与隔夜、A026午夜后及连续两自然日用量分别到窗再核验，不提前宣称完成。无需要用户处理的新增阻塞。

## A-014 补充四十五 已收到／进行中：部署B068

main `1e30f9e40db4037ad2ad4858faaa43cea96f0428`下发明确运维安装。PR94已合并`e5329528699f2c96efcb41900df5e769bfd803af`；准确head `f5dbd97ced5eeec29c7ecce4e627ef23228c5a3e` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40551779386/job/122357157544) SUCCESS已核对。变更：按批准迁移0009仅新增intraday_snapshots.day_volume bigint，先迁移再重启四个快照及pages，其余进程保持；识别并停止指定8091预览。先核对生产receipt/列是否已存在、真实运行作业和进程，再安装已验收main，保存迁移证据，核对自然SIP非空比例及四页状态/暂缺数。无参数或模型调用变更，不重复已完成0007/0008迁移。

## A-014 补充四十五 已完成：B068已上线，成交量自然写入已验证

2026-10-27 17:53:40 UTC生产已快进验收merge `e5329528699f2c96efcb41900df5e769bfd803af`（[PR94](https://github.com/XuQingsong/inves-cog/pull/94)，准确head `f5dbd97ced5eeec29c7ecce4e627ef23228c5a3e` 的[phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/40551779386/job/122357157544)）。先确认day_volume不存在和受影响作业空闲，停止四个旧快照进程并确认真实退出，快进已合并代码；迁移0009单次提交成功、新列bigint，之后才启动四路快照并重启pages。迁移SHA256 `3af6af88d490df0caf23040aa782232ba5fd83f4cf625f6ba91bff2486e05b23`；仅迁移使用批准的本项目DDL账号，业务ingest和web角色权限独立核验、均非管理员。没有重跑0007/0008。

新PID stock_snapshots4057908、iex_snapshots4057916、macro_snapshots4057966、wide_snapshots4058013、pages4058025，均RUNNING；主scheduler3981483、翻译3258700、M93599229等其余Supervisor业务PID保持。配置字节和两份模型参数hash保持，生产工作区干净。指定/tmp/b063_serve.py活动预览0，8091无监听，未把SSH退出当远端进程退出。证据本项目`ops/b068-deploy-20261027.json`（phaseinstalled）。

独立核验于17:54:02 UTC开始（重启结束后22秒）：重启后新写入Alpaca:delayed_sip共77行/77代码，day_volume非空77/77=100%；最新自然批次fetched_at17:54:00.929350，原成交范围17:38:32.626026–17:39:00.635157。历史旧行未回填，100%只指上线后新采集行。三个分钟作业已自然完成17:54、failed0；wide进程已运行，但该核验点尚未到17:55五分钟窗口，不把进程存活当下一批宽池完成。Alpaca停止标记不存在。没有手工补采或调用模型。

四页真实HTTP响应均200；按返回HTML中“暂缺”文本出现次数：`/`9、`/stocks`77、`/s/NVDA`6、`/account`1。仅报告计数，不输出私有页面/持仓；不把200或成交量100%冒称所有缺失字段已清零。证据`ops/b068-verification-20261027T175402Z.json`。已自行决定：无新增。下一步需求方线上走查；A025第三盘中样本19:00 UTC后、全天/隔夜及A026午夜费用观察继续原窗口，部署运维已完成，无需用户额外操作。

## OPS-A025 进行中：第三盘中样本已取；Yahoo真实429限频导致宏观陈旧

2026-10-27 19:00:52 UTC（ET15:00:52）第三样本，生产head `e5329528699f2c96efcb41900df5e769bfd803af`，证据`ops/a025-natural-20261027T190052Z.json`。A025准确head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6`、[PR90](https://github.com/XuQingsong/inves-cog/pull/90)、[CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527)沿用；B068安装已完成，不重复迁移。

SPY SIP769.24，原18:45:00.264078/采集19:00:00.867174，差900.60秒。IEX SPY/NVDA/池内相对小市值SMCI首次采集距原成交27.115/2.434/7.616秒，读取年龄78.480/53.800/58.981秒；IEX减SIP分别+0.17/+0.10/+0.0301，原成交相隔约15分钟，非同瞬间价差。IEX当日去重22566行（非全天最终），Alpaca停止标记无。stock/iex/wide已自然完成19:00，近10分钟failed0；宽池19:00实际结束19:00:07.120625，也补齐B068重启后宽池真实作业已完成的证据。

TNX仍4.995%，原17:54:54、首次采集18:10:00.395390，首次延迟906.40秒但读取年龄3958.04秒（65分58秒）。不能只报首次延迟称合格。一次有界只读诊断19:02:05（`ops/a025-tnx-diagnosis-20261027.json`）确认：YahooIntraday最近18:59自然尝试status=degraded/processed0，source_health明确13代码全部SourceError:status=429，backoff_seconds900、retry_at19:14:00.016160；宏观所有代码最新采集都停在18:10。failure_count1是该健康汇总窗口，consecutive_failures3是当前存储计数，不冒称整个故障仅1次。failed0不等于业务成功；本次宏观时效未通过，首交易日“Yahoo是否触发限频”答案为是。

影响：美债/期货/汇率/比特币等13个宏观快照在页面继续显示旧原时点；股票SIP/IEX/宽池仍在推进。已有自动退避15分钟正按批准规则运行，不擅改频率、来源、IP、权限或绕过限频；无手工HTTP/模型请求。已在本对话直接通知用户真实影响与证据，目前无需用户决定。下一步19:14后下一唤醒只读核对自然重试是否恢复；未恢复则如实保留源端运维阻塞及后续自动退避，不重置诊断预算或刷请求。盘前3/盘中3采样阶段完成，但不能称全项通过；全日、隔夜与A026午夜费用观察继续。已自行决定：无新增。

## OPS-A025 进行中：自然重试仍429，保留源端运维阻塞

19:20:03 UTC只读核对已约定19:14自然重试：实际job19:14:00.033795–00.372090，degraded/processed0；13个Yahoo宏观代码仍全部429，consecutive_failures4，自动900秒退避，下次19:29:00.032452。所有宏观最新采集仍18:10，未恢复。证据`ops/a025-tnx-retry-20261027T1919.json`（文件名按唤醒窗口，内部真实观测时间19:20:03）；没有新增HTTP请求/手工补采/重启/参数变更。既定自动退避已执行，不能以本次作业结束称业务恢复。当前不需要用户操作，维持其他已授权工作；不逐次重试刷诊断，下一只读恢复检查20:00 UTC后或新答复/新任务到达时，仍按源端限制如实报告。此前第三样本及CI/head证据不变。

## OPS-A025 进行中：20:00窗口仍源端限频

20:01:32 UTC只读证据`ops/a025-tnx-retry-20261027T2001.json`：自然20:01 job于00.328193结束，degraded/processed0，13个代码仍429，存储consecutive_failures7，既定退避900秒、retry_at20:16:00.017103。最新真实采集仍18:10，未恢复；没有源端额外请求、重启或参数变更。原因与影响未变化，无需用户操作；不把休市后旧值或作业完成说成恢复。此轮有界核实已足以支持源端限频结论，不继续逐批诊断；下次合并到10-28 00:45 UTC后的A023收盘/宏观隔夜自然核验，若出现新任务或答复则及时处理。A025全天行数应等ET20:00采集窗口结束后统计；A02605:00 UTC后用量窗口不变。

## OPS-A023/A025 进行中：ET10-27收盘与全天快照核验；Yahoo已自然恢复

10-28 00:50:48 UTC真实只读联合核验，生产head `e5329528699f2c96efcb41900df5e769bfd803af`，main仍`1e30f9e40db4037ad2ad4858faaa43cea96f0428`无新任务。证据`ops/a023-a025-close-20261028T005048Z.json`及`ops/a025-close-supplement-20261028.json`（00:51:27）。本轮未改代码、参数、调度、角色或来源，没有手工补采、模型请求、迁移或服务重启；沿用已验收准确head/CI，A025 PR90 head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6` [CI](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527)不重复运行。

Yahoo限频已自然恢复：20:32仍degraded/processed0，20:48首次所核对恢复job ok/13，20:49/20:50继续ok/13。隔夜00:00、00:15、00:30、00:45四次自然job均ok/13；最新健康failure0/backoff0，原数据最新00:44:54。已在本对话通知恢复，不把恢复倒推为此前限频未发生。13代码接口成功不等于全部代码都有新成交：实际隔夜新原时点9代码（八个期货/美元指数及BTC），各3条，共27条；首次原时点00:04:19–00:14:52，最新00:34:23–00:44:54，最新采集00:45，证明ET20点后15分钟采集真实推进；美债/VIX闭市后保留原时间，不伪造成隔夜新报价。隔夜完整ET20–04还未结束，08:00 UTC后才收口。

A025全天统计按10-27 08:00至10-28 00:00 UTC（ET04–20）的首次fetched_at计去重入库：SIP42229（盘前5430/盘中30008/盘后6791）、IEX27023（146/26798/79）、Yahoo6035（1460/3502/1073）；各来源范围77/77/13代码。IEX当日首次采集含77条前一交易日原成交，按原as_of属于ET10-27且采集窗口内的真实当日成交只有26946，明确区分，不冒称27023全是今日新成交。宽池94826去重行/1270代码，最终原成交19:40:06.624761、最后采集19:55:06.994176。wide自然job早期4次degraded，09:50ET起74次ok，不能把后续完整覆盖倒推开盘即全。Alpaca持久停止标记不存在，未见触发快照429停止；Yahoo确实发生429，不称全源未限频。盘前与盘中各3时点证据已齐，但早盘TNX旧值、部分IEX旧成交、第三盘中宏观限频、严格小盘样本与独立公开价格对照限制保留，故不称首交易日全部验收通过。7/30天真实保留期仍需自然时间，未伪称已验证。

A023第二交易日收盘：bars_full自然00:20:43–00:29:09 ok/227109；vix_daily00:45:26–27 ok/75。ET10-27 VIX Yahoo17.5200004578（约17.52），CBOE最新仅10-26的18.39，不能将CBOE成功取回当当日新鲜；VIX3M当日CBOE19.57，Yahoo19.5699996948。日历财报表2739条，06ET自然job新增/处理2665、来源Nasdaq；宏观表128条，06ET自然job degraded/107且source_health记录SourceError statusNone，存在部分失败，不能称整批完整刷新。未来财报窗口覆盖持仓5/13、标的池29/59，仅聚合计数不输出持仓；不在未来10交易日内有财报不等于缺失。没有因此擅自启动新付费/备用调用或重复日历补跑，保留源端限制，按已授权下一自然周期观察。

ET10-27截至本次20:50ET新闻新入库3147条，均extraction_status=ok；关联新闻info_id或news_triage用途的模型调用0。AlpacaNews健康ok，最新原新闻00:11:05、最近成功采集00:41:56。美东自然日尚未结束（04:00 UTC），3147不是完整24小时最终数；将在05:00 UTC后的A026用量核验一并补齐A023完整第二日新闻与调用统计。A026连续两自然日任务仍未到完成窗口，不能因本轮新闻调用0称未来费用已经验证。已自行决定：无新增；目前无需用户操作，源端限制如实保留。

## OPS-A026 进行中：首个午夜窗口真实用量已核验；向量失败单列

2026-10-28 05:01:11 UTC（ET01:01）只读核验，生产head `e5329528699f2c96efcb41900df5e769bfd803af`；A026已于前日15:27:52.900699安装，PR91准确head `49dc405ba20574a91d3869896f4d8d45b8f57508` 的[CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40528031606/job/122272829343)沿用已验收证据。main仍`1e30f9e40db4037ad2ad4858faaa43cea96f0428`，无新任务。证据`ops/a026-midnight-usage-20261028T050111Z.json`，本轮不补采、不手工模型、不重跑清理或迁移。

ET10-28 00:00至01:01：news_card19次，输入32295/输出5275=37570 token，failed0/usage_missing0；summary_oneliner1次，输入86/输出24=110 token，failed0/usage_missing0。info_fields_extraction0次/0token，entity_tagging0次/0token；其余task在该时段0。19次news_card均有info_ids、关联19条已有CIK/ticker映射的池内/持仓公告，非相关/未匹配0、无关联ID调用0；只输出计数，不输出私有发行人或持仓。当前所有kind pending0，不能把曾保留相关1条一直写成未处理。

午夜自然enrich前三轮04:00:16–58 statusdegraded，processed32/32/4；计数tagging_failed0、deferred0，但embedding_failed2/15/2，合计19。后续04:01及每10分钟新结构化条目自然rules_only_structured1/statusok。已对19次公告关联结果独立核验：Form4 15、sec_8k4，extraction_status均ok，embedding错误均SourceError；安全分类未暴露429/401/403/404/402、timeout/quota/balance/budget指标，cause为空，现有存储不足以确认底层原因。news_card生成成功与向量生成失败是两件事，pending0不能冒称向量成功。证据`ops/a026-midnight-rounds-20261028.json`、`a026-midnight-embedding-summary-20261028.json`、`a026-midnight-embedding-categories-20261028.json`。已在对话直接说明影响：这19条相关公告的向量检索输入缺失，公告分析结果已保存；底层原因未知。未手工重试模型/embedding或擅改费用、来源、权限。请需求方评估是否下发限定的向量链路诊断/修复任务；A只按既有部署与自然用量观察继续，不以未知错误编造充值结论。

ET10-27完整自然日分task（安装前后分列）：安装前info_fields_extraction236次/输入39744输出9931；news_card294次/输入394089输出45923，7次failed且usage_missing7，已知token和不代表未知费用为0；news_translate6次/输入6563输出4142。安装后至ET午夜仅anomaly_candidates1次/14892+2220、claim_extraction1次/2076+3076、move_card1次/34693+1317，均failed0/usage_missing0；这证明保留归因自然运行，不能把安装前236次info_fields算作新版本违规。ET10-27全天entity_tagging0；完整原始分段在receipt，不将半日安装说成完整两天用量验收。

A023第二个完整美东自然日新闻补齐：ET10-27 first_seen新入库3194条，全部extraction_statusok；关联news:条目或news_triage用途的模型调用0。前一交易日2935条/新闻模型0的已核验证据沿用；两日观察要求的数据已回报，CBOE当日更新滞后、宏观日历部分失败等已知限制仍保留供需求方验收，不将“观察结束”冒称所有源完整。A026当前仅第一天首小时通过用量范围核验，第二天及两个完整自然日尚待：10-29 05:00 UTC后同口径并补齐ET10-28全日，10-30 04:00 UTC后补齐ET10-29。A025完整隔夜08:00 UTC后核验。已自行决定：无新增。

## A-014 补充四十六 已收到／进行中：部署B068页面补充

收到main `bcc822f51360e17bb598dee01af8194c9327d7ee`明确安装指令，PR95验收merge `4b47cac062719c406341ddf1b752b00ac7303cee`已在main；准确head `6c59523450e7d85c89b8545f8fe0c5f31ef3f9fc` 的[phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40638298979/job/122650299306) SUCCESS已核对。按批准范围快进并只重启pages，核验三个页面状态和暂缺数，其他进程/配置保持，无迁移或手工模型调用；午夜向量故障仍单列，不能将本次页面修复当向量修复。

## A-014 补充四十六 已完成：B068页面补充已上线

2026-10-28 05:48:12 UTC生产快进验收merge `4b47cac062719c406341ddf1b752b00ac7303cee`（[PR95](https://github.com/XuQingsong/inves-cog/pull/95)；准确head `6c59523450e7d85c89b8545f8fe0c5f31ef3f9fc` 的[phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/40638298979/job/122650299306)）。只重启pages，旧PID4058025已实际退出，新PID221534 RUNNING；其余Supervisor业务PID全部保持，包括主scheduler3981483、四路行情4057908/4057916/4057966/4058013、翻译3258700、M93599229等。配置字节保持，工作区干净，无迁移/数据补写/模型请求/预算变更。

部署前首轮预检发现额外ops/answers/A-014.md路径，在修改代码或重启之前停止；只读核对差异后确认它仅为已批准运维答复，随main继承，继续同一安装，未跳过范围检查。没有重复已完成0009迁移。实际核验三页均HTTP200，返回HTML“暂缺”次数：首页`/`1、列表`/stocks`2、个股`/s/NVDA`5。计数为当前数据时点，不把与昨日不同时间的计数差当严格同数据比较，也不称全部缺失清零。证据本项目`ops/b068-followup-deploy-20261028.json` phaseverified。

已自行决定：无新增。下一步需求方线上走查；A026午夜向量19项失败仍单列，未被页面部署修复，不手工调模型重试；08:00 UTC后A025完整隔夜及10-29/30既定用量观察保持。

## OPS-A026 根因更正：向量被现有配置禁用，不是额度耗尽

用户在本对话询问“向量生成故障是什么问题？”，本轮继续有界只读检查实际错误枚举与配置，不触发任何embedding/模型请求。生产读取结果：INVES_COG_EMBEDDING_ENABLED当前不为1（enabled=false），凭据存在且endpoint为HTTPS；19条关联公告错误逐一精确匹配`Embedding paused by operator`（19/19），其余类别0。adapter在enabled=false时请求前直接抛SourceError，所以这19次未向向量服务发请求，不是token耗尽、远端限频或已证实的凭据问题。凭据存在不等于远端有效，本轮未调用验证。证据`ops/a026-embedding-rootcause-20261028.json`，仅存布尔与类别计数，不含key/连接串。

前轮只按错误类型及HTTP/预算指标分类，遗漏具体消息中的主动暂停含义，导致“现有存储不足以确认原因”的结论不准确，此处明确更正。影响仍是19条公告无新向量；公告news_card及正文分析成功保存，新闻入库不依赖该步骤，不能把它说成新闻列表为空原因。现有调用链仍尝试已禁用的向量功能，才在job中记embedding_failed/degraded；这是禁用配置与处理/告警行为不一致。关闭由谁何时设置的依据本轮未核实，不武断归责。

未修改开关、恢复付费服务、切模型、补跑19条或更改权限。后续若要求恢复向量，须先核对原暂停依据和已批准预算/模型范围；若保持禁用，则需需求方安排明确修复任务，让自然处理将“已禁用”正确标为跳过，不能以关闭状态冒称已生成。当前用户只问原因，已直接说明，无需用户为本轮只读核查做操作；A025隔夜及A026自然用量观察继续。

## OPS-A026 向量修复方案：保留费用暂停，修正旧路径；恢复须按已批准异步合同

用户追问“向量问题怎么解决？”。本轮只读进一步确认：历史提交`f0b7e7b1369b4fc262fe62be5d18714abdeb6d4b` handoff/M1/questions.md明确记录用户“先制定月预算、后续再开”，当时停全量并设开关0。不能把UD-A51取消机器资源限额解释为取消模型费用暂停。现有M1 Q-M1-29又明确批准`text-embedding-async-v1`/1536维、唯一来源ingest.info_embeddings、弃用info_items.embedding；现行m8.yaml也要求该模型/维度。triage.embed_item仍走text-embedding-v3/1024并写item.embedding旧路径，故直接开启现有同步开关既违背费用暂停，也不能保证下游读到合规向量。

具体建议供需求方下发限定修复任务（此处不是代需求方派单）：1）在关闭状态将向量步骤显式记为disabled/skipped，不发请求、不计embedding_failed，不将缺向量说成已生成；公告分析与正常入库继续，检索保留已有“向量检索降到规则检索”提示。2）接通已批准异步模型和info_embeddings独立表，按model/dimensions/input_sha256隔离与去重，断点续跑、保留真实created_at/PIT；禁止写弃用旧列，不重跑news_card。3）费用暂停恢复之前先形成可审阅的输入条数、估算用量/月预算与有界真实验证范围；预算与恢复授权确认后仅补缺失向量，核验19条实际合规入表与下游读取、无重复向量/公告分析调用。此轮未获新增预算/恢复决定，未改生产开关/模型/配置或运行任何付费补算。

A026原单明确A仅部署，M1/ingest开发恢复需最新明确任务范围；本方案已向用户说明并在GitHub提供具体修法及验收边界，等待需求方任务不停止A025/A026已授权自然运维。已自行决定：无新增接口/来源/依赖变更；没有把方案写成代码已交付或业务已恢复。

## OPS-A025 完整隔夜自然核验已完成；盘前美债旧值限制单列

2026-10-28 08:22:12 UTC（北京16:22）只读核验ET10-27 20:00至10-28 04:00完整窗口，即UTC00:00–08:00。生产head `4b47cac062719c406341ddf1b752b00ac7303cee`，main仍`bcc822f51360e17bb598dee01af8194c9327d7ee`无新任务。A025已验收PR90准确head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6` [CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527)沿用，不重新安装或测试。

证据`ops/a025-overnight-20261028T082212Z.json`：自然YahooIntraday job32/32均ok且结束，32个整15分钟时槽全部覆盖，无缺槽或非15分钟批次，每批processed13。实际sessionovernight且原as_of也在窗口内的新入库280行/10代码：九个期货/美元指数/BTC代码各31行，VIX1行；原时点首00:04:19、尾07:44:56，最后首次采集07:45。00:00批次还取得8条原sessionpost的前日尾部新入库值，明确不把它们算作隔夜新成交；processed13不代表13个代码每次都有新原报价。没有补采、手工HTTP/模型或修改时间，主功能ET20–04每15分钟真实运行已核验；不将这一个窗口等同周末休市及7/30天真实保留期全部验证。

ET04:00起真实恢复每分钟，08:00–08:06七个job均已结束，但statusdegraded/processed10。最近source_health success_count16/failure_count0/backoff0，同时note明确^FVX/^TNX/^TYX三项ValueError，故是部分代码解析失败、不是Yahoo整体恢复后又全源限频。只读补充`ops/a025-yield-preopen-20261028.json`于08:23:24确认三项最新原as_of均10-27 18:59:54，首次入库20:48。现有parser在overnight容许30小时旧值，ET04后改为当日午夜起的时间门槛，这些旧值确实会被拒绝；这与错误高度一致，但未额外获取源端payload，不能冒称已实证每个响应的确切ValueError分支。旧报价的真实日期保留，未伪造新值或无依据解除过滤。影响是三种美债收益率尚无当日盘前新值，其余10代码继续分钟更新；当前无需用户操作。

本次GitHub同步首次SSL失败后一次重试成功；后续新唤醒核对遇自动审批超时，再按工具允许一次重试成功，未绕过拒绝或跳过最新控制。全部证据及状态已真实完成后回报。A025首日全天与完整隔夜观察已提供，盘中限频、部分陈旧/小盘样本与公开价格对照等已知限制仍保留，不能称整单全部业务验收通过。下一步：北京时间18:10后（10:10 UTC）合并核对下一自然日历周期是否消除既有部分失败；20:30后（12:30 UTC）仅核对自然美债新值是否到达，不主动请求源；A026下一次分task用量10-29 05:00 UTC及完整两日窗口不变。向量修复仍等待需求方明确任务，不擅自打开费用开关。已自行决定：无新增。

## OPS-A023 进行中：宏观日历部分失败已由下一自然周期恢复

2026-10-28 10:18:12 UTC（北京18:18）只读核验，生产head `4b47cac062719c406341ddf1b752b00ac7303cee`未变，main仍`bcc822f51360e17bb598dee01af8194c9327d7ee`无新任务。证据`ops/a023-calendar-natural-20261028T101812Z.json`。美东06:00自然财报job10:00:57–10:01:20 statusok/processed2603，NasdaqEarnings健康ok、failure0，未来最晚11-10；宏观日历10:01:20–10:01:49 statusok/processed152，NasdaqEconomic健康ok、failure0，最晚11-07。昨日宏观部分失败的健康状态已恢复，不把旧失败记录当作持续当前故障，也不倒写昨日完整成功。

当前表中财报Nasdaq2854行、宏观Nasdaq146行，latest fetched分别10:01:20.535739与10:01:48.264232；job processed152与表内去重146是不同统计口径，不能将152冒称最终存储行数。未手工补采、调用AlphaVantage/模型、修改代码参数/角色或重启。已自行决定：无新增；本轮审批超时后按允许一次重试完成最新控制核对，未绕过审批。下一步美债盘前当日新值在12:30 UTC（北京20:30）后只读核验；A026明日05:00 UTC用量窗口与向量开发范围等待不变。本局部源端运维限制已恢复，无需用户操作。

## OPS-A025 进行中：三种美债收益率已自然取得当日盘前新值

2026-10-28 12:37:37 UTC（北京20:37）按既定窗口只读核验；main仍`bcc822f51360e17bb598dee01af8194c9327d7ee`、A运行且无新任务，生产head `4b47cac062719c406341ddf1b752b00ac7303cee`。沿用A025 [PR90](https://github.com/XuQingsong/inves-cog/pull/90)准确head `ebd1df21a5c844b7247df1af8884fbc7716f2bf6` 的[CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40490321442/job/122142329527)，不重新部署或测试。证据`ops/a025-yield-natural-20261028T123737Z.json`。

^FVX/^TNX/^TYX最新原as_of均为今日12:21:55 UTC，首次采集12:37:00，sessionpre；此前仅有前日旧值的限制已经消除。12:36和12:37两轮自然Yahoo job均已结束、statusok/processed13；12:33–35仍degraded/10，不倒写早盘成功。新报价到首次采集约15分05秒，保留Yahoo延迟属性，不称实时。source_health仍是12:25聚合，保留degraded与三项ValueError旧note；它早于已成功的两轮，不把尚未刷新汇总当作当前三种收益率仍无新值，也不称汇总健康已经ok。

未手工请求行情源、模型或补采，无参数/来源/调度/角色变更或服务重启。已自行决定：无新增。已直接通知用户恢复，本局部无需用户操作；首日其他已说明的验收限制与7/30天真实保留期仍保留。下一步沿既定窗口10-29 05:00 UTC核对A026午夜与完整ET10-28用量、10-30 04:00 UTC后补第二个完整自然日；向量开发范围仍待明确任务，费用开关保持原批准状态。不为滞后的健康汇总新增逐分钟巡检。

## OPS-A026 进行中：首个完整自然日与第二个午夜窗口已核验

2026-10-29 05:09:12–05:16:37 UTC（北京13:09–13:16）按既定窗口只读核验；main仍`bcc822f51360e17bb598dee01af8194c9327d7ee`、A运行且无新任务，生产head `4b47cac062719c406341ddf1b752b00ac7303cee`。A026安装时间仍10-27 15:27:52.900699 UTC，沿用[PR91](https://github.com/XuQingsong/inves-cog/pull/91)准确head `49dc405ba20574a91d3869896f4d8d45b8f57508` 的[CI success](https://github.com/XuQingsong/inves-cog/actions/runs/40528031606/job/122272829343)，不重复部署、迁移或历史清理。证据`ops/a026-midnight-usage-20261029T050912Z.json`、`ops/a026-day-scope-20261029T051032Z.json`、`ops/a026-enrich-state-20261029.json`。

ET10-28完整自然日（UTC10-28 04:00至10-29 04:00）各task实际调用/输入/输出：anomaly_candidates 3/32999/4665，claim_extraction 5/10161/14942，move_card 5/156441/2093，news_card 52/84512/13669，news_translate 6/6611/4204，summary_oneliner 1/86/24；共72次、330407 token，所有记录failed0、usage_missing0。info_fields_extraction及entity_tagging均0次；新闻入库3985条、extraction_status均ok，关联news条目或news_triage用途模型调用0。news_translate的6次是保留翻译用途，与新闻分类调用0分别呈现，不称全部新闻相关模型0。52次news_card关联52条范围内sec_8k/form4，无不相关/未匹配、无空info_ids；范围依据当前池、纸面持仓和CIK映射，仅输出聚合计数。

ET10-29午夜至01:10实际仅summary_oneliner 1次、130+28=158 token，failed0/usage_missing0；news_card及停用的两个task均0。当前全部kind pending0。该午夜窗口无info_enrichment job记录；CLI仅在has_pending_info时建立job，不能编造午夜已跑某批。唯一enrich实际PID3981485存在，scheduler3981483及既有Supervisor业务进程保持，结合无pending解释当前空闲，进程存活本身不作业务成功证据。

完整ET10-28 enrich有165轮ok/processed2530、14轮degraded/processed406；向量开关仍false，既有向量缺失问题未修复，不能把模型调用成功、pending0或本次用量达标等同向量成功。本轮未重新请求向量、调模型、补采、改参数/来源/角色/调度或重启。首版只读脚本日期替换误指部署证据为10-28，读取阶段即失败，修正回实际10-27后完成；无业务写入或重复执行。

已自行决定：无新增。本次完成首个完整日与第二个午夜窗口的自然观察，两个完整自然日仍未齐；下一步10-30 04:00 UTC（北京12:00）后核对ET10-29全日并收口连续两日用量。向量开发仍须明确任务及原费用恢复边界，不擅自开启付费。当前无需用户操作；已知向量限制已向用户明确披露，不重复要求既有授权。


## A-027 已收到／阻塞：接单门槛与提交前自验清单缺项

2026-10-30 03:09 UTC起核对main `5abfd94ceb096c2446633e309d16688f438e9959`，A运行，收到核心公司财报数据准备任务。已读A-027、最新ops/README、AGENTS及只读方案 `docs/phase1/design/anomaly-first-2026-10-30.md`；确认任务限定新闻/日历相关ingest与测试，不调模型、不改规则A，期权与覆盖核查为只读。

当前门槛冲突：ops/README §1.1明确“只有看到关单，agent才领取下一个编号”，但main中没有 `ops/answers/A-026.md`，A-014补充四十四只是部署授权，没有A-026已关单记录；§1.3要求下发时提供 `ops/answers/A-027.md` 提交前自验清单，当前也不存在。A-027任务正文的测试与验收要求已读，但不能自行替需求方补写其清单或关单。需要需求方补齐A-026开发关单（可将未来自然观察单列OPS，按§1.2不阻塞开发）及A-027自验清单；无需用户重新批准持续运行。尚未开始A-027代码、真实期权请求或数据库查询，未创建PR，故无开发head/CI结果，不能冒称已开工或已交付。已直接在本对话说明。

A026连续两完整美东自然日的最后窗口仍为10-30 04:00 UTC（北京12:00）后核验ET10-29，不提前将未结束自然日写成完成；原向量费用暂停不变。A-027流程缺项不停止该已授权运维项。已自行决定：无接口/数据库/调度/来源/依赖变更。原临时状态工作区Git元数据已清理，改用 `/private/tmp/inves-cog-status-20261030` 的agent-status副本；仅改A.md，保留其他线。


## A-027 进行中：关单及自验清单已补齐，开始执行

用户直接要求“再看一下”；2026-10-30 03:22 UTC已fetch核对main `9ecfc7949bf3fefa5facc5813ce02a43aa2e6921` 新增A026已关单及A027 T1–T8清单，先前流程阻塞解除。按原任务执行，无新增用户预算或权限决定。变更：仅news_poll调度将在核心财报日的批准窗口从10分钟加密至1分钟；读取现有earnings_calendar日期/time与核心名单，限频降级到10分钟并记source_health，不改去重/分级/入库/模型开关。先失败测试提交再实现；期权免费账号可行性、29家一致预期和10-14至今日历为只读核查，结果附A027答复。部署待PR验收合并及明确安装指令，当前不改生产。


## A-027 进行中：实现与只读覆盖回报已推送，等待准确head CI

PR https://github.com/XuQingsong/inves-cog/pull/96；head `de4d654d3402963290bf41418b7d216d83cf2268`。先失败测试提交 `9187b5f`（19项实际失败），后实现提交de4d654；T1/T2核心当日财报pre/post/unknown边界与DST时钟、T3限频降级持久化/source_health、T4原rules-only新闻入库计数模型0，专项及相关调度59项通过，M1离线159项通过/13排除。本机整套M1中5项数据库检查因Docker命令不可用未通过，不伪称全套通过。T5准确head真实CI https://github.com/XuQingsong/inves-cog/actions/runs/40998117996 当前in_progress，另push运行40998079631同head；尚不能写已完成。

T6–T8已写PR中的ops/answers/A-027.md：仅3次免费indicative请求，NVDA与INTC HTTP200、200/min头；同期股票/期权ET10-29 15:59:59，最近财报后到期分别11-20/10-30、平值212.5/92，跨式粗估8.50%/8.14%。indicative报价调整且INTC IV缺失，不能冒称可成交OPRA或完整IV；首版混配盘后股票的29.80%已丢弃并在答复说明。29家eps_cq及raw当季营收均存在，但最新as_of均10-17，数据陈旧。保留8条日历与首条实际业绩新闻日期/时段一致；ASML/TSM/META更早日历历史缺失不可核验，META首入库跨日，ASML/TSM实际发布早于批准pre窗口，均如实单列，未伪造历史完整。

生产只读证据：`ops/a027-coverage-20261030T032657Z.json`、`ops/a027-options-aligned-20261030T033056Z.json`（以实际文件名为准，PR答复记录读取结果的evidence字段）。无模型/向量、付费开关、生产数据写入或部署。变更已按任务范围实现news_poll调度，不新增来源/表/依赖；Alpaca新闻使用既有120/60秒限速、加密最多120页，429当日持久退回10分钟。下一步核对准确head CI；需求方验收合并与安装授权后才部署。OPS-A026-1仍04:00UTC后按既定窗口核验，不提前宣称完成。

## A-027 已完成：PR已推送、准确head CI通过，待验收合并

2026-10-30 03:38 UTC（北京11:38）[PR96](https://github.com/XuQingsong/inves-cog/pull/96) head `de4d654d3402963290bf41418b7d216d83cf2268` 的[phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/40998117996/job/123875920897)已独立核对headSha及conclusion。干净Docker环境966 passed/60 deselected，另2项CI断言passed；本机此前缺Docker的检查已由完整CI实际运行验证。先失败测试完整SHA `9187b5fbd43ada01c3b69b358a0389b7941b9f75` 保留，19项实际失败后实现。

自验逐项：T1 `test_core_date_only_and_durable_backoff`、`test_schedule_reads_persisted_calendar_and_does_not_change_other_tasks` 验真实形态report_date/time、核心/非核心/非当日；T2 `test_window_boundaries` 验pre/post/unknown及边界，`test_dst_local_window_and_utc_persisted_start` 注入DST切换日；T3 `test_poll_rate_failure_persists_ten_minute_fallback`、`test_accelerated_news_budget_and_no_model` 验429立即退出、持久退回10分钟、source_health degraded及页预算；T4 `test_poll_calls_existing_rules_only_ingestion` 验原路径入库和计数triage零调用，其余任务集合不变；T5准确head CI成功如上；T6 NVDA/INTC免费indicative同期跨式样例附答复，明确INTC IV缺失、报价调整及非实时可成交限制；T7全部29家最新as_of、eps_cq、raw当季营收覆盖表已附，as_of均10-17陈旧；T8保留8条日历日期/时段一致，更早历史缺失、迟入库、窗口外发布均明确列出，未将不可核验称为全对。

交付物ops/answers/A-027.md T1–T8回报及源码/测试均在PR。证据文件名已核对为 `ops/a027-coverage-20261030T032657Z.json`、`ops/a027-options-aligned-20261030T033056Z.json`。已自行决定：无新增接口、来源、依赖或预算；按任务实现调度，保留原rules-only新闻和所有模型/费用开关。未合并、未部署、未写生产业务数据，代码交付不等于线上分钟采集成功。下一步需求方验收、合并及下发安装，A不自动合并；OPS-A026-1仍北京时间12:00后按既定窗口收口，当前不到点，不提前重复查询或重新部署。

## OPS-A026-1 已完成：连续两个完整美东自然日用量已收口

2026-10-30 04:04:26 UTC（北京12:04）到既定窗口后，只读核验ET10-29完整日，即UTC10-29 04:00至10-30 04:00，严格上界不混入新日调用。main `9ecfc7949bf3fefa5facc5813ce02a43aa2e6921`、A运行，生产head仍 `4b47cac062719c406341ddf1b752b00ac7303cee`；A026 [PR91](https://github.com/XuQingsong/inves-cog/pull/91)准确head `49dc405ba20574a91d3869896f4d8d45b8f57508` 的[CI SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/40528031606/job/122272829343)沿用，未重新部署。证据 `ops/a026-final-day-20261030T040426Z.json`。

ET10-29各task实际调用/输入/输出：anomaly_candidates 9/86727/9124；claim_extraction 14/25372/24375；move_card 14/214496/7884；news_card 10/14498/2577；news_translate 6/7579/4969；summary_oneliner 1/130/28。合计54次、397759 token，全部status ok，failed0、usage_missing0。info_fields_extraction及entity_tagging均0。news_card关联10条均池内/持仓相关8-K或Form4，无范围外、未匹配或空info_ids；只输出聚合，不输出持仓。新闻first_seen入库4218条全部extraction_status ok，关联news条目/news_triage模型调用0；保留翻译6次单独呈现，不能称全部新闻相关模型0。当前所有kind pending0。

与已核验ET10-28第一日（72次/330407 token、新闻3985条、news_card52条均相关、两个停用task0、新闻分类0、failed/usage_missing0）合并：两个完整日126次/728166 token，新闻8203条、分类0；非新闻news_card分别52和10次。首日证据及分类范围沿用 `ops/a026-midnight-usage-20261029T050912Z.json`、`ops/a026-day-scope-20261029T051032Z.json`，不重复请求源或模型。用量随异动归因任务增加有变化，不以总token高低替代用途收敛判断。

ET10-29 enrich共165轮ok/processed2487、9轮degraded/processed295，全部ended且unfinished0；向量开关仍false，既有向量缺失/停用记失败问题仍保留为OPS-A026-2，不能把pending0、调用成功或观察结束冒称向量恢复。未重新诊断/开启向量、补跑、改参数、来源、权限或重启。本次只完成已批准的连续两日用途/费用观察，不等同系统整体或全部数据源验收。

已自行决定：无新增。下一步需求方取本收口证据验收；A027 PR96准确head CI已成功，仍待验收合并及明确安装指令，A不自行合并部署；没有新任务或可行动变化则结束本轮，原持续接单授权与a-github定时器保持。

## A-014 补充四十七 已收到／进行中：部署已验收B069

2026-10-30 07:33 UTC，main `21e57dcc096316390665f36e6493fa33303aa715` 新增明确安装指令。PR97已MERGED，验收head `da3d9ad4cc0d26d65f805dc7ba6dcc565fa8441f` 的[phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/41019939953/job/123944710612)与merge `1672681b85666382c39bf56159e3623d8020ab19` 已核对。变更按批准范围：先管理员仅执行phase1_m7_0003迁移，再以现有perception最小业务角色单次回填10-27至10-30，新增唯一live_perception常驻，重启anomaly_daily和pages，其余进程及8091保持。先检查生产现存表、真实进程和已提交前缀；回填设置远端期限，失败不盲目重跑。无模型、规则A、费用开关或新来源变更。完成安装与实际结果后再报告业务进度；今晚ET21:10后另核对自然异常写入。

## A-014 补充四十七 进行中：B069安装、回填及首次真实增量已完成

2026-10-30 07:41:31 UTC（北京15:41）生产安装验收merge `1672681b85666382c39bf56159e3623d8020ab19`，工作区干净。沿用[PR97](https://github.com/XuQingsong/inves-cog/pull/97)准确head `da3d9ad4cc0d26d65f805dc7ba6dcc565fa8441f` 的[phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/41019939953/job/123944710612)，无未合并代码。管理员仅执行 `phase1_m7_0003_news_events.sql` 一次，SHA256 `0e02b5f7c8a5a26f9a7cdabc70b5ca7c8aa9fdd5c813ca73fb7832a5b68439f1`；迁移前两表均不存在，迁移后业务perception角色具备写表权限且不是管理员成员。

明确授权单次回填 `--replay 2026-10-27 2026-10-30`，远端80秒期限，返回码0，日志 `events=299 items=11518`；表从0变299行并提交游标。之后证据序列化遇datetime TypeError，阶段停在replay_verified，未启动新进程或重启旧服务；只读核实299行、已提交游标及回填PID退出后，仅修复证据保存并续接启动阶段，没有重复迁移或回填。脚本日期参数按现有实现筛first_seen UTC日期，因此事件ET日期范围实际10-26至10-30，未将这个结果误写成纯ET10-27窗口。

live_perception唯一PID1816793，沿用anomaly_daily环境/目录/日志配置，仅追加新program。随后指定anomaly_daily旧774142实际退出、新1816798；pages旧221534退出、新1816826。其他所有Supervisor业务PID保持，包括scheduler3981483、四路行情4057908/4057916/4057966/4058013、M9 3599229、翻译3258700等；参数/模型任务配置hash保持。未停止8091，核验仍监听。embedding仍按原授权关闭，无任何模型/向量请求或费用开关变化。

启动5分钟内首轮真实日志 `events=2 items=42`；07:42:14独立只读复核 `pass failed` 次数0、news_events仍299（增量upsert不是新增2行）、live_cursors `live_perception_events` value `2026-10-30 07:41:03.780511+00:00`、updated_at `07:41:15.987525+00:00`。首轮回填游标value `07:31:12.480157+00:00`已真实推进。HTTP `/`、`/s/INTC`均200；不把接口200或进程存活等同今晚异常识别已成功。证据 `ops/b069-deploy-20261030.json` phaseverified、`ops/b069-replay-20261030.log`、`ops/b069-verification-20261030.json`。

已自行决定：无新增业务/权限范围；仅在核实已提交前缀后恢复未完成安装步骤。下一步按补充47第6条，于ET10-30 21:10后（UTC10-31 01:10，北京10-31 09:10后）核对当晚anomaly_daily实际写入的盘后异常条数/成员及post_sigma_fallback次数；当前安装阶段完成，未来自然运行尚未验证。A027 PR96仍待需求方验收合并，不借本次B069部署提前安装A027。

## A-027 部署运维 已收到／进行中  2026-10-30 19:47 北京

收到 A-014 续十四补充四十八：PR96 已验收关单并合并 `544a78ad1c38572c0c53d132800bcf7c25fba99f`，准确 head `de4d654d3402963290bf41418b7d216d83cf2268` 的 [phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/40998117996/job/123875920897) success 已重新核对。变更：快进最新 main，只重启 scheduler；无迁移、不手工触发采集或模型，其余服务含 live_perception 保持。先核对真实进程及工作区，再安装并检查自然 news_poll 间隔、AlpacaNews source_health。A-028 已收到信箱，按一次一单，在本次部署收口后领取；未来财报窗口证据独立跟踪，不占开发任务位。

## A-027 已合并安装，真实运行验证进行中  2026-10-30 19:48 北京

生产已快进至 `583b7f3a00e8c2b2d538f7ef00c45db193752e6f`，包含已验收 merge `544a78ad1c38572c0c53d132800bcf7c25fba99f`；[PR96](https://github.com/XuQingsong/inves-cog/pull/96) 准确 head `de4d654d3402963290bf41418b7d216d83cf2268` 的 [CI](https://github.com/XuQingsong/inves-cog/actions/runs/40998117996/job/123875920897) success。安装及独立进程对照完成，仅 scheduler 更新，其余运行服务含 live_perception 原进程保持，服务配置未改，无迁移或手工采集/模型调用。详细证据 `ops/a027-deploy-20261030.json` 保存于项目私有运行目录。

安装时 AlpacaNews source_health=ok、连续失败0；近6轮新闻任务均ok、约10分钟间隔，但这些是安装前证据，未冒称新版本自然运行成功。下一步：后续唤醒核对安装后自然 news_poll 实际间隔及 source_health；下一核心公司财报日再核对分钟窗口和发布→入库延迟。未来窗口独立跟踪，不阻塞 A-028 开发；本轮不重复采集或重启。已自行决定：无。

## A-028 已收到／进行中  2026-10-30 19:56 北京

A-027 已见需求方关单，新单 A-028 与 T1–T6 自验清单齐备。解决财报前一致预期过期、日历不足和缺少隐含波动参考数据；先只读核实停更根因，再按授权实现、先失败夹具测试后修复。变更：限定 ingest、schedule_consensus、phase1_m1_0010_implied_moves 及测试；每日一致预期范围为标的池∪持仓∪核心公司，日历至少45天，期权仅 indicative、交易日ET15:50、独立source_health。无付费源、模型、规则A或跨线改动。新表和调度安装只在需求方验收合并并下发部署后执行；首个15:50自然样例另验。已自行决定：无。

## A-027 普通日自然运行已验证  2026-10-30 20:07 北京

安装后两轮news_poll实际起于UTC11:50:11、12:00:20，均结束ok，间隔约10分09秒（自然轮询调度误差），没有在今日无核心财报时变成每分钟。AlpacaNews=ok、连续失败0、last_attempt12:01:11；本轮只读核对，没有补跑或新增模型调用。证据并入私有 `ops/a028-diagnosis-20261030.json`。A-027准确head/PR/CI沿用已报告安装记录；下一核心财报日窗口内实际间隔及发布→入库延迟仍待自然运行，不占A-028开发位。

## A-028 进行中：根因确认，修复已推送、准确CI待结果  2026-10-30 20:25 北京

根因已核实：Alpha常驻正常更新独立valuation表，fundamentals基本面表仅10-17一次m2_consensus，后续没有派发；日历只取前10个交易日。Nasdaq一次只读实查11-17实际有NVDA post，不需新来源。先失败8项提交 `fa4adb3`，实现及本地相关回归通过；已推送分支phase1/a028-earnings-data，迁移和生产调度尚未执行。详细答复在分支ops/answers/A-028.md；新表写权限及Postgres集成测试等待准确head CI，不预记通过。下一步取CI结果并修复实质失败，完成后送需求方验收。

## A-028 已完成（代码与离线验收），待需求方验收合并  2026-10-30 20:30 北京

[PR98](https://github.com/XuQingsong/inves-cog/pull/98)，完整head `76e9d193ae86e1d484ebf4d7a1cafa97260ec73b`，[准确head phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/41055026790/job/124060275390)。实际干净容器985 passed、80 deselected，随后CI断言2 passed；日志明确 `tests/m1/test_a028_database.py .`，不是待运行检查。先失败历史 `fa4adb3`（8 failed）保留，本地专项17通过，相关调度/新闻/基本面回归64通过（后续新增调度用例也专项通过）。工作区干净，未自动合并、未生产迁移、未重启或运行新采集。

- T1：只读job_runs和源日志证明常驻Alpha每天正常写独立valuation表，而m2_consensus仅10-17一次，根因是基本面采集未调度，不是Alpha停更。新增独立每日调度、成功快照写入和失败degraded；`test_daily_estimates_uses_existing_free_page_when_json_requires_auth`覆盖现有公开页面回退。
- T2：范围并集、当季raw金额及币种、缺失不以年度代替、captured_at PIT读取；`test_consensus_scope_and_raw_quarter_currency`、`test_consensus_snapshot_reader_has_cutoff_and_raw_fields`、`test_daily_scheduler_scope_health_restart_and_options_slot`通过。
- T3：查询今日至+45天、保留原失败日期处理；`test_calendar_horizon_includes_45_days_and_holidays`、`test_calendar_missing_90_days_and_nasdaq_nvda_shape`通过。上线前库未来90天核心缺口20家已逐项写答复；Nasdaq真实一次请求能取NVDA11-17 post，未补写日历或新增源。
- T4：`phase1_m1_0010_implied_moves.sql`按批准表与角色矩阵；pre/post/unknown到期日、最近行权价、交易日15:50和重复采样、缺IV、同秒股价及旧报价拒绝均通过。真实Postgres集成证明ingest写入、web只读、同日重启不重复。
- T5：indicative固定、有限分页、200/60秒限速、429单次退出和独立AlpacaIndicative health；`test_option_pagination_http_429_and_reference_feed`、`test_unaligned_and_missing_quotes_record_degraded_health`通过；调度和采集路径模型客户端构造计数均0。
- T6：上述准确head CI已真实完成。分支answers中提交前的“待CI”时间截面，以本条结果和PR最新CI为准，不沿用其他head。

证据：PR内ops/answers/A-028.md及私有 `ops/a028-diagnosis-20261030.json`、`ops/a028-coverage-20261030.json`。已自行决定：时间对齐允许±1秒，call/put≤1秒且报价采样不旧于120秒；缺少对齐值留缺并degraded，未混时段补值；沿用既有免费Yahoo页面处理JSON鉴权/限频；Alpha任务避开15:35–15:51、新基本面任务避开15:30–15:51保证采样时隙，均未扩大模型/来源/权限。

下一步：需求方验收合并并下发部署后，A执行唯一迁移及指定服务安装。之后自然更新基本面/45天日历，重新核对核心90天缺口；首个交易日15:50 implied move真实样例仍待自然运行，未冒充完成。本项代码交付不阻塞未来运维窗口；A-014补充47盘后自然异常核验仍按北京时间10-31 09:10后执行。

## A-029 已收到／进行中（2026-11-04 北京）

用户决定 UD-A-52：继续按原 GitHub 信箱流程每 10 分钟接单。A-028 已由交接方关单并负责部署。A-029 以 PR120 `a7c6d70abd3e67ce9a0cd1520799d21a49ff3ba5` 为基线，按 T1–T10 验证。新增回测开关默认关闭，仅在 Mac 本地库回测，最多 6 个并行进程。已确认本地回测库及面板可用，本地缺晴雨表，F2 市场确认输入将在授权窗口只读复制。其他验证先行。

A-029 进行中（2026-11-04 北京）：Mac 本地原始基线实际完成，481 笔交易，trade_hash `f56ffe611b7c029a8e55a59936fdb298b9ce902377c8a74ff39428d0e4a7e767`，结果 `/private/tmp/a029-original-baseline.json`。F1 首组测试先失败提交 `9177d82`，初版 `3a4771f855256db46503ef1365e37ec08194d6a6` 两项测试通过，挂接限于回测引擎。默认关闭复跑已启动，尚待核对指纹。后续继续 F2–F6 和批量评估；晴雨表复制须等美东授权窗口。尚无交付 PR 或 CI 结果。

A-029 进行中：F1 接入后默认关闭复跑与原始基线 trade_hash 完全一致。F4 观察仓通过核心门槛后在卖出判断前转核心，F5 使用决策日前最近周五的面板替换估值门槛，估值前五分之一以向上取整并含边界并列处理。均保留先失败历史。当前本地 head `caf90dca3e3f13261ad13510889be933cdb1d97c`，专项 5 通过，尚无交付 PR 或 CI。下一步 F2、F3、层级数据诊断及合并后的最终回归和评估。

A-029 进行中：F2 破位确认初版 `c563ac3906f2cc5b09f4f8fafee70074ee99026d`，先失败提交 `cc3e485`，专项累计 10 通过。未获基本面或市场确认时，使用 MA200 下方连续收盘或超 1 倍 ATR 确认，首次减半。ATR 取最近 14 个交易日真实波幅的算术平均，基本面红线与技术破位分开。生产晴雨表尚未读取，实际 F2 回测未运行。下一步 F3、F6 和本地评估。

A-029 进行中：F3 买回初版 `cb569300afa07ba1e2f8e4ee6318c9f072b61d40`，先失败 `c919483`，专项累计 14 通过。按实际价格清仓成交启动计数，三个收盘连续站上 MA200 后才允许估值分豁免，仍受基本面和透支否决约束。只读确认 TSM/V/SNDK 本地都有 fixed 财务行，尚不能据此判断缺层级原因。已启动单进程 PIT 层级诊断与最新默认关闭复跑，限时 900 秒，结果待核。F2 生产晴雨表未复制，组合评估未运行。

A-029 进行中：59 只本地 PIT 层级诊断完成。V 有层级 67/2220 日，主要缺核心财务字段；TSM 6/2220 日，主要为财报滞后、过期和成长分缺失；SNDK 54/431 日，先缺行情长度，后缺第四季度。SKHY 80 日全缺足够行情。证据 `/private/tmp/a029-tier-diagnostic.json`，尚未补齐源数据，不将默认层级当修复。F3 后默认关闭指纹仍完全一致。滚动评估补齐三项差值分位统计，本地 head `252b04efe8e237933201caaa1af1725a2ff918db`，专项 14 通过。已启动仅 Mac 单进程、限时 900 秒的 base/F1/F3/F4 个案，待读实际结果。尚无交付 PR 或 CI。

A-029 进行中：本地 62 只个案已完成 base/F1/F3/F4/F5/veto（193/185/225/194/190/191 笔）。F3 在个案中触发 AAPL 2026-06-24 买回，GOOGL 2025 年没有符合新条件的买回成交。F5 首次买入 AAPL 2026-01-27、GOOGL 2024-02-08；AMD、KO 无买入。当前本地 head `866da5e6dd910d74825f9b876995c327e19a044a`，本地 m3/m4 与专项 71 通过（含 v18），另 2 项容器数据库用例因本机缺 Docker 报错，待 CI。Mac 本地四工作进程滚动评估已启动，限时一小时，当前只含不依赖晴雨表的变体，F2 和组合版未运行。F6 源数据缺口仍在核对，未造补齐结果。

A-029 进行中：已推送基于 p2-v1 的[草稿 PR121](https://github.com/XuQingsong/inves-cog/pull/121)，head `01fae25d45a3fb0032a1bbfff56a15752fc52e04`，[对应 phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/41862892734/job/126689319942) 已排队，尚无结果。先失败测试后实现按实际成交与交易所交易日核对短持有，专项 15 通过。部分滚动评估尚无结果文件，完整组合仍待晴雨表授权窗口。草稿用于提前运行 CI，尚未送最终验收。

A-029 进行中（2026-11-05 北京）：Mac 28 起点部分滚动已实际完成，五组结果 `/private/tmp/a029-rolling-partial.json`。收益差中位数（百分点）F1 +0.391、F3 0、F4 −5.656、F5 −8.118、veto +65.598；收益胜出占比 57.1%、39.3%、35.7%、39.3%、75.0%。这是固定池回放，非完整组合结论。逐笔部分评估已单进程启动，尚无结果。PR121 同一 head 的 phase1-blocking 仍排队。F2 与组合继续等生产只读窗口，F6 缺口待解决。

A-029 进行中：五组逐笔结果 `/private/tmp/a029-signals-partial.json`，每组 259 笔基线买入。当前匹配用同标的、同信号日成交，缺配对包含仓位路径差异，不能直接归为规则否决。veto 同日匹配 117、缺配对 142，后者 20/60 日收益中位 +1.9%/+7.5%。F6 本地 SEC 缓存离线复算四个日期证实 V 仍缺 EPS TTM/增速、SNDK 仍缺第四季度与 EPS 增速。证据 `/private/tmp/a029-financial-probe.json`，未改本地或生产表。下一步检查原始事实可用性及修复可行范围，F2 仍等授权窗。PR121 对应 CI 仍排队。

A-029 进行中：PR121 `01fae25d45a3fb0032a1bbfff56a15752fc52e04` 的 [phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/41862892734/job/126689319942) 已实际 SUCCESS，仍是草稿阶段。Visa 根因进一步确认：公司级 CompanyFacts 没有可用 EPS，现有 D9 需要 Class A 维度申报实例。本地缓存 10 份，离线按申报日累积重提验证出 9 期 EPS TTM，其中 6 期有同比，4 期仅余非阻塞 ni_tag_fallback。证据 `/private/tmp/a029-v-instance.json`。下一步验证这些真实快照转成回测层级并做隔离输入，不写线上数据。TSM/SNDK 仍核对可恢复性。

A-029 进行中（2026-11-05 北京）：PR121 `eca036c8036359f2d403c90d5473496726350cf5` 的 [phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/41869237874/job/126711442125) 实际 SUCCESS。Visa 可选离线修复已验证：67→326 个有层级交易日（总 2220），首次 2024-07-24 防守，完整日史 `/private/tmp/a029-v-repaired-tier-history.json`。TSM 两个本地缓存目录为空，索引对应 2026-10-08/15 的 6-K，无可用附件。SNDK 两份本地 CompanyFacts 均缺 FY2025 独立 Q2 diluted EPS，无法以已知 Q1/Q3/FY推导 Q4；不能把累计 EPS 当可加减独立季度。两项修复需要带原始披露时间的申报附件或等效可核查数据，等待需求方提供或明确指定已批准的获取途径。F2/组合仍按计划等授权窗，不停止其他本地工作。

A-029 进行中（2026-11-05 北京）：已收到 main `79f739e731d2c8c7e552bd723345361518942bbe` 的需求方答复。UD-A-53：TSM 可在 Mac 本地从 SEC EDGAR Archives 获取 6-K/20-F 附件，遵守 SEC 限速，以 acceptance 时间做 PIT，半天内无可核查季度 EPS 则保留缺口。SNDK 分拆前无独立 Q2 EPS，满四个独立季度前保留缺层级，不借用 WDC。晴雨表按原授权窗口只读复制，覆盖不到的日期走技术分支，并逐起点报告覆盖率。最终追加 veto 前五贡献及剔除后中位数。现有 PR121 head `eca036c8036359f2d403c90d5473496726350cf5` 的 [phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/41869237874/job/126711442125) 已通过，仍为草稿。下一步开始 TSM 有界取证及本地评估，晴雨表北京时间 11:00 后读取。

A-029 进行中（2026-11-05 北京）：UD-A-54 用户在 A 线对话直接决定“我觉得没必要，现在就开始吧”，批准本次提前只读复制 `flows.barometer_daily`。保留最小权限、单进程、nice/ionice、查询超时和范围约束。仅复制日期、可见时间和恐慌等级，回测在 Mac 的 inves_cog_bt 执行。逐起点覆盖率已推送到 PR121 `cea1a415b03018948ecf5ce11910ebb904db709b`，本地专项 17 项通过，准确 head 的 CI 待核对。

A-029 进行中（2026-11-05 北京约 10:28）：按 UD-A-54 发起生产只读导出，仍无完整 CSV，Mac 回测未启动。线上卡顿时一次 SSH 探针成功，负载 33.49/33.66/33.55，约 2.1 GB 可用内存，swap 已用 521 MB，根盘 48%，本任务远端锁当时被占用。随后的 CPU/I/O 和进程采样因 SSH 无响应超时，根因待查。导出有远端 40 秒进程期限和 12 秒查询期限；本地 SSH 等待不作为作业存活或成功证据。下一步先核对远端锁和导出文件，再决定是否重试，避免并发。

A-029 进行中（2026-11-05 北京约 10:31）：已读需求方答复三，小批量生产只读随时可做，保留单进程、只读账号和查询超时，生产禁止回测。只读诊断确认主机 2 核、负载 30.41/32.42/33.11，采样 30 个阻塞进程、73% CPU 时间等待 I/O、I/O PSI some avg10 99.43% / full avg10 65.42%，19 个 Python 进程在 folio_wait_bit_common。直接卡顿机制是严重 I/O 等待，触发作业尚未确认。导出锁仍占用，本地文件仍为零字节，未重试或启动回测。

A-029 进行中（2026-11-05 北京 10:40）：生产 I/O 压力持续，avg10 some 99.96%、full 66.33%。20 个 D 状态 Python 进程同父 PID 1258，cgroup 明确属于 inves-cog-ingest.service；父进程 11-03 10:25 启动，早于本次导出。该服务是采样中最大受阻进程组，仍未确认造成存储拥堵的读请求或磁盘侧原因。晴雨表 flock 仍占用，零字节输出，未重试。未重启或停止共享服务。

UD-A-55（2026-11-05 北京）：用户要求实际解决线上卡顿。只读采样确认本项目 inves-cog-ingest.service 占整机同窗口物理读量 140623872/147808256 字节。已自行决定仅临时停止该服务并复测压力，影响采集更新，保留数据、配置和其他服务。确认恢复条件后再启用，避免未经核验反复拉起。

UD-A-55 执行结果：采集服务已实测 inactive/dead，MainPID=0。停止后阻塞进程 30→0，实时 I/O 等待 73%→0%，I/O PSI some avg10 最低复测 0.08%。采集更新暂时停止；服务仍 enabled。仓库网页脚本默认端口 8080 无监听，未确认线上网页入口。原晴雨表导出 SSH 超时、锁已释放，输出零字节。自动审批拒绝了移除时间保护并重试导出的组合命令，未执行；先保留保护，回测未启动。

UD-A-55 续：已核对生产 HEAD 77e8661e9061aeea8d9cbbacb71e3b201156265a 包含于 main，既有 supervisor 同时托管 pages 和采集。已自行决定用同一已部署网页入口单独恢复，临时 user unit，保留原端口及只读数据库角色；采集仍隔离。

UD-A-55 续：已部署网页以临时 inves-cog-pages-recovery.service 独立恢复，服务器原端口 / 实测 HTTP 200（2.915 秒），采集仍隔离。A-029 保留原时段保护的导出尝试因美东窗口尚未开放而退出，无完整文件，无本地回测。

UD-A-56（2026-11-05 北京）：用户直接答复“恢复同步，继续完成 CI 和验收提交”。已恢复同步，核对 main 3f45059fb97aaa57e28558ba048dac62d48628eb 的答复，服务器后续处理归 SWE-2，A 继续仅 Mac 本地 A-029。晴雨表 2220 条已复制并导入 Mac，逐起点 PIT 覆盖率 100%；F2/组合版和修正版全部评估完成。修正加仓持有期后，组合版短持有 88→1，剩余 VRT 2025-02-25 M-51 灾难止损，普通短持有 0；T2 字面“总数 0”保留差异，未伪称完全满足。默认关闭 trade_hash 与原始基线一致。离线 75 passed（含 v18），容器数据库测试未在本机执行。透支否决剔除 WDC/MU/LRCX/AMAT/STX 后收益差中位数 +65.60→+0.17 个百分点。下一步推送完整报告和可复核证据、核对准确 head CI 并提交验收。最新本地 head 8e41c5f 尚无对应 CI。

A-029 进行中／已提交验收（2026-11-05 北京）：[PR121](https://github.com/XuQingsong/inves-cog/pull/121) 已转非草稿，head `0fc0c53e70a1b91d033a0ddadea96431d175e779`；已核对 Actions head_sha 完全相同，[phase1-blocking 实际 SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/41990281088/job/127120610752)。代码、T1–T10 回报及 17 份 checksummed 实际输出已推送，位置 `ops/answers/A-029.md`、`handoff/A029/report.md`、`handoff/A029/evidence/manifest.json`。本地 75 passed（含 v18），最终默认关闭 481 笔 trade_hash 与原始基线相同。F2/组合每个起点晴雨表覆盖率 100%，修正版组合收益差中位数 −15.15 个百分点，F1 −9.33；veto 剔除前五贡献标的后 +0.17。已自行决定保留 F1 明确允许的 M-51 灾难止损；T2 字面总数 0 尚有 1 笔差异，VRT 2025-02-24 买入、次日 M-51，普通短持有 0。该差异已在 PR 单列请求需求方验收裁定，未自行放宽标准或删除合法止损。下一步由需求方验收并决定合并，A 持续接收答复，不自动合并或部署。

A-029 已完成／需求方已关单（2026-11-05 北京）：最新 main `7d3260d6f24094361cfdec1becb5eb14d60c3007` 的 `ops/answers/A-029.md` 明确验收通过，接受 T2 一笔 M-51 灾难止损例外及 TSM/V 输入限制。[PR121](https://github.com/XuQingsong/inves-cog/pull/121) head `0fc0c53e70a1b91d033a0ddadea96431d175e779` 的 [phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/41990281088/job/127120610752) 已核实。需求方合并至 p2-v1 `9ea9725`，已核对交付 head 被包含。未合入 main、未部署；p2-v1/main 冲突的后续合入另行安排。需求方结论：F1–F5 及组合的收益中位差均为负，透支否决优势高度集中，均无上线依据，线上规则 A 保持原行为。证据见 PR 的 handoff/A029 及 T1–T10 回报。已自行决定项见交付报告，无新增决定。下一步继续每10分钟接收 A 线信箱，目前无 A-030，不重复运行或部署。

## A-030 已收到／进行中（2026-11-05 北京）

收到 main `625dd38bc4aa9559acdc07cb5d79ce806316fa1b` 的 A-030 及 T1–T10。解决隐含天花板展示、长期风险提示和 Visa EPS 缺失。变更范围按任务授权：合并 p2-v1 到交付分支、valuation_v1 新表与每日计算、版本化阈值、页面与计划理由、公司级 EPS 缺失时维度回退；不改变交易行为。先处理基线冲突并保留 #122/#123，再保留失败测试/夹具后实现。生产迁移、财务回填及指定服务部署仅在需求方验收合并后执行。已自行决定：复用现有分类优先；缺现成分类时按任务默认建议提问并推进不受影响部分。当前无 PR 或本单 CI，不将待执行验收计为完成。下一步核对分类与数据合同、解决基线冲突。

## A-030 进行中：代码阶段已推送，生产取证部分受阻（2026-11-05 北京）

[草稿 PR124](https://github.com/XuQingsong/inves-cog/pull/124)，当前已推送 head `2c87dbf6a6678d4cd67e6f13d86bc0c0c1c708cf`。整合 main `625dd38bc4aa9559acdc07cb5d79ce806316fa1b` 与已验收 p2-v1 `9ea9725488126c7c7347f974119f910b0725f2f5`；唯一答复冲突保留交付明细和验收关单，main的性能修复未覆盖。未合入main、未部署。阈值真实校准52周23625样本，p60=2.973940812973705、p80=4.3594142175667。实现每日ceiling输出/持久化迁移、展示、计划理由后置注释、EPS只补公司级缺失期间及独立来源标记。保留先失败测试历史；最新本地相关108 passed、2 live deselected（含v18回放），Docker数据库用例未在本机执行。

首轮 head `34afa643ca512756838d6e080f6dd50578bd2298` 的 [CI实际失败](https://github.com/XuQingsong/inves-cog/actions/runs/42051809460)：1014 passed、1 failed，原因是历史样本不足事实提示被删；已恢复该提示，仍删除历史PE分位数值合理性表述。新head CI尚待读取，不沿用旧CI、不记通过。迁移 `phase1_m5_0003_ceiling_daily.sql` 未执行；权限设计仅valuation写新表、web/trading只读，撤销其他默认继承权限。

证据 `handoff/A030/progress.md`、`handoff/A030/evidence/`。Mac本地只读副本2026-11-02的59只算法实测约0.074秒、进程峰值42.95MB，不等同完整每日服务耗时。该副本缺真实当日层级/FY1，且早于阈值校准日，均明确missing，不伪造历史档位。Visa现有真实缓存当前恢复4个有效状态，2026-04-29 EPS TTM由缺失到11.47；未生产回填，完整层级覆盖未验收。GOOGL/META缓存公司级EPS存在；BRK.B缓存缺失，尚待检查。

卡点与owner：生产SSH两次在登录阶段直接关闭，导出脚本未执行，没有运行远端任务或写数据库；故最新生产59只/KO手算、生产形态截图和同日新旧计划业务对照尚未完成。连接根因未定，需要服务器运维方核对SSH连接限制/服务日志；A负责连接恢复后的有界只读取证、其余代码和CI继续推进。GitHub本轮也间歇TLS/EOF，已重试成功推送当前head及同步状态；不据此断言服务器故障根因。已在本对话直接告知用户，未仅写Git后静默。

已自行决定：复用m5现有周期/金融分类；使用线性横截面分位后取52周中位数；未来校准不得用于历史档位；保留实例origin并用独立eps_fallback标记，防改选值优先级；待成交订单的估值理由幂等更新，避免每日累加。下一步核实当前head CI并修复失败，连接恢复后完成T3/T6/T7/T8/T9真实证据，尚不提交最终验收。

A-030 阶段核对更新：当前 head `2c87dbf6a6678d4cd67e6f13d86bc0c0c1c708cf` 的 [phase1-blocking 实际 SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42058532358/job/127353459493)，已核对 Actions headSha 完全相同，完成时间 UTC15:52:43。之前 f6abb03 的CI也通过，但以当前head为准。代码和最新阶段状态均已推送。只读替代验证：项目网站公开NVDA/监控池接口均HTTP200，说明网页入口可访问；监控池2026-11-04接口59只均未提供估值原始输入，不能用其伪补生产核算。SSH两次登录前关闭的原因仍未定；未因SSH故障断言整机卡死。后续取证仍需运维方协助核对SSH服务/连接限制；A负责恢复后的已授权小批只读及最终验收材料。整体任务保持进行中，PR124仍草稿，未合并、未部署，不重新请求原范围授权。


## A-030 进行中：生产取证已恢复，Visa完整补缺试算完成（2026-11-06 北京）

当前[草稿PR124](https://github.com/XuQingsong/inves-cog/pull/124)已推送代码head `50891ad308dc542bdc9e8d792250a4bd5b7d7bb7`，对应[真实CI运行中](https://github.com/XuQingsong/inves-cog/actions/runs/42084555376/job/127446045399)，未计为通过。此前51e1234的CI失败（1021通过/1失败）为B064沿用已禁用的“目标价”文案断言，现改为机构观点更新并保留真实分组/计数断言。main仍625dd38bc4aa9559acdc07cb5d79ce806316fa1b，未部署/迁移/生产补写。

SSH恢复后已完成有界只读导出，不再等待运维修复SSH。真实2026-11-04的59只公开输入离线公式计算0.03324秒、33.73MB，39growth/12cyclical/6loss/2financial，30只有m；缺当日层级明示按8%，校准晚于历史日故band不适用。KO不在监控池、生产无fin_state，以已有Mac财报+生产价格单独手算并标明混合来源，不伪称当日产出。NVDA/GOOGL独立几何现金流现值核对误差约1e-14，MU/INTC明确周期/亏损路径。

真实11-04计划缺失，未用空结果通过。改取最近10-30已发布计划，在服务器内执行同一理由注释并逐字段比较；2处理由变化，其他字段完全相等，只输出聚合和摘要不导出交易/持仓明细。四张个股页以服务器内先过滤公开字段的快照渲染分支代码，已刷新核验；不冒称已部署。T6持仓图尚缺：此前完整响应导出被自动审批拒绝（可能含私密仓位）；公开字段服务器预过滤替代已成功。已在本对话一次性询问用户：允许服务器内完全遮盖身份/数量/成本/金额/比例/交易明细后只导出结构与新增文案截图用于PR，或不外传持仓页改用夹具截图与服务器内检查；未收到答复前不传私密页面，其他工作继续。

Visa47份官方附件全部缓存，首批20份后TLS超时已退出，核对前缀后仅续取剩余16份、180秒期限完成，无重复作业。完整Mac离线EPS-only试算：生产47状态EPS非空1→46，2223交易日层级覆盖70→2203，45条待补；最新2026-07-29已非空的EPS11.75保留，首份2015-01-29前序期间不足仍缺。旧4状态/8条补缺等为中间证据，以完整文件a030-v-history-repair-final.json为准，尚未生产回填。旧年份分类缓存缺失时，离线核验脚本只读缓存XML且严格核对CIK/ClassA配置/USD-shares/披露日；现代10份附件与既有Arelle提取EPS事实逐份完全相同。GOOGL/META生产当前公司EPS存在；BRK.B/BRK-B不在监控池且无profile/财务行。回填脚本要求已合并main及非管理员ingest业务角色，只更新EPS缺失原行并幂等，不覆盖其他事实。

本地纯A03020项通过；m3/m4/m5+A030排除需Docker用例100 passed、2 live deselected，含v18。数据库权限/幂等交准确head CI验证，本机无Docker不计通过。已自行决定：按真实原计划选择10-30对照，不把缺失11-04当空仓；只补EPS不以重提取整行覆盖历史；旧taxonomy缺失采用离线显式EPS证据且交叉验证，不额外请求外部分类文件。无新增付费/模型/账户/权限/生产服务变更。

剩余与owner：A负责最终CI、证据manifest、T1–T10回报与隐私安全持仓图；用户仅需答复截图交付边界。需求方负责验收和合并，之后A按原授权执行唯一迁移、45条EPS补缺、只重启valuation_v1/pages/paper_plan/financials（以实际清单核对），再核实首日行数/HTTP200/全部程序前后清单。代码交付、合并安装、真实运行仍分开，当前不记已完成。


## A-030 进行中：最终交付head CI已通过，T6隐私交付边界待答复

[PR124草稿](https://github.com/XuQingsong/inves-cog/pull/124)最终head `08656deb58687e47946e1a77cebeda515918cde3`，已核对Actions headSha完全一致，[phase1-blocking实际SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42085917940/job/127450844902)。代码head50891ad也实际通过1027 passed/204 deselected、CI自检2 passed；最终head不借用旧CI。交付分支工作区干净，18份证据/截图SHA256已逐个核验。逐项结果在ops/answers/A-030.md，完整边界/部署准备在handoff/A030/progress.md；45条Visa待补清单与首份仍缺失的原因都已推送。v18单独复核1 passed。

仍不标已完成：T6真实持仓页截图尚缺。已准备并查看明确标注“全部测试夹具，非实际持仓”的预览图，严重透支长期提示存在、下行风险计数仍0；不冒充真实生产图。用户的截图交付方式问题尚待答复（允许服务器端完全遮盖后用于PR验收，或不外传、采用夹具加服务器内检查）；未传出私有页面/持仓明细。真实自动审批拒绝的是完整响应导出、理由为可能包含私密仓位，公开字段服务器内预过滤替代已成功。

下一步/owner：用户只需答复上述隐私边界；A据答复完成T6并提交完整验收。需求方验收合并后A继续既已授权的迁移、EPS-only补缺、限定程序重启及真实运行核验。main仍625dd38bc4aa9559acdc07cb5d79ce806316fa1b且A运行，未合入/部署/执行迁移/写生产数据库；不重复启动回测或下载。自动接单保持原ACTIVE与原线程，不因本阶段交付暂停。


## A-030 进行中：用户已批准完全遮盖持仓截图（UD-A-57）

用户在本对话直接答复：“允许完全遮盖后的截图用于 PR 验收”。授权范围仅服务器端先遮盖证券名称、股数、成本、金额、仓位比例和交易明细，只保留页面结构与新增风险文案的截图用于PR；不允许原始私密页面或数据出服务器。A据此完成T6，不再等待同一答复。已准备公开个股截图、夹具预览、45条Visa待补清单与准确head CI；当前交付head08656deb58687e47946e1a77cebeda515918cde3，未部署/迁移/回填。先在项目隔离临时目录渲染分支预览并去除敏感文本/属性/脚本数据，再导出脱敏结果，实际核验后更新证据和最终CI；不改变线上服务或交易行为。


## A-030 进行中：UD-A-57已执行准备；新卡点为服务器认证后无响应

用户“允许完全遮盖后的截图用于PR验收”已记录并生效，不再等待截图授权。已保留先失败脱敏测试9d672fa，再实现服务器内渲染/遮盖脚本；代码head `bf88c454cd787edd6fca73e20e4cc2223b8491ea` 已推送PR124，PR仍OPEN/DRAFT且head已更新。纯A030离线21 passed、静态检查通过；该head当前无CI检查，不借用08656de旧成功，正在触发既有工作流。

服务器先只读探测发现已有google-chrome，无需安装。上传隔离预览包（仅分支renderer/样式/公开估值数据，约246KB）SSH超时；随后远端65秒锁定截图命令也无结果，不能把命令发出计为生成图片。只读核对临时锁/文件同样超时，实际远端产物未知。进一步一次18秒诊断确认TCP连接、SSH banner、认证和session打开均成功，随后命令无响应退出255；网页首页HEAD在4秒内未响应。一次18秒SFTP聚合load/mem/io读取失败，未取得指标。故原因尚未确认，不武断称磁盘满/IO/OOM，也不将用户授权当卡点。

未取得可导出的脱敏PNG，原始私密payload/HTML未返回本机，未改线上服务、数据库、角色、调度或运行回测。远端脚本设计55秒进程期限/22秒浏览器期限、外层timeout65和flock锁；恢复或重试前必须先核对本项目真实锁/进程/文件，不重复上传或并发启动。此前尝试状态未知，不说远端没有进程。

影响：T6真实持仓截图及最终验收未完成；新功能/EPS补缺仍未上线。需要服务器运维方通过云控制台核对并恢复远端命令响应（A无法通过已失去响应的SSH取得主机指标）；A继续CI与证据准备，恢复后只导出服务器端完全遮盖后的PNG及无私密字段的核验摘要。已直接在本对话说明问题、证据、已做准备和需要的运维操作，不重复索取UD-A-57许可。


## A-030 进行中：收到main紧急通知，禁止生产浏览器；清理尝试无响应

已读取main `22f87db67deb6fd89080a01ef8cae3884c28bec8` 的紧急通知。立即停止生产端截图方式；仅对本次临时路径匹配的Python/Chrome及子进程发出有界清理命令，外层timeout25，仅在本次flock锁释放后删除该目录。该SSH也超时退出255，没有清理结果，不能宣称进程已退出、目录已删或未产生作业。需要运维通过云控制台核对本次路径 `/tmp/inves-cog-a030-ud57-bf88c45`、`--user-data-dir=/tmp/inves-cog-a030-ud57-bf88c45/browser`、该目录render.py，以及 `/tmp/inves-cog-a030-ud57.lock`；仅清理本次预览，不全局杀Chrome或停业务服务。A没有扩大清理到其他进程/项目/数据库。

已在分支移除所有生产浏览器调用，改为服务器内先遮盖、只在127.0.0.1提供一次请求的脱敏预览（50秒期限/25秒等待），Mac经SSH隧道截图；原始持仓不发往Mac。遵守用户UD-A-57并落实需求方新约束，不再问同一授权。服务器未恢复前不启动新预览或反复SSH诊断，先核对并完成旧残留清理。

[PR124](https://github.com/XuQingsong/inves-cog/pull/124)新head `9ff69c6d601b5249b0318c319cca5705bc594412`，已将main紧急通知与既有逐项回报合入，唯一ops/answers/A-030.md冲突双方内容都保留。旧bf88c454cd787edd6fca73e20e4cc2223b8491ea的[CI实际SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42149825637/job/127670070319)，但生产浏览器方案已撤销，不能作新head最终CI；新head既有工作流正在触发。纯A03021 passed，静态检查通过；无PNG交付、未合入main、未迁移/部署/生产回填。

当前问题/owner：服务器认证后无命令响应及网页超时，具体资源根因未取得证据；运维通过云控制台恢复并协助核对本次预览残留。A继续最新CI并在恢复后负责T6；用户截图授权已解决，无需重复答复。已在本对话直接反馈新通知、清理未证实及新方式。


## A-030 阻塞：最新准确head全部CI通过，生产取证与清理待命令通道恢复

[PR124草稿](https://github.com/XuQingsong/inves-cog/pull/124)准确head `9ff69c6d601b5249b0318c319cca5705bc594412` 的[phase1-blocking实际SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42150701619/job/127672990495)已核对headSha一致；同次replay/cases也实际SUCCESS。已合入main22f87db紧急通知并移除生产浏览器调用，单机21项A030离线测试与静态检查通过。分支工作区干净；旧head结果不冒充本head。PR保持草稿，未合入main、未迁移/部署/生产EPS回填。

UD-A-57截图授权已解决，不再等待用户答复。实际剩余：服务器SSH认证/session成功后命令无响应，首页HEAD超时；仅针对本次隔离目录的有界停止/清理命令也超时，无法确认远端进程/目录状态，持仓脱敏PNG没有交付。尚未取得主机负载/IO/内存指标，根因未知。需要服务器运维通过云控制台恢复命令响应，并核对仅本次 `/tmp/inves-cog-a030-ud57-bf88c45`、对应browser目录与render.py、`/tmp/inves-cog-a030-ud57.lock` 的残留；不全局停Chrome或业务。A负责恢复后先证实旧作业清理，再按服务器先脱敏loopback预览+Mac隧道截图完成T6。此轮不再重复线上诊断或启动预览，不将本机SSH断开当作远端退出。

已在本对话直接告知新卡点与所需运维操作；其他已授权部分完成CI和PR同步，未用报告替代能够执行的工作。原A线自动接单持续开启，无新截图授权请求。


## A-030 进行中：继承新main内存修复，线上恢复仍待证实

本轮main更新到 `def6c08d8b118210d0149571ccfec2ef7222b0b6`（已合并PR125）。变更：交付分支继承main中M9 fin_state有限窗口、每日模块spawn子进程释放内存以及issuer_profiles较低并发的既有修复；不另改调度、来源或内存策略，不替需求方部署。保留A030解释-only行为与生产浏览器禁令，合入后重新核对准确head CI。仅主线代码已合并不证明生产已安装/恢复；最新A030答复尚无服务器恢复/本次预览清理确认，不启动远端任务或重复诊断。


## A-030 进行中：服务器命令响应已恢复，本次预览无残留

main内存修复合入后，本轮仅一次8秒轻量只读核对返回成功：responsive=true，旧临时目录 `/tmp/inves-cog-a030-ud57-bf88c45` 不存在，精确匹配的本次预览Python/Chrome进程0，原lock文件不存在；loadavg0.16/0.37/1.08。这证明当前无该次残留，不反推早先是否实际启动或由谁清理。服务器命令通道旧阻塞已解除；网站及持仓取证尚须实际完成，不能仅凭负载称全部业务恢复。

A不再等待运维或重复截图授权，立即按UD-A-57及main紧急约束继续：服务器先脱敏、仅127.0.0.1单请求有界预览，Mac经隧道截图；生产绝不运行浏览器。新预览使用独立08019e1前缀目录，原路径不复用，执行前检查存在性及锁，完成后核实清理。交付head `08019e1f4465ff3b0334c3d7adc9419846862663` 已无冲突继承main `def6c08d8b118210d0149571ccfec2ef7222b0b6`，相关36项本地返回通过，1个数据库用例因无Docker未执行，留准确head CI验证。未合并PR、未部署/迁移/生产回填。


## A-030 进行中：T6真实脱敏持仓截图已交付，服务器临时资源清理已证实

用户UD-A-57已完整落实，`handoff/A030/screenshots/account-redacted.png` 已推送PR124：真实11-04持仓结构，服务器先遮盖身份/数量/成本/金额/比例/交易文字/链接/属性/脚本及盈亏交易颜色，再经loopback SSH隧道由Mac截图；生产不启动浏览器，原始payload/HTML不出服务器。图片实际打开核验，1440×7000，SHA256=4d5f3c8801f338b9221afdfd291ad49daaa8139ba97ab160114a0a25372d9262，记录见account-redaction-verification.json。真实历史日早于校准，图中档位不适用，未伪造严重透支；另有明确测试夹具图覆盖长期严重透支提示且风险计数不增。Mac生成PNG后退出超时被20秒保护终止，预览真实退出0，不伪称浏览器正常退出。

最终只读核验：本次服务器预览进程0，临时目录/锁已删除，旧bf88c45目录亦不存在，证据a030-ud57-cleanup.json；生产当前head为 `def6c08d8b118210d0149571ccfec2ef7222b0b6`。此前命令响应/清理未证实卡点已解除，不再等待运维或截图授权。本轮未改线上服务/数据库、未部署A030或生产回填。

[PR124](https://github.com/XuQingsong/inves-cog/pull/124)最终证据head `1afdf27db8fcfbbff7cc71f28172b9569ad2adca` 已推送，含main内存修复及紧急禁令、颜色遮盖失败测试/实现历史、T1–T10回报，21份证据/截图SHA256逐个核验通过。本地A03022 passed；08019e1准确CI实际SUCCESS，但本head新增了颜色遮盖及最终证据，须核对自身CI，不借旧绿灯。正在跟到该head真实CI完成，随后转非草稿提交需求方验收，不自动合并。无待用户输入；合并后A继续原授权迁移、45条EPS幂等补缺、限定重启和真实运行核验。


## A-030 已完成（开发与离线验收交付）／已提交需求方验收，尚未合并部署

[PR124](https://github.com/XuQingsong/inves-cog/pull/124)已真实转为非草稿（OPEN、isDraft=false），head `1afdf27db8fcfbbff7cc71f28172b9569ad2adca`。该准确head的[phase1-blocking实际SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42162946446/job/127712680092)已核对headSha完全一致，同次replay/cases也实际SUCCESS。最新分支工作区干净，GitHub为MERGEABLE；已继承main def6c08内存修复和22f87db紧急禁令，保留#122/#123。最新main a51918c后续调度优化的两文件在本PR相对merge-base无变更，不回退main。本地A03022 passed、静态检查通过；Docker用例由真实CI验证，不计本地通过。首次PR ready请求TLS超时，先核对仍草稿后一次重试，已实际核验非草稿。

完整T1–T10回报在ops/answers/A-030.md，结果/限制/部署准备在handoff/A030/progress.md。manifest.json的21份证据/截图SHA256已逐个核验。T6生产持仓结构完全遮盖图account-redacted.png已实际查看，身份/数值/交易文字及颜色、链接/属性/脚本均遮盖，原始payload/HTML不出服务器；服务器仅loopback预览，浏览器在Mac，预览退出0。服务器本次进程0、临时目录和锁已删除，旧目录也不存在，证据a030-ud57-cleanup.json。生产当前读取head为def6c08，命令/持仓接口已恢复，本轮未替生产安装或改服务。旧服务器/清理/授权卡点均已解除，无待用户输入，不再重复请求UD-A-57。

T3真实11-04的59只逐项输出与5只手算已提交；KO不在池且生产无fin_state，用已有Mac财报+生产同日价格单独手算，混合来源明确；历史日早于校准、缺当日层级均明示，不伪造当时档位。T7真实10-30已发布计划只改2处理由，其余字段完全一致，原持仓/订单未导出。T8最终45条Visa EPS-only补缺清单：47状态EPS非空1→46，层级70→2203/2223交易日为Mac离线试算，首份前序不足仍缺、原非空不覆盖；GOOGL/META公司EPS存在，BRK.B不在池，不扩池。历史下载/回测不重复启动。

阶段边界：本条“已完成”只指开发及验收提交，不是需求方验收通过、main已合入或线上功能完成。T1真正进main、T8生产回填及T10首日真实运行均在需求方验收合并后，由A继续原授权唯一迁移、45条幂等补缺、限定程序重启、全部程序前后对照、ceiling首日行数/HTTP200/实际EPS覆盖核验。A没有自动合并PR、迁移、部署、生产财务写入或模型调用。需求方负责验收/合并并关单，A持续接收答复并完成后续授权阶段；原a-github保持ACTIVE原线程，不因本阶段交付暂停。


## A-030 进行中（部署接单）／A-031 已收到

用户要求查看最新任务，本轮fetch核对main `1377557c43aed5656e6d8acdfb285e9338a38665`：A030已由需求方验收、PR124合并 `5622d2b3b2c1ef6e1307f925ac3a258375228f99`，开发已关单；部署授权在ops/answers/A-030.md，当前已明确进入可部署阶段，不再等待同一合并或用户许可。原交付head `1afdf27db8fcfbbff7cc71f28172b9569ad2adca` 的[准确CI SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42162946446/job/127712680092)沿用，不重复本地回测或生成账户。

部署优先：先核对远端真实head/工作区、已有job/迁移/回填前缀、全部程序/PID及inves-cog-data/monitor/alerts.log；唯一迁移phase1_m5_0003_ceiling_daily.sql，V45条先备份、仅既有非管理员ingest业务角色幂等补缺，仅重启valuation_v1/pages/paper_plan/financials，禁止supervisorctl update及生产浏览器。过程出现新告警即暂停，不把命令发出、程序存活计为成功。需求方补充真实故障原因为claudeuser slice内存上限，用户已提高至7G，PR125/126已降内存；本轮不擅自改资源上限。

A031已收到（ops/inbox/A/A-031.md及T1–T9）：R1历史标普500透支否决风险/三组合12滚动起点；R2基本面或fear≥3才触发的破位v2/v2b与28起点评估；R3规则A漏选逐门诊断及单门放宽全池对照，只报数据、观察，不提或上线规则修改。TSM按既有合规SEC User-Agent限速有界重试，失败保留缺口。全部Mac inves_cog_bt/本项目目录，最多4工作进程，代码仅backtest/scripts/tests/handoff/A031，新开关默认关闭。部署为独立运维与本单并行且优先；A031结果尚未运行，不把已收到说成已完成。无待用户输入，A负责执行与核验，需求方负责最终研究判断和验收。

## A-030 已完成（合并安装、EPS回填及首日真实运行核验） 2026-11-06

生产安装 main `1377557c43aed5656e6d8acdfb285e9338a38665`，包含已验收 PR124 merge `5622d2b3b2c1ef6e1307f925ac3a258375228f99` 与准确交付head `1afdf27db8fcfbbff7cc71f28172b9569ad2adca`；该head [phase1-blocking SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42162946446/job/127712680092)。没有新代码改动，不借新main声称重新CI。生产原先detached HEAD，守卫在数据库写入前停止；核对已跟踪文件无修改后切回既有main并fast-forward，未覆盖未跟踪运维记录。仅执行批准的phase1_m5_0003_ceiling_daily.sql，未执行其他迁移、supervisorctl update、生产浏览器、模型或回测。

真实结果：服务器内先备份V原47状态，备份 `/home/claudeuser/inves-cog-data/deploy/a030-20261106/v-eps-before.json` 权限受umask077保护，SHA256 `0daff60277326ac8eb72cec4f8390444d813d6135a0914a8b5ddeee7728e8aeb`；既有非管理员inves_cog_ingest业务登录实际updated45/already_present0/missing_state0。EPS非空1→46/47；同一真实历史2018-01-01至2026-11-04共2223交易日，score_history只读核算层级70→2203天。首份前序不足仍缺，原非空保留。未将历史补缺伪称历史当时已可见。该层级核算单票内存函数，无生产交易回测或模型调用。

仅重启 valuation_v1/pages/paper_plan/financials，全部22程序前后清单保存在同目录 services-before.json、services-after.json。逐项核对：anomaly_daily63473→63473；attribution_labels1624→1624；attribution_tracks1625→1625；consensus_snapshots1626→1626；daily_modules63440→63440；embedding原EXITED仍EXITED；financials1629→110513；flows1630→1630；iex_snapshots1631→1631；live_perception1635→1635；m9 45421→45421；macro_snapshots1640→1640；morning_page1641→1641；news_translate1642→1642；pages1644→110392；paper_plan63530→110436；review1646→1646；scheduler1650→1650；stock_snapshots1664→1664；valuation_v1 63489→110380；watchdog1666→1666；wide_snapshots1667→1667。除原embedding外均RUNNING，不将原EXITED称全部健康；未改变范围外进程。

首日真实业务估值使用既有valuation业务角色完成，数据库独立复查ceiling_daily在2026-11-05实际59行。首页、/account、/barometer?static 独立HTTP检查均200，不输出页面或持仓内容。全过程监控alerts.log inode1179927/306bytes，独立终检仍306bytes，无新增告警。迁移、回填、四程序重启、真实估值均只执行一次；最后打印完成摘要时date JSON编码失败，但completed.json已保存，随后独立只读核验表行数/EPS/HTTP/服务清单，不重复运行。完成时间2026-11-06 05:43:29 UTC；服务器completed.json、eps-result.json、valuation-result.json、progress.json与备份保留供需求方复核。

自动审批曾拒绝原始alerts日志末尾导出（可能敏感运行信息）；已改为服务器内检查inode/字节变化，未导出日志原文，不绕过拒绝，无需新增用户授权。没有新增权限、数据来源、服务或调度变更。已自行决定：以已知历史窗口复核同口径层级，首日仅运行既有估值计算，不触发纸面执行或补跑其他业务。

下一步：需求方负责上线走查/最终验收；A继续已收到A031 Mac本地研究，生产部署已收口，不再重复迁移、回填、账户生成或首日计算。A031尚无结果，不冒称已完成。原a-github持续开启。

## A-031 进行中：R2默认关闭基线已核验，研究批次运行中

已复用干净开发目录 `/private/tmp/inves-cog-a030`，基于main1377557建立并推送 `phase2/a031-research`，当前head `6d0bb8d4f379af36ed7f87e0c29730cdd5cd4c0c`。先失败测试提交a204bb5（实际4 failed/4 passed），再实现c530b95：新增仅backtest可选breakdown_v2/v2b，基本面或fear≥3才允许M55，市场单独触发v2b卖1/3，去掉技术后备；入场记录entry_books并统一研究runner/fear输入选择。A029+A031专项26 passed，ruff通过。当前无PR和该head CI，未称交付完成。

Mac本地只读库inves_cog_bt真实默认关闭复跑已返回481笔，trade_hash `f56ffe611b7c029a8e55a59936fdb298b9ce902377c8a74ff39428d0e4a7e767`，与A029完整基线完全一致。已保存handoff/A031/evidence/r2/base.json。R2同一批次真实进程PID87400（执行session65656），命令scripts/run_a031_r2.py，1800秒总期限、最多4worker；progress.json阶段base，输入准备及基线177.64秒。后续F2/v2/v2b、信号及28起点仍运行，不能以进程存活当研究结果。下一轮先核对该PID、progress和已保存前缀，不重复启动；同一诊断预算不重置。没有生产连接、模型或线上规则变更。R1/R3/TSM仍待完成，尚未得出策略结论。

下一步由A继续三个研究部分并形成完整T1–T9报告，需求方据数据作规则设计。部署A030已在上条核验完成，不因研究任务重复执行。无待用户决定，原自动化不变。

## A-031 按需求方通知暂停／A-032 已收到 2026-11-06

刚读取新main `77d74f56af9315c031a4d97ed19312ca17798562`：ops/answers/A-031.md明确暂停本单，A032优先。已立即向本轮Mac研究session65656发送中断，实际返回exit130/KeyboardInterrupt，发生在四版本逐次研究、尚未建立rolling进程池；未继续启动研究。已完成代码分支head6d0bb8d及默认基线base.json保留，不丢弃、不伪称A031完成。默认trade_hash与A029完整一致；test_v18_replay亦实际1 passed。任务级暂停不暂停原a-github，也不是重新等待用户恢复A线。

A032已收到：长期数据守护机制，覆盖缺失/陈旧/异常检测、串行有界补采、下游重算、中文合并告警/结论/08:30北京时间日报邮件、页面数据状态及影响提示。变更（任务明确授权，先记录后实现）：新增dataguard包、配置期望清单、新缺口/状态审计表迁移、新supervisor data_guard程序、web数据状态展示与现有补采入口调用；不改各采集业务逻辑、不安装未合并版本。SMTP只读服务器环境变量，无配置时正常检测并明确邮件未配置，不写凭据；首次上线默认只检测，至少1天后由需求方决定补数开关，不自行开启。当前一次性补数由另行运维负责，A不重复执行；已完成A030部署不重跑。

下一步A核实既有调度、实际表和日期索引，先写真实形态失败测试再实现，离线注入时间/假SMTP；生产只读取证需有界且不导出敏感日志/持仓。暂不创建表、安装服务、外发邮件或重跑生产业务。开发完成后交准确head CI和PR供需求方验收，合并后才执行授权部署。无待用户输入。

## A-031 继续／A-032 暂不开工（最新需求方通知覆盖）

又读取main `1fa0016afefed8f02fdebe079118e292458eee74` 的ops/answers/A-031.md通知二及A032通知：用户决定逐个开发，先完成并验收A031，再开始A032；覆盖前条暂停优先级。按最新通知继续A031，不索取重复恢复确认。A032仅已读/已收到及边界记录，未实现、未迁移、未装服务或发邮件；邮件Gmail STARTTLS口径保留待该单生效。

原A031 PID87400已独立ps确认不存在，保存的base与F2结果已推送分支提交 `634acc8`。当前研究head `6ac0f9b`（完整SHA下次以git核对），续跑入口跳过已有base/F2文件，保留中断历史；执行session35632，仅Mac本地inves_cog_bt。原1800秒批次已用部分预算，恢复收缩至1200秒，不无限重置；新增到期终止所有本批worker的清理。当前只恢复缺失v2/v2b与信号/rolling结果，尚未把运行中当完成。默认关闭基线hash已完全一致，v18实际1 passed，专项26 passed；最终准确head CI仍待完整交付后。下一轮先核对现有进程与progress再继续，避免重复开跑。

## A-031 进行中：UD-A-58 已获授权，修正成员期间；R2/R3真实计算完成

用户刚在本对话直接答复“允许用标普官方公告修正（建议）”。用户决策UD-A-58：仅为A031本地研究引入免费的标普官方成员变更公告，重建核对加入/退出期间；不接入生产、不付费、不扩为其他来源。变更：研究输入成员期间来源增加标普官方公告，先记录本条再按授权执行；不再等待同一来源批准。

R1指定面板已核实有成员日期错误：ABMD首行2018-01-05，标普入选2018-05-31；SIVB首行2018-01-05，标普入选2018-03-19。原生成代码只限制已退出公司的退出日、未限制加入日；原期间元数据不在Mac。本轮初步37.95秒/292477风险观察/36组合仅provisional，不称T2通过。证据handoff/A031/evidence/r1-source-audit.json；已准备计算框架、完整数值和覆盖审计，A负责按UD58修正全体期间后重算，不只修两个反例。

R2原批次超时后先优化历史重复排序，R3实际复跑基线hash与A029完全一致，才执行新方案；新的rolling-only计算实际303.54秒完成全部112检查点（28起点×base/F2/v2/v2b），4worker，进程session43809待终检。四版本和信号未重复跑。不是无限重置同一诊断预算；实际计算数据完整，尚需汇总验收。R3全池逐日卡点、首次通过/买入、4道单门p60对照实际159.58秒完成。专项32 passed，v18先前实际1 passed。研究分支当前898bab4（后续交付完整head/准确CI另核对），无PR/CI最终交付，未称整单完成。

TSM使用既有含邮箱SEC UA：两索引200，CompanyFacts200但季度EPS行0；2026-10-15官方盈利附件成功提取EPS(NT$)29.43（2026Q3），对照2025Q3为17.44、2026Q2为27.25；证据tsm-quarter-filing.json，未当成USD ADR EPS或生产修复。现有本地最新财务行期间回落2024年/annual_basis及stale_fundamentals问题保留，研究层级历史据真实输入披露。未改生产/规则/模型调用。A032仍暂不开工，A031验收关单后再做。

## A-031 进行中：PR131完整研究已推送，准确head CI正在核对

[PR131](https://github.com/XuQingsong/inves-cog/pull/131)草稿OPEN，完整head `f59c55c10b37c3382ae421fd0c3c766333c32905`。已无冲突继承main `8766daa`；相对main仅backtest/scripts/tests/handoff/A031和本单answers，未修改线上规则或B线代码。该准确head [phase1-blocking运行中](https://github.com/XuQingsong/inves-cog/actions/runs/42198314310/job/127827049137)，同次cases已SUCCESS，replay运行中；不借fe667be已成功的旧CI。本地tests/backtest+v18实际42 passed/9.60秒，ruff全变更通过，manifest147份文件逐个SHA256核验0差异。尚未标整单完成或验收通过。

UD-A-58已执行收口：正式批次144次HTTP、121份标普官方公告，缓存后所有重解析0网络。现代/旧式表、日期缩写、跨行单元格、公司简称与股票代码绑定均保留先失败测试后实现；326条去重事件，原提前纳入等错误修正后最终287515个个股窗口观察、36组合，R1真实33.74秒。未把只修两个反例当全期完成；121公告均有来源哈希，9份无成员事件/TBA/重复实施通知逐项说明，Fox新旧发行人明确区分。原过期大体积试算及下载缓存均已清理，仅保留结果、来源事实和代码。

R1仍有真实输入覆盖局限：部分已退出公司缺价格/财务资料；41个缺口代码逐项本地可用性审计（本地688份CompanyFacts元数据也已核对），不虚构缺失公司、不把有价格但亏损导致m不可定义误称全部财务缺失。报告明示可观测样本仍有选择偏差，不能宣称“全体历史标普完整无偏”已满足。原初始周面板仅2018-01-05起，1月组实际首建仓2018-01-08、之前现金；股息及真实退市兑付未伪造。T2覆盖、T3完整数值均已交，限制交需求方按原清单验收，不擅自降低标准或外推结论。

R2真实28起点112检查点已完整；v2相对base收益差中位数+8.74pp、胜出57.1%，最大回撤差中位数−1.48pp（即回撤更大）；v2b+7.09pp/53.6%/−1.41pp，F2−0.47pp/46.4%/+0.22pp，只报告数据不作规则取舍。M55全部sell_frac路径实际核对，市场独立触发v2b仅1/3。全期fear覆盖2220/2220，输入严格PIT。R3实际完成四门对照及13只诊断股逐日数据；TSM/ARM被既有FOREIGN资格规则挡住，与财报缺失分开。TSM本地2018–2026共2220日、6日有层级、0可交易；官方季度EPS为普通股新台币，不当作USD ADR，不声称EPS或网络恢复即规则放行。

T1–T9逐项答复已在PR。现阶段A跟到本准确head真实CI并提交需求方验收；无新生产/模型/付费来源/权限/外发决定，原自动化不变。A032在A031验收关单后开始；A030不重复部署。

## A-031 进行中（研究已交付验收；R1完整无偏验证仍有输入覆盖限制）

[PR131](https://github.com/XuQingsong/inves-cog/pull/131)最终head `f59c55c10b37c3382ae421fd0c3c766333c32905` 的[准确phase1-blocking实际SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42198314310/job/127827049137)已核对headSha完全一致；同次[replay SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42198314310/job/127827049259)、[cases SUCCESS](https://github.com/XuQingsong/inves-cog/actions/runs/42198314310/job/127827048801)。不是先前fe667be结果。代码/完整数值/T1–T9答复/147文件manifest均已推送，清理逐路径已证实。当前无运行中的A031计算或下载，无需重启已完成批次。

阶段结论：可用输入的R1/R2/R3研究和代码交付已完成；PR提交需求方正式审阅，不自动合并或部署。**不标整单全部标准通过**：R1已消除已识别成员日期错误，但历史退出公司价格/财务覆盖仍不足，无法证明全体历史标普无偏；原始缺失、亏损导致m不适用与资格限制分别披露。T2覆盖与各年缺失清单、41代码输入可用性审计完整可审阅；需求方需按原清单判断这些局限是否影响验收及后续补数范围，A不自行降低标准、伪造数据或扩大新来源/预算。用户UD-A-58已完整执行，不再索取同一授权。

A继续接收验收答复并落实范围明确的修正；A032严格等A031验收关单，不因出现新编号提前开工。A030部署已完成不重复执行。原a-github保持ACTIVE/每10分钟/原线程，不因交付或等待验收暂停。无新的用户权限/预算操作要求。
