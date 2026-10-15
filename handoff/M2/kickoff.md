# M2 开工复述单

模块：M2 财报与基本面档案　文档版本：v1　复述人：开发者　日期：2026-10-13

任务卡：`docs/tasks/phase1/T02-M2-fundamentals.md`。分支：`phase1/m2-fundamentals`。
基线：M0 v3 合并提交 `e478fe6bd0960a08b296f757cf7cfcc6a6d20bfb`，并同步 main `56a2ab69f14b7ad33d662a0b01cd9b5641a2037c` 的 README R7 说明。本 PR **只提交本复述单**；不开始实现、测试、夹具、依赖、导入或连接任何外部数据库，等需求方答复后再进入开发。

已读整体需求、第一阶段任务书、任务卡、README §3–4/§7.1、M2 v1 全文、规格 §4.4–4.6、4.8、9.2。通过 `load_golden('m2_fundamentals.json')` 核对已发布标准答案。Muse 仅以固定提交 `aacea04e4562f70854d69330fe724aa2799f2858` 的源代码作只读参照，详见第 7 节，未执行、导入或拷贝进本项目。

## 1. 我理解要做的事

| FR | 本模块的行为 |
|---|---|
| FR-M2-01 | 在 inves_cog.ingest.fundamentals 内重写 legacy，按同一冻结 companyfacts 和截止日期逐字段复现 Muse 的取数；不实现四本账或把 Muse 代码作为依赖 |
| FR-M2-02 | fixed 在 legacy 基础上逐项开 D1新营收标签、D2第四季推算、D3滞后实例解析、D4毛利推算、D5净利润兜底；五项开关独立、来源可追溯 |
| FR-M2-03 | D2任一前季缺失，Q4=NULL、q4_missing；不把缺季当0，不用跨财年季度凑齐 |
| FR-M2-04 | 按当时可见状态给 stale_fundamentals（>180天）、revenue_tag_gap、companyfacts_lag 等健康码，不把旧财报伪称最新 |
| FR-M2-05 | SIC 4911/4931/4991 标 industry_basis_na，单独这个码不拒绝打分；不能掩盖真正的采集缺失 |
| FR-M2-06 | 计算本期TTM自由现金流率减一年前TTM自由现金流率，单位pp；缺窗口为NULL |
| FR-M2-06b | op_margin_ttm=TTM营业利润/TTM营收，按README百分数存储；OperatingIncomeLoss也适用D2，缺标签为NULL |
| FR-M2-07 | 输出健康 JSON、can_score/can_trade 和拒绝原因；外国申报人只观察；核心字段完整性与segment码边界见疑问 |
| FR-M2-08 | 每日北京10:30前保存59只一致预期；向Muse方申请的历史文件离线导入，按as_of/ticker/source幂等，保留原时间，不回补或外推 |
| FR-M2-09 | F2只用as_of≤目标日的快照；目标日前N个自然日向后找最近快照，偏离目标>3天为缺失；不足N天明确标注；计算广度、分歧度和最近四季surprise |
| FR-M2-10 | F1只从申报原件XBRL实例取分部收入/利润、披露的重要费用；收入加抵销项核对合并营收，≤1%才通过；single_segment要有披露依据 |
| FR-M2-11 | 检测重分部，保存新recast_group与并列历史；不跨口径计算同比；名称/数量与同期误差条件见疑问 |
| FR-M2-12 | 每个新分部起草一次segment_mapping_draft，只用glm-5.3；待审核不写segment_std、不用于隐含幅度；保存审核状态和时间 |
| FR-M2-13 | 每日59份F3档案，主营业务/财报趋势/一致预期三个区块有数据或缺失理由；新财报、EPS当年共识变化>3%、M1指引事件分别留变化记录 |
| FR-M2-14 | 每个采集、离线导入、提取、分部映射、派生和档案任务写job_runs，耗时/状态/计数/错误/params_version可核对 |

## 2. 不做的事与边界

不做M3打分、M5估值、M8基本面轨道判断、M10页面、分部加总估值、A+交易规则，不改M0门禁或跨模块迁移。日常纸面组合读取fixed，v18复现读取legacy，两套行同时保留并明确extractor。

测试继承M0 v3：Clock注入，离线HTTP响应/冻结XBRL及本地taxonomy、LLM录音；不启动本地TCP服务、不使用真实key、不联网下载taxonomy，不手工skip/xfail。**每个规则同时验证拦截与不误伤**：PIT未来不可见/当日可见，stale181天/180天，D2缺一季/完整三季，标签缺口/合法旧标签，SIC命中/普通行业，不确认映射/确认后可用，分部误差>1%/≤1%，窗口偏移4天/3天，未配置/源恢复、重复导入/不同来源新行。

