# M2 自测报告

基线：main c52fcc0，M2 v8；2026-10-15。已按用户新授权合入M1最终共享代码，第二轮六项完成。当前59行健康及59份档案已刷新，53只美国公司可打分，LITE因真实GAAP大额亏损命中新门禁，不再带异常质量分进入交易；五只外国申报人按规则不可交易。PR #4请求验收，最新完整SHA的CI结果在PR说明核对。

## 1. 工程与回放

联合阻塞测试39 passed，10.38秒；独立replay 1 passed，5.93秒，零跳过，唯一最终证据为blocking.xml、replay.xml。90组Muse对照、2,255字段仍零差异，输入与oracle哈希不变；未导入或运行Muse/stock-pm代码。M0网络、时钟、模型、golden、权限门禁均保留，测试只用夹具及录音。干净Docker CI以GitHub最新SHA为准，本机pytest不冒称容器结果。

先失败测试再实现：d9867f6覆盖第二轮规则，964f7b7扩充COST财政季度与V维度边界；实现4a089cb。除两个既有复杂函数extract_state、parse_segments外没有新增复杂度豁免；本PR全部改动Python文件通过Ruff整理。共享pending各保留本模块行、CHANGELOG和fixtures MANIFEST取并集，依赖及锁文件已合并。真实milestones及docs不改。

## 2. 不变量

I10标签优先级、I11累计推单季、I12三天原件回退、I33分部轴/抵销/合计、I34 PIT一致预期窗口均有正反断言。D9可独立关闭；class A只放行V的精确FASB轴/成员，B类、其他公司、仿造namespace与混合维度仍拒绝。fixed放行80–120天；legacy长度及默认修复开关不变。

## 3. 逐条验收

| 条款 | 自评 | 唯一最终证据 |
|---|---|---|
| AC-M2-01 | 本地39项阻塞、1项回放通过，最新干净CI见PR | blocking.xml、replay.xml、legacy-replay.json |
| AC-M2-02 | 59只两套提取差异；BE/COHR/COST/LRCX/JPM/V/XOM可打分；LITE原值已核实并按Q-M2-27阻止打分 | differences.json.gz、d9-impact.json |
| AC-M2-03 | 59行健康；53只可打分，LITE命中implausible_value，不可打分无原因0、可交易缺核心0；earnings_event_missing从49降到5 | health.json、earnings-audit.json |
| AC-M2-04 | 51/54分部覆盖=94.44%；已采分部合计差异均≤1%，缺NOW/XOM/CRWD逐只登记 | coverage.json、segment-original-audit.json.gz |
| AC-M2-05 | AMD/WDC/NVDA/MSFT/COHR与真实10-Q原文逐元素一致 | segment-spot.json |
| AC-M2-06 | Muse历史导入幂等、5只×3日期F2历史窗口复算通过；真实采集失败及迟到均如实保留 | database-verification.json、f2-history.json、consensus-collection.json |
| AC-M2-06b，非阻塞 | 一次真实59/59成功入库、失败0；尚需第二次完整采集，期限M5验收前 | consensus-collection.json |
| AC-M2-07 | 59份真实F3档案更新，财报/分部/一致预期均有内容或明确原因 | profiles.json.gz |
| AC-M2-08，非阻塞 | 审核队列接口/录音测试通过；真实映射草稿仍未完成 | 原名test_segment_mapping_pending；backlog.md |

## 4. 第二轮六项结果（后续变更见第7节）

1. M1共享件合并完成；不自建同名表或第二个SEC/LLM客户端。M1合并main后再同步main。
2. q4_missing只针对最近八季及打分字段，辅助成本字段和历史久远缺口不误伤。仍保留全部诊断；D4能实际补出的毛利不再误判缺失。
3. fixed采用80–120天；COST的12周常规季、16周第四季及168/252天累计现金流按实际营收财政日历对齐，不用自然月猜季度。90组legacy回放零差异。
4. D9：JPM采用RevenuesNetOfInterestExpense；V从十份财报实例取精确A类EPS；XOM当前CIK2115436的序列仅两季，用共享SEC读取前身CIK34088补历史，保留原filed及来源，配置和影响矩阵在m2.yaml。三只关闭/打开D9的逐字段差异见d9-impact.json。
5. 官方索引Accepted新核实44只，持久化到M1既有表；原10只有效，剩ARM/ASML/NOK/SKHY/TSM的submissions均无Item 2.02 8-K，各自申报数量与原因附证。健康页、档案均重跑，不伪造反应日。
6. Yahoo接口429后同源网页解析嵌入JSON，页间隔≥5秒，source=yahoo_page，F2与yfinance同优先级。真实59只全成功；首次尝试因未应用新source约束迁移而入库失败，原记录保留。修复迁移后再实际联网采59只，不把缓存回写算第二次采集。成功运行晚于北京10:30，status=degraded、deadline_met=false保留。

