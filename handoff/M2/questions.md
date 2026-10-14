# M2 需求答复与已验证的新规则问题

基线 main e7db5a9，M2 v3。历史 K13 已写 Q-M2-16，M0 修复仅在 M1；K14 按 Q-M2-17 使用 FRED 七日余额报价和原币证据，实源 ASML 旧期间已补足。K15 于本线程获准仅允许 srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember，测试先行实施，其他混合维度继续拒绝。

## K16：同轴汇总、利润专用抵销与其他经营分部辅助成员

位置：Q-M2-11 / FR-M2-10。提问时51/54的分部存在覆盖满足90%，但14家营收合计未达标。真实逐行数字见 v3-segments.json.gz、v3-coverage.json；没有用合计反推数字或削弱阈值。

已核实原件事实：

1. NVDA 0001045810-26-000075：ComputeAndNetworking + Graphics = 96,221,000,000，与合并营收一致。CorporateNonSegmentMember 仅有利润，没有营收；它的 revenue 仍为 NULL。现行将这条 NULL 一起送进营收容差门禁，产生 mismatch。是否把原件明确为利润专用的行排除于营收加总，同时保留该行和 NULL/原因，区别于确有营收元素但 nil 的未知金额？
2. UNH 的同一 StatementBusinessSegmentsAxis 同时有 OptumHealth/Insight/Rx 和 TotalOptum 汇总成员；全平铺合计为合并营收 158.6109%。CAT 同轴也存在 ReportableSegmentAggregationBeforeOtherOperatingSegmentMember 汇总项。文档只限定 axis，未明确成员层级及加减权重。建议读取同一申报原件的 definition/calculation 与分部表证据，区分实际分部、汇总项和抵销权重；不按名称猜测、不通过试组合凑 1%。
3. GEV 0001996810-26-000148：PowerSegmentMember 原营收 5,477,000,000，主业务轴外另有 srt:ConsolidationItemsAxis=gev:OperatingSegmentsExcludingIntersegmentEliminationMember，未含 SubsegmentsAxis 的汇总 context 为 c-378。这是另一种未获准的辅助成员，当前严格门禁正确拒绝，不能直接套用 K15。是否允许仅将这个已验证的 GEV 辅助成员加白名单？带 SubsegmentsAxis 的三维 context 仍拒绝。

官方原件目录：https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/ 与 https://www.sec.gov/Archives/edgar/data/1996810/000199681026000148/ 。其他申报号逐家记录在分部证据中；原件缓存保留在提交范围之外。

用户答复（本线程）：采用上述原件规则并继续修复。已测试先行完成K16；59只原件重新核验，14家营收合计异常降至0。原件逐行权重、汇总关系、表格区块/列及哈希见k16-original-audit.json.gz。营收NULL保留，不填0；GEV放行严格限定ticker、namespace和成员。
