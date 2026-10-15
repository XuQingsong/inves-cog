# M2 需求答复与已验证的新规则问题

基线main d273b28，M2 v5。K15/Q-M2-18、K16/Q-M2-19均已写入需求并完成。历史 K13 已写 Q-M2-16，M0 修复仅在 M1；K14 按 Q-M2-17 使用 FRED 七日余额报价和原币证据，实源 ASML 旧期间已补足。K15 于本线程获准仅允许 srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember，测试先行实施，其他混合维度继续拒绝。

## K16：同轴汇总、利润专用抵销与其他经营分部辅助成员

位置：Q-M2-11 / FR-M2-10。提问时51/54的分部存在覆盖满足90%，但14家营收合计未达标。真实逐行数字见 segments.json.gz、coverage.json；没有用合计反推数字或削弱阈值。

已核实原件事实：

1. NVDA 0001045810-26-000075：ComputeAndNetworking + Graphics = 96,221,000,000，与合并营收一致。CorporateNonSegmentMember 仅有利润，没有营收；它的 revenue 仍为 NULL。现行将这条 NULL 一起送进营收容差门禁，产生 mismatch。是否把原件明确为利润专用的行排除于营收加总，同时保留该行和 NULL/原因，区别于确有营收元素但 nil 的未知金额？
2. UNH 的同一 StatementBusinessSegmentsAxis 同时有 OptumHealth/Insight/Rx 和 TotalOptum 汇总成员；全平铺合计为合并营收 158.6109%。CAT 同轴也存在 ReportableSegmentAggregationBeforeOtherOperatingSegmentMember 汇总项。文档只限定 axis，未明确成员层级及加减权重。建议读取同一申报原件的 definition/calculation 与分部表证据，区分实际分部、汇总项和抵销权重；不按名称猜测、不通过试组合凑 1%。
3. GEV 0001996810-26-000148：PowerSegmentMember 原营收 5,477,000,000，主业务轴外另有 srt:ConsolidationItemsAxis=gev:OperatingSegmentsExcludingIntersegmentEliminationMember，未含 SubsegmentsAxis 的汇总 context 为 c-378。这是另一种未获准的辅助成员，当前严格门禁正确拒绝，不能直接套用 K15。是否允许仅将这个已验证的 GEV 辅助成员加白名单？带 SubsegmentsAxis 的三维 context 仍拒绝。

官方原件目录：https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/ 与 https://www.sec.gov/Archives/edgar/data/1996810/000199681026000148/ 。其他申报号逐家记录在分部证据中；原件缓存保留在提交范围之外。

用户答复（本线程）：采用上述原件规则并继续修复。已测试先行完成K16；59只原件重新核验，14家营收合计异常降至0。原件逐行权重、汇总关系、表格区块/列及哈希见segment-original-audit.json.gz。营收NULL保留，不填0；GEV放行严格限定ticker、namespace和成员。


Q-M2-20：Yahoo部署出口封禁已由需求方确认。AC-M2-06b非阻塞，期限为M5提交验收前；等待用户选择代理或Alpha Vantage，当前不重试、不换源。

## 第二轮已自行决定（任务书§4.6）

- 用户已允许M2立即合入M1，不再等待main合并后才开发。第二轮六项均完成；工程冲突按已批准并集规则处理。
- COST采用营收已存在的实际财政日历定位前三季和YTD结束日，解决12/16周及168/252天累计现金流；不改legacy默认行为和Muse冻结答案。
- XOM先核实当前/前身SEC事实，D9按m2.yaml明确前身CIK，仅固定版合并并保留原filed；V的A类维度精确限定，D9关闭时该补充事实不能绕由D3泄入。
- 财报事件逐只检查M1共享表，再用同一个SEC客户端核对官方索引，缺失49降为5；剩余为无Item 2.02的外国申报人，原因及计数见earnings-audit.json。
- 首次Yahoo采集解析成功但新source数据库约束尚未迁移，失败记录保留；应用迁移后重新真实采集59只全成功。没有以旧缓存充第二次采集。
- 外国Yahoo预测币种/ADR单位在M5估值使用前核对，raw保留供应商口径；当前只观察，不把原币预测冒充统一美元估值输入。


## 第三轮已自行决定（§4.6，已验证原件）

- LITE的−69.351亿净利润及−92.96 EPS与最新10-K及新鲜facts一致，原件披露77.566亿债务终止损失。保留GAAP原值，以新Q-M2-27规则阻止打分，不以调整后盈利冒充原报表。证据及旧验收预期冲突见self-test第7节，请需求方复核。
- CRWD同时存在4拆1前后每股口径、较新单季重述与旧累计口径；fixed统一可见拆股口径，并在单季更晚时重算累计推导。独立年报加减半年核算净利润44.995百万、EPS约0.05；legacy不变。
- V只在登记的多类别发行人及D9开启时用最新季度加权稀释股数，缺失时不冒用A类流通股。
- 数值门禁保留异常原值及各季明细，只改变固定版健康状态，不篡改历史或golden。
- 新迁移使用模块下未占用序号，历史重复编号不回改。