## 3. 输入和缺失处理

| 输入 | 来源、接口、拟处理 |
|---|---|
| 59只标的与身份 | M1负责建立config/universe.yaml；M1未完成时使用本模块冻结输入，不私建第二套业务标的清单；SIC、foreign判定来自submissions |
| submissions、8-K、指引字段、行情健康 | M1的原始submissions、earnings_events、info_items、bars_daily；M1尚未完成先用契约夹具，实际表/字段等待两份复述单的答复 |
| companyfacts | `https://data.sec.gov/api/xbrl/companyfacts/CIK{10位CIK}.json`，约2009年起的历史facts；按filed/end截止过滤，不用今天最新修订替代当时值 |
| XBRL/iXBRL原件 | 根据submissions accession定位SEC Archives目录/index.json、实例/inline文档和依赖taxonomy，D3与F1共用解析器；源失败保留历史状态并标lag/segment_missing |
| SEC访问 | 与M1共享全项目限频；官方总上限10请求/秒，拟共用5请求/秒预算、User-Agent、缓存与429退避；身份等待R5，不另起一个各自10请求/秒的客户端。[SEC API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)、[访问规则](https://www.sec.gov/about/developer-resources) |
| 一致预期当日 | 文档限定yfinance：Ticker.eps_trend、earnings_estimate、revenue_estimate、eps_revisions、analyst_price_targets、earnings_history；不接另一个供应商。拟少并发、缓存同ticker响应、429指数退避，限频参数待确认；缺值NULL/窗口原因可见。[维护者API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html) |
| Muse历史 | 最新README R7规定由开发向Muse方申请离线文件，附表结构/导出时间并放仓库外；本模块只读文件，绝不连quant、还原quant数据库、读取连接文件或调用其采集代码。当前不联系Muse，导出安排随答复确定；格式见第7节，等待R7 |
| 图谱/分部映射 | M6的entities只读快照与已审核映射；M6前可以起草待审核，不能猜节点后标已确认。role_ingest当前无graph读取权，交付合同见疑问 |
| LLM | registry.segment_mapping_draft，glm-5.3，900秒、失败待分析不换模型；等待R4，测试只用录音，审核可用明确JSON合同供M10消费 |

R4、R5、R7未落实时先开发离线机制，不能用假数据证明真实59只覆盖。`test_fundamentals_live_smoke` 的本模块pending原因将在答复后按用户指示记 **等待 R4/R5/R7**，仅双重显式live开关可联网，永不进CI。缺Muse基准时replay也不能假称通过，须明确登记其R7依赖。

### XBRL解析库方案（待确认）

倾向用 **Arelle（Python发行包arelle-release）** 作XBRL实例、Dimensions和iXBRL解析器，读取context期间、QName、单位、dimensions、nil及缩放/符号后数值；业务提取、标签优先级、D1–D5、健康码全部在本项目重写。它支持传统XML和Inline XBRL，能够处理公司扩展taxonomy，优于仅按HTML/XML标签猜分部。[Arelle官方文档](https://arelle.readthedocs.io/en/latest/)。

收到答复后才选择并锁定Python3.11兼容版本和传递依赖。本地taxonomy/实例包先冻结并登记SHA与CHANGELOG，解析时离线，不允许解析器偷偷联网补DTS。证券定制标签/分部利润映射要有披露依据，保留profit_basis，不转换成统一口径。解析失败不从新闻/电话会补数字。

## 4. 输出、下游与空值语义

- `fundamentals.fin_state`：按ticker/extractor/accession/filed保存状态，含规格全部财报字段及新增fcf_margin_change_pp、op_margin_ttm、health_codes、field_sources；推算/兜底明确记录标签、原始期间、申报和方法。
- `state_asof(ticker, as_of_date, extractor)`：M3/M5读财报唯一入口；只返回filed≤日期的最新可见状态，没有为None。保留修订历史，不覆盖旧申报行。
- `segments/segment_mapping`：供M6/M8/M10；保留收入、利润、profit_basis、recast_group及审核状态；未审核segment_std=NULL；同比不可比为NULL，不把重分部当正常增长。
- `consensus_snapshot/consensus_derived`：供M5/M8/M9/M10；新增快照只追加，覆盖不足与缺字段分开标注；没有历史不以Yahoo当前“7daysAgo”值制造过去的snapshot。
- `profile/health`：供M10展示及M3数据检查，59行有健康码，拒绝原因不为空；页面渲染/交易执行不在本模块。

所有数据空值NULL/JSON null。原始缺失与合法数值0区分；分母为0或经济含义不成立的比率为NULL并保留原因。%/pp按百分数数值存；breadth、fcf_conversion等比例按其定义与单位合同存，不把1.0误成1%。legacy的“缺现金当0”冲突不擅自照搬，见Q-M2-1。

## 5. 每条验收的证明计划

| AC | 测试 / 证据 |
|---|---|
| AC-M2-01 | 原名15项blocking：test_revenue_tag_gap、test_q4_derived_from_annual、test_companyfacts_lag、test_stale_fundamentals_code、test_gross_margin_derived、test_ni_tag_fallback、test_industry_basis_na、test_fin_state_pit、test_extractor_fixed_toggles、test_segment_extraction、test_segment_recast、test_segment_mapping_pending、test_consensus_derived_pit、test_consensus_import_idempotent、test_health_contract；加test_legacy_matches_muse_state的30只×3日期、逐字段1e-9对照；真实基准未提供时不能用合成预期代替 |
| AC-M2-02 | 59只legacy/fixed字段与健康码差异、D1–D5单项开关影响矩阵，重点LITE/BE/COHR；真实数据恢复后验证可打分，夹具证明缺陷和修复机制 |
| AC-M2-03 | 59行health、拒绝原因/核心字段空值交叉校验、外国申报人can_trade=false；“哪些空字段阻止打分”须先明确 |
| AC-M2-04 | 54只的实际分部覆盖≥90%、single_segment披露证据、逐期收入+抵销误差；合成正常/1%边界/>1%错误均测 |
| AC-M2-05 | 抽5只含AMD/WDC，分部值逐条对应accession、原文fact/context与利润口径；真实申报原件的证据需SEC身份/冻结包 |
| AC-M2-06 | 连续5个交易日59只快照、原始日表与派生窗口、Muse导入行数/哈希/幂等记录；R7不能由新抓取数据取代 |
| AC-M2-07 | 59份JSON三区块有数据或缺失原因、变化记录的来源info_id/申报及阈值边界；无数据不可伪造完整趋势 |
| AC-M2-08 | 录音与待审核/确认/驳回JSON、未确认不能用于segment_std；M10负责页面。真实起草覆盖等待R4，审核合同待确认 |

应关闭I10/I11/I12/I33/I34；测试函数仍为文档17个，不改名。不修改milestones；不删除仍依赖真实数据的本模块pending行，不让文档的“全部转绿”掩盖R4/R5/R7缺口。

### 中期检查点

答复后、最终验收前提交 `handoff/M2/checkpoint.md`：**LITE、BE、AMD、CEG、ASML** 各一行最新legacy和fixed状态（截止时间、accession、filed、全部字段、健康码、field_sources），以及 **AMD、WDC** 分部表（期间、标签/context、利润口径、映射状态、抵销、误差、recast_group）。R5未到位可用任务书允许的冻结夹具，但明确标“夹具”与未验证真实覆盖，不冒充实盘样例；检查点用于核对合同，不替代验收。

## 6. 疑问（均未实施）

| 编号 | 文档位置、问题 | A / B、倾向与理由 |
|---|---|---|
| Q-M2-1 | FR01/README空值：Muse S:L194–202忽略缺失债务部分、缺现金按0算net_debt；shares也不是始终稀释股本，和§4输出“稀释股本”不一致 | A：legacy连这些缺失兜底也复现；B：NULL规则优先，缺现金/债务不能推导net_debt，明确legacy对照哪些字段/哪些例外；shares为legacy原口径、fixed另定。倾向B，请定冲突处理和fixed股本规则，不能偷偷差异或用0补缺 |
| Q-M2-2 | FR02/D1–D5：FY/累计6/9个月长度、同filed多标签平手、D4成本标签优先级与Q4的EPS/加权股本、D3“三天”起点未规定 | A：仅靠季度编号/任意天数推算、把全年EPS/加权股本也直接减前三季；B：显式fiscal year/context/期间判定，流量才推Q4，固定同日期优先级，D3按可见时间+自然天边界。倾向B，请给FY/累计期间判定、D4优先级、EPS策略、D3满3天还是第4天及正常期已有facts的判据 |
| Q-M2-3 | FR02/开关测试：D1修营收会连带改变增长率、毛利率、FCF率；D3补实例也可能触发D1/D4 | A：“只影响对应字段”仅允许一个直接字段变化；B：允许同一修复的明确派生依赖链，其他开关仍关闭。倾向B，请定义影响矩阵/开关顺序，防止测试和公式矛盾 |
| Q-M2-4 | FR01/test_legacy_matches_muse_state：冻结输出写“开发用Muse代码生成”，用户又明确只读、不调用Muse；固定raw数据/30只名单/对照字段未提供 | A：我直接运行/导入Muse代码生成；B：向Muse方申请由其在自身环境导出oracle及冻结输入，本项目独立重写后只比较离线数据。倾向B；请确认申请渠道、30只×三日期基准、companyfacts哈希、生成版本/字段清单，或明确另有允许的生成方式；没有oracle不得宣称replay已通过 |
| Q-M2-5 | §3/FR08/09：quant四表没有营收共识、coverage和EPS高低等字段；历史snapshot_date是北京时间，当前as_of业务日、same-source重复/跨来源优先级、跨财年0y/+1y可比性未明确 | A：用现在的Yahoo回望或当前字段补旧快照、重映射历史日期/财年；B：保持原导出日期，未存字段NULL并留原因，新增captured_at/目标财年等可见元数据，窗口仅比较同目标期；两source并存并明确选择规则。倾向B，请确认第7节CSV包合同、当日as_of定义与冲突优先级 |
| Q-M2-6 | §4/FR01：每次新申报行与Muse只从RELEVANT_TAGS找状态生效日不同；same-day多个申报/修订、field_sources、财报与实例历史版本如何选择 | A：完全复现有限标签触发生效日并按输入顺序任取同日行；B：存所有规定申报/accession与时间，legacy回放按明确适配口径，最新可见版本有固定排序和来源合同。倾向B；请确认/A修订、同日排序、D3解析旧实例的历史可见时点，以及M1原始submissions字段合同 |
| Q-M2-7 | FR07/AC03：segment_*被列ok类却含segment_missing/sum_mismatch；“可交易但财报字段为空”是全部字段还是核心字段？no_bar/earnings_event_missing如何合并 | A：任意NULL或segment码都禁打分；B：明确核心必填字段、允许因分母/窗口无意义而为空的比率及健康码严重级别，段落遵循同一矩阵。倾向B，不能误伤合法亏损/单一分部/公用事业，也不能缺营收却可交易 |
| Q-M2-8 | FR10/11/规格4.8：BusinessSegmentsAxis和ProductOrServiceAxis并存、公司自定义利润标签、抵销项、single_segment、分部重命名条件未细化 | A：两axis都加总、无维度就认单一分部、所有segment_*随便算同比；B：主axis优先、补充axis不重复计数，保留抵销/原利润口径，有证据才single_segment；变化且同期差>1%才新组，无同期可比值保留未知。倾向B，请确认标签/axis/context选择和无法比较时的状态、零营收容差、recast AND条件 |
| Q-M2-9 | FR09/13：coverage与revision period对应、分歧度/变化均值≤0、缺任一季surprise_last4、EPS跨负/零基数的3%触发和记录基准未明 | A：用0/绝对值/少于四季平均或每日前值猜算；B：明确分母和统计量/目标财年，缺项NULL并说明；变化记录只在明确基准上比较。倾向B，请给surprise_last4是列表还是汇总、计量单位、跨财年/跨零和阈值边界（严格>3%） |
| Q-M2-10 | §2/6外国申报人年度口径、约2009年起、op_margin/fcf_change新增字段不在Muse旧函数里 | A：把全年当一季拼TTM或宣称旧oracle有新增字段；B：年度与季度基准显式区分，foreign不交易；新增字段按本规格另算并单独测试，不混进旧字段比较。倾向B，请定年度口径、IFRS标签范围、历史起始与新增字段在两extractor的规则 |
| Q-M2-11 | §3/FR12/14：role_ingest无graph权限；共享job_runs/source_health、LLM客户端由谁建？M2还需要哪些图谱/审核字段 | A：管理员绕过或改M0/导入M6；B：M1负责共享采集运行表和接口，M6供只读实体快照，M2写自己的记录/审核合同，权限变化另由需求方指定。倾向B，请确认接口责任与实体快照合同 |
| Q-M2-12 | 解析器/检查点/待接通验收：Arelle锁定方式、taxonomy离线包责任、R7实际到达前的oracle和真实证据 | A：轻量XML猜值并运行时联网补依赖，夹具报告当作真实覆盖；B：Arelle独立业务规则+冻结离线DTS，向Muse方申请历史基准，检查点和验收区分夹具/真实未完成项。倾向B，请确认解析库选型、冻结包提供方和上述中期样例合同；此阶段不新增依赖 |

## 7. Muse 只读取数细节及历史导出

所有源码位置固定于 [aacea04](https://github.com/XuQingsong/muse/tree/aacea04e4562f70854d69330fe724aa2799f2858)。以下是**实际读到的行为**，不是要复制的实现；未在规格写明的细节请需求方确认写入M2新版文档。尤其NULL冲突不在此自动批准。

| 细节 | 读到的行为 | 固定源码位置 |
|---|---|---|
| PIT与单位优先级 | filed和end均≤CUTOFF；缺/坏日期条目跳过；每个标签先选第一种存在的单位，不跨单位拼接；季度单位候选依次USD、USD/shares、shares | [S:L47–66](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L47-L66)、[S:L75](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L75) |
| 季度长度 | 需要start；end-start天数80到100，含两端；不是用fp=Q1/Q2/Q3来筛，不推Q4；少于4个季度整条序列返回None | [S:L69–86](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L69-L86) |
| 同期多标签/修订 | 以end为键合并候选标签，filed严格较新才替换；filed相同先遇到者留下，受标签顺序和源条目顺序影响 | [S:L73–86](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L73-L86) |
| 营收标签顺序 | RevenueFromContractWithCustomerExcludingAssessedTax → Revenues → SalesRevenueNet；不含IncludingAssessedTax | [S:L141](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L141) |
| 流量标签 | 毛利GrossProfit，净利润NetIncomeLoss，稀释EPS EarningsPerShareDiluted，经营现金流NetCashProvidedByUsedInOperatingActivities；capex先PaymentsToAcquirePropertyPlantAndEquipment，再PaymentsToAcquireProductiveAssets，按同期间最新申报合并，非两标签相加 | [S:L142–146](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L142-L146) |
| TTM/增长窗口 | TTM取排序后最后4个观测；营收同比要8点，最近4点对前4点，前组和为0则None；季度同比函数同样要求8点，然后最新/倒数第5、上一季/倒数第6 | [S:L149–155](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L149-L155)、[F:L70–89](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/factor_framework_v3.py#L70-L89) |
| EPS与毛利可比性 | EPS增长要8点且两组TTM和均>0；毛利率要求毛利/营收最近4个季度end列表完全相同，变化pp还要前4个同样对齐 | [S:L156–169](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L156-L169) |
| FCF与比例 | OCF和capex各取最后4个后相减；此处不额外要求二者end列表完全相同。margin/ROE为百分数，conversion为比值；净负债/FCF只在FCF>0时计算 | [S:L170–202](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L170-L202) |
| 时点标签规则 | first tag有候选即返回该标签的最大(end,filed)，不跨标签择全局最新；单位默认USD→shares | [S:L89–96](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L89-L96) |
| 资产负债标签顺序 | 权益StockholdersEquity；现金CashAndCashEquivalentsAtCarryingValue；流动债DebtCurrent→LongTermDebtCurrent；长期债LongTermDebtNoncurrent→LongTermDebt；流动比率AssetsCurrent/LiabilitiesCurrent | [S:L184–198](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L184-L198) |
| 缺失债务/现金 | 已有债务部分直接相加，现金缺失时net_debt按0扣减；这与本项目NULL要求冲突，必须先答复Q1 | [S:L194–202](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L194-L202) |
| 即时股本 | 比较dei EntityCommonStockSharesOutstanding和us-gaap CommonStockSharesOutstanding的最新end，end相同保留前者；同end按accn去重、同accn取更晚filed；多值最小/最大>0.9视重复取最大，否则合计 | [S:L99–128](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L99-L128) |
| 股本新鲜度/兜底 | 即时值非0且end在截止前400天内用它；否则尝试季度WeightedAverageNumberOfDilutedSharesOutstanding，序列不足4点不能用；再退回旧即时值；记录shares_date近似标记 | [S:L129–136](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L129-L136) |
| 过期和季度缺口 | 营收end距截止>180天标fund_unreliable；否则最后4个end跨度>380天移除增长/毛利/FCF率/PS等相关字段，但不移除rev_ttm本身；两检查是if/elif | [S:L216–233](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L216-L233) |
| 状态生效日 | 初始2025-12-31；只从固定7个RELEVANT_TAGS的10-Q/10-K/20-F/6-K及前缀变体中收集2026年filed日，每日调用取数语义；会遗漏只新增资产负债/新标签的日期 | [P:L55–83](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_2026.py#L55-L83) |
| 价格派生边界 | fund_states移除pe/ps/fcf_yield/peg、市值和拆股嫌疑；compute_books用当日price重算，不是把虚拟price=1的字段存入财报状态；四本账及按价派生属M3，估值区间属M5 | [P:L78–80](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_2026.py#L78-L80)、[P:L109–125](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/paper_trade_2026.py#L109-L125) |

### 历史数据从哪里导出，什么格式

**已确认来源**：README R7指定的Muse沙箱 **quant库、data schema**。最新main要求开发向Muse方申请pg_dump或CSV，附表结构和导出时间，文件置于仓库外；数据由Muse方长期保存，不会丢失。固定源码的 `schema.sql:L4–13` 明示实际结构以pg_dump为准，旧DDL只作字段参照。`restore_quant.py:L13–16` 提到旧备份 `quant_dump_v2_2026-10-08.sql.gz`，这是gzip压缩SQL旧恢复包的名字，**不等于已经拿到最新数据**，也不建议把该恢复脚本或连接配置导入本项目。R7仍未到位；我不读取quant数据库。

建议向Muse方申请下面4张原始表的 **UTF-8 CSV.gz**，每表一个文件、带表头，日期ISO格式、timestamptz保留UTC、NULL使用明确`\N`；附manifest（表名、schema、截止时间、ticker列表、行数、SHA-256、导出格式版本），再在本项目仅解析文件。此具体格式是**建议，待Q5确认**，不声称存在现成导出路径；若提供pg_dump/SQL.gz，须明确只抽取离线数据的转换合同，不能连接或还原quant来绕过约束。

| Muse来源表 | 固定源码的字段与目标映射 |
|---|---|
| data.estimates_trend | snapshot_date,ticker,period,cur,ago7/30/60/90,rev90_pct；period=0q/+1q/0y/+1y的cur对应eps_cq/nq/cy/ny。ago*仅是抓取日的回望读数，不构造过去快照 |
| data.estimates_revisions | snapshot_date,ticker,period,up30,down30,up7,down7；0q与0y不能混用，FR09的coverage/目标期待确认 |
| data.price_targets | snapshot_date,ticker,price,mean,median,high,low；mean/median对应pt_mean/pt_median，其余原始证据保留 |
| data.earnings_history | ticker,quarter_date,eps_actual,eps_est,surprise_pct,first_seen；quarter_date不是首次可见日，PIT以first_seen及导出证据判断 |

表名/字段位置：[schema.sql:L4–62](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/schema.sql#L4-L62)；旧备份说明：[restore_quant.py:L1–16](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/restore_quant.py#L1-L16)。

额外核实：旧每日采集的日期是**北京时间date**，EPS/revision/target/history分别从yfinance各接口保存，earnings_history的surprisePercent写入前乘100。[fetch_estimates_daily.py:L20–63](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/fetch_estimates_daily.py#L20-L63)、[L85–105](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/fetch_estimates_daily.py#L85-L105)。四表没有rev_cy/rev_ny、coverage、EPS high/low或完整目标财年；不能从当前数据填历史空洞。源脚本注释称32只，实际TICKERS列表28只加MU/GOOGL是30只；历史实际覆盖必须以导出manifest核对，不能靠注释或猜59只齐全。

可一并向Muse方申请原始companyfacts缓存 `pit_cache/{ticker}_facts.json` 的JSON和SHA（可选、省下载时间）；legacy oracle需要独立的30只×3日期输出及相同raw输入，不能从本项目自己的结果反向生成期望值。[原缓存格式](https://github.com/XuQingsong/muse/blob/aacea04e4562f70854d69330fe724aa2799f2858/code/screen_asof_2026_01_01.py#L36-L44)。

R7的Form 4 (`data.insider_transactions`) 和VIX (`data.vix_daily`)交M1；这里不替M1实施导入。所有历史值保持可见时点、源标记muse_import，不把目标价当估值，不导入数据库连接配置。

## 8. 收到答复后的流程

先提交失败测试与冻结输入，再写独立提取/解析/导入实现；标准答案只走现有load_golden，不新增副本。所有冻结输入登记MANIFEST和仅追加CHANGELOG。到中期提交第5节样例；全部真实验收证据就绪后提交self-test并改正式PR标题。当前在草稿复述单处停下，等待需求方逐条答复。