## 5. 真实数据与夹具的边界

current-financial-audit.json.gz是本项目此前捕获SEC输入、标明新增D9取数及原件缓存的重算，不算一次新的59只完整联网财报采集。NOK原件0001104659-26-105772、TSM原件0001046179-26-000680没有可唯一识别实例，保留D3_failure和companyfacts_lag，未用零/前值掩盖；外国申报规则继续生效。

金额换算仍使用现有FRED/ALFRED历史可见版本；期末最多向前七个自然日且记录实际报价日，缺口抛FXGap。原ASML历史起点缺口已补2006年起数据并留证，不用NULL掩盖。

## 6. 未完成项

非阻塞：第二次59只真实一致预期采集（M5验收前）、真实分部映射草稿。Yahoo页上外国公司的预测金额沿用供应商原始口径，付费/新源/代理均未引入；原始响应留在raw，观察用途不冒充统一美元估值输入，后续M5接入前核对单位。

当前无待用户答复的阻塞问题。M1已在main有条件验收，M2最新CI绿后转正式提交验收，未获M2验收前不合并PR #4。每个AC只留一份最终文件，旧-v3/-k16证据留在Git历史。


## 7. 第三轮重新提交验收

任务卡T01-T02-round3的第1–5项已完成核实、修复及重算。先红测试afd805a、8049913、7a29762，实现19e61ec、dd032d8；未改legacy，90组对照仍零差异。

### LITE：原件推翻了“数值算错”的假设

重新下载SEC 2026财年10-K，主报表无维度context c-1明确为2025-06-29至2026-06-27：营收3,014百万美元、净亏损6,935.1百万美元、稀释EPS−92.96。新鲜companyfacts与原件完全一致。10-K披露债务终止损失7,756.6百万美元。这是真实GAAP损失，不能替换成调整后盈利或删掉亏损来满足原“可打分”预期。

按本轮Q-M2-27，保留原值，命中规则1及规则3，can_score=false、can_trade=false；理由附推算第四季及另外三季。新的阻止打分条文优先于原AC-M2-02中LITE“可打分”的旧预期，需需求方依据原件复核。URL、context、sha256与金额均见round3-source-audit.json，测试冻结了实际负数，未改golden。

### CRWD：拆股与重述口径混用

原件披露2026-07-01实施4拆1。公司facts同时保留旧口径EPS和新报表已重述的比较EPS，直接相加使符号错误。fixed只按当时已可见的拆股事实统一每股口径；legacy不动。

另发现旧九个月累计数压过后来重述的Q1/Q2，第四季推算把旧口径带回TTM。现当单季披露晚于累计数时，以较新的前三季推Q4，并记录实际使用的输入与最晚可见日。CRWD净利润由58.460百万修为44.995百万美元；独立验证：年报−162.502百万+本期半年33.080百万−同期半年−174.417百万=44.995百万。TTM EPS约+0.05，Q4 EPS仍按既定近似推算标记，不冒称全年EPS严格可加。完整原件与拆股证据见round3-source-audit.json。

### V、合理性门禁与59只

V按m2.yaml登记多类别股，fixed/D9使用最近季度稀释加权股本1,898百万股，来源标multi_class_diluted；EPS×shares/ni_ttm=0.987141466，legacy仍保留原A类流通股口径。正例放行该字段，其他类别、发行人及D9关闭均不误用。

新增implausible_value，只在fixed检查三条要求，含1及0.5/2边界、1,000万美元豁免、推算季度符号/支配性正反用例。59只已重算，53只美国公司可打分；只有LITE命中该新码，仍可打分但违反独立比值检查的行数0。BE使用最新10-Q/A核对，未退回未修订报表。差异、健康页、档案各保留唯一最终文件；逐条审计见plausibility-audit.json。

第5项pending原因已改为等待59只完整财报实源冒烟及新门禁核验，明确Yahoo已接通，不再说等代理或Alpha Vantage。缓存重算如实登记job_runs，不充作新的全量联网采集。

### 非阻塞AC-M2-09与M1收尾

第6–9项正在独立处理，期限M5验收前，不伪称已完成：NOK已定位为Revenue标签2017后改用RevenueFromContractsWithCustomers；TSM新20-F有2025事实但companyfacts缺失，需原件回退；四家季度6-K及TSM月度公告目录已定位，后续以固定规则入新表，不调用LLM。新迁移将使用未占用模块序号。

M1现有实源测试尚缺SEC/SECDailyIndex健康记录，正式窗口20:45–21:15 ET之前不会伪造状态或提前删pending。常驻任务选择已补齐，接电防休眠断言生效；明早实际job_runs和最终live结果仍需授权的08:50自动核对后补证。只读账号已创建、可读且无表写权限，按需连接信息私下交付，不入仓库。
