# M1 开工复述单

模块：M1 行情与信息采集　文档版本：v1　复述人：开发者　日期：2026-10-13

任务卡：`docs/tasks/phase1/T01-M1-market-info-ingest.md`。分支：`phase1/m1-market-info-ingest`。
基线：M0 v3 合并提交 `e478fe6bd0960a08b296f757cf7cfcc6a6d20bfb`，并同步 main `56a2ab69f14b7ad33d662a0b01cd9b5641a2037c` 的 README R7 说明。本 PR **仅提交本复述单**，不提交实现、测试、夹具、依赖或配置变更；等需求方逐条答复后再开发。

已按顺序读整体任务书、第一阶段任务书、任务卡、README §3–4、M1 v1 全文，以及规格 §3.2、3.3、4.1–4.3、4.7、5.5。golden 通过 `load_golden('m1_earnings_sessions.json')` 读取并核对；不改 docs。

## 1. 我理解要做的事

| FR | 本模块的行为 |
|---|---|
| FR-M1-01 | 59 只股票和 14 只 ETF 的分钟线覆盖美东 04:00–20:00；用 XNYS 日历标记盘前、盘中、盘后，半日市盘后从 13:00 开始 |
| FR-M1-02 | 保存原始日线、单独保存拆股复权因子；post_close 只取盘后有成交的最后一根 bar，无成交为 NULL |
| FR-M1-03 | 广域普通股集合每月首个交易日重算成员，每日检查成交额；保存全部候选、历史资格和四类排除原因，不调阈值凑人数 |
| FR-M1-04 | 全市场 Alpaca News 首次回补 90 天；原生 id 去重，转载用 source_root 联系但不因此丢弃原始条目；两个时间都保存 |
| FR-M1-05 | 全市场 8-K Atom 入全量库；每日保存标的池 submissions 及历史分页，保留 items 和 acceptanceDateTime 供 M2、M7 使用 |
| FR-M1-06 | 仅从 8-K Item 2.02 生成 earnings_events，按接收时段决定 reaction_day；ref_close 来自此前最后一个常规收盘，10-Q/10-K 只回填财季；兜底能力缺口见疑问 |
| FR-M1-07 | 从原始 Form 4 非衍生交易表提取交易代码、股数、价格、officer 和 accession；以 filed_at 可见，不以成交日提前可见 |
| FR-M1-08 | 每小时保存美国免费榜和畅销榜前 100，监控实体名次跳升严格 >20 才产生事件；快照照常保存 |
| FR-M1-09 | 来源等级按配置映射；未知来源为 4；转载与原始来源分开记录，不因为转载声称来自一级来源就自动升级 |
| FR-M1-10 | 监控实体 Trends 每日采集，热度严格 > 同口径 90 日均值的 3 倍才产生事件；失败标未接通，不造数据 |
| FR-M1-11 | 监控官网正文变化才产生事件，保留正文差异片段，页面抓取失败不当作删除全部正文 |
| FR-M1-12 | 词表先标注代码和公司名，entity_tagging 输入标题与正文前2,000字，用 deepseek-v4.1-flash 补充图谱实体id；重试 2 次后仍失败也保存信息 |
| FR-M1-12b | info_fields_extraction 使用同一模型，补指引及方向、评级/目标价变化、缺失的发布时间；失败字段为 NULL，标明抽取来源 |
| FR-M1-13 | DashScope 生成嵌入；失败 embedding=NULL，记录失败计数，不能阻塞信息保存 |
| FR-M1-14 | 每次任务更新 source_health；区分未配置、短期故障和持续不可用；具体状态优先级见疑问 |
| FR-M1-15 | FINRA 空头与 CBOE 期权统计保存并进入全量库；宏观六类 FRED 数据也接入。免费端点覆盖限制必须展示 |
| FR-M1-16 | 每个采集、回补与维护任务都写 ingest.job_runs，包含 trade_date、起止时间、状态、计数、错误摘要和 params_version |

## 2. 不做的事与边界

不做 M7 异常判断、M8 说法抽取/归因、M2 财报数字、M6 图谱生成、M10 页面渲染，不按“重要性”过滤信息，不接社交、融券费率、产业价格或其他供应商补洞。健康页在本模块指可供 M10 消费的健康数据，不实现页面。

继承 M0 v3：测试用冻结响应、合成输入和按任务名+输入哈希索引的录音；Clock 注入；asyncio、socketpair、TestClient 可用，**不启动本地 TCP 服务**。所有门禁/过滤同时测应拦和不应拦：完整 bar 正常入库、无成交不冒出假价格；普通股过线入选与四类排除；重复 id 去重与不同新闻保留；名次跳升 21/20、Trends >3/等于3；陌生实体或 LLM 失败仍保存原文。缺失为 NULL，不用前值、0、空字符串或 NaN 代替。

## 3. 输入、接口和限频方案

`config/universe.yaml`、`monitored_entities.yaml`、`source_levels.yaml` 当前尚不存在；本模块按规格建立前两者人工初版和来源配置，未明确的别名/实体映射等答复。M6 后续输入如何交付见 Q-M1-11。

以下是**拟采用**的接口与工程参数。供应商额度是已核对的事实；主动限频、重试参数和有歧义的取数规则均待确认，不是已实施配置。所有 HTTP 客户端可注入；测试以假传输和假等待器验证分页、429、超时和恢复，不联网或真实等待。

| 数据源 | 接口 / 用法 | 限频、失败与前置条件 |
|---|---|---|
| Alpaca 分钟线、日线 | `GET https://data.alpaca.markets/v2/stocks/bars`，分别 timeframe=1Min/1Day；显式 start/end、feed、adjustment=raw；遍历 next_page_token，不能只取第一页。复权因子拟另取 split 调整对照，不改 raw | 官方 Basic 历史 API 200 次/分且最近 15 分钟受限；拟≤120 次/分、共享配额与响应 X-RateLimit 头，429 按 Retry-After/reset 暂停。SIP 全市场覆盖，不能默默切成 IEX。等待 R5，08:00 截止与延迟权限见 Q1。[bars](https://docs.alpaca.markets/us/reference/stockbars)、[额度](https://docs.alpaca.markets/us/docs/about-market-data-api) |
| 候选证券和代码/CIK | Alpaca 只读 Assets `GET /v2/assets?status=active&asset_class=us_equity`；SEC ticker/CIK 映射与 frames 关联 | 不连接交易或下单接口。缓存资产元数据；Assets 不保证普通股/ETF/ADR 分类充分，分类依据待答复 |
| Alpaca News | `GET https://data.alpaca.markets/v1beta1/news`，不以 symbols 筛掉池外消息，include_content、按时间窗分页；created_at 作来源发布时间候选，保留 updated_at 原始证据 | 共享供应商额度、检查响应限频头；90 天分窗回补，保存断点。R5 未到位用冻结响应。[News API](https://docs.alpaca.markets/us/reference/news-3) |
| SEC 8-K Atom | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&owner=include&count=100&output=atom`；完整保存链接/accession | SEC 全项目合计最多 10 请求/秒；拟 M1+M2 共享 5 请求/秒预算，带用户确认的 User-Agent，缓存与退避。不能假定最新 100 条就是全量，缺页补采方案见 Q4。[官方资源](https://www.sec.gov/about/developer-resources) |
| SEC submissions、Form 4 | `https://data.sec.gov/submissions/CIK{10位CIK}.json` 及 filings.files 历史 JSON；Form 4 根据 accession 的 SEC Archives 目录/原始 XML 下载 | 与上述 SEC 统一限频；只在来源可见时间入库；身份等待 R5，历史 Form 4 导入等待 R7。不读取 Muse 数据库 |
| SEC 广域股本 | `https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/CY{年}Q{季}I.json`，选最近可用 instant frame，按 CIK 关联 | 帧仅取最近申报的日历期对齐值，保留 accn/end 原始证据；股本取不到标 no_shares，不擅自改用另一标签或供应商。与 M2 共享 SEC 限频。[frames 文档](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) |
| Alpha Vantage 兜底 | `GET https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month`，CSV；全市场一次取回再筛标的 | 官方通常 25 次/天，拟每天缓存一次全市场结果，不逐只耗额度；429/额度信息标未完成。该端点是未来预定日历，不能提供历史实际发布时间，见 Q5；等待 R5。[端点](https://www.alphavantage.co/documentation/#earnings-calendar)、[额度](https://www.alphavantage.co/support/) |
| App Store | Apple 官方 [RSS Builder](https://rss.marketingtools.apple.com/) 的 US/free/100 feed；grossing 候选为 Apple 旧 RSS `https://itunes.apple.com/us/rss/topgrossingapplications/limit=100/json` | 两榜各每小时一次、同域串行，ETag/Last-Modified；无公布的固定 SLA，429 后退避。现行 grossing 可用性需确认，不拿 paid 榜替代；见 Q8 |
| Google Trends | 文档指定 pytrends：TrendReq/build_payload/interest_over_time，底层 explore 和 widgetdata/multiline；同实体同窗口比较 | 无稳定官方额度；拟串行、请求间至少 10 秒，429 冷却本次源；接口错误标未接通，不绕到其他 API。pytrends 已归档，实际可用性不作为既成事实。[维护者源码](https://github.com/GeneralMills/pytrends/blob/master/pytrends/request.py) |
| 官网 / IR | 人工监控 URL 的 HTTP GET，正文提取、哈希、差异片段 | 每 URL 每日一次，同域串行、拟间隔≥2秒，条件请求；429/403 不当作正常空正文。URL 和正文稳定区域来自监控清单，不全站爬取 |
| FINRA 空头 | 官方 Query API 候选 `GET/POST https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest`，按 settlementDate 和 symbol 过滤、按发布日采集 | 官方同步上限 1,200 次/分/IP；拟 60 次/分并按两次/月发布日缓存。官方该数据集声明 OTC 覆盖，不能声称覆盖 NYSE/Nasdaq 59 只，更不能用日度做空成交量冒充空头持仓；待 Q7 明确所指接口。[数据集与额度](https://developer.finra.org/docs) |
| CBOE 期权统计 | [Daily Market Statistics](https://www.cboe.com/us/options/market_statistics/daily/) 的交易日期页/下载，保存市场级 call/put 成交量、持仓、比率及原始日期 | 每发布日一次，拟同域≤1请求/秒、缓存/条件请求；不把汇总数据解释成单股 IV、希腊字母或资金方向。所需粒度见 Q7 |
| FRED 六类宏观 | `GET https://api.stlouisfed.org/fred/series/observations`；候选 series_id：CPIAUCSL、PAYEMS、DGS2、VIXCLS、DCOILWTICO、DTWEXBGS；保存来源单位、观测日和版本时间 | 每日增量、拟≤30请求/分、缓存和429退避；`.` 缺失值为 NULL。FRED key 未在现有 R5 清单中列出，见 Q9；不用观测日冒充精确发布时间。[API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html) |
| 实体标注 / 字段抽取 | registry 的 entity_tagging、info_fields_extraction、必要的 dedupe_assist；模型仅 deepseek-v4.1-flash | 120秒超时、重试2次；并发/服务商由 R4 确认。等待 R4，只用录音；失败保留原信息 |
| DashScope 嵌入 | 官方同步 text-embedding HTTP API 或兼容 embeddings API，base URL、模型和维度由 R5 提供 | 批大小和额度取账户/模型真实限制，不写死未确认维度；超时/429可重试，仍失败为 NULL，不阻塞入库。[官方接口](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api) |

拟统一对瞬时 HTTP 429/5xx/超时最多重试 3 次、指数退避有上限；401/403/数据格式不符不重复轰炸。实际参数放 `config/params/p-2026.10/m1.yaml`，需要与任务总预算共同确认。上表未声称任何 key 或源已接通。

### 广域集合市值和预计人数

遵守 Q-M1-3：**SEC frames 的 EntityCommonStockSharesOutstanding × 最近常规收盘价**。保存 frame 名、CIK、end/accn、价格日期；没有股本不借 M2 diluted shares 填洞。ADV20 拟用最近 20 个交易日原始 close×volume 的均值，原值比较 20 亿美元/2,000 万美元含等号；窗口不足不能当作 0 或前值。成员按 M1 范围每月首个交易日重算，每日检查成交额并保留剔除/恢复证据；细则待 Q2–3。

预计 1,000–1,500 只是规格 §3.2 的规划估计，验收区间为 800–2,000；**不是当前实测人数**。R5/R6 未落实时只能用合成边界表证明筛选，不能承诺真实入选数。真实导出须包含候选总数、入选数、各排除原因、无映射/无价格/窗口不足明细。

### source_root（拟议，等 Q6 答复）

1. info_id 是原始条目主键，重复同一 id 只计一次；first_seen_at 保留首次，published_at 保留信源原值和出处。
2. 上游原生稿件 id 或明确的原始稿件链接优先作为根证据。URL 只规范 scheme/host、片段和已确认的追踪参数，保留有语义的路径/查询；单独出现媒体名字不够。
3. 没有上游 id 时，拟以规范正文的完整哈希识别同稿；不以相同标题、同股票、近似主题或 LLM 判断单独合并。只去 HTML/空白噪声，不删除数字、否定词、引述或关键句。
4. 根可表示为 `源头标识:原生id`，无上游证据时用规范稿件哈希；仅标题/正文缺失的条目保留自己的根，不能猜通讯社归属。LLM 仅辅助找候选，最终归并需可核对证据。
5. 不同 URL 的转载条目保留各自 info_id/来源/时间，只共用根；同一根不能造成多条独立信源投票。source_level 仍按原始载体判定。

## 4. 输出、下游和空值语义

- `ingest.bars_minute/bars_daily/wide_universe`：供 M3、M4、M6、M7；完整保存时间、session、source、raw 价格与资格历史；无盘后成交 post_close=NULL。
- `ingest.info_items`：供 M7–M10 回捞、归因与健康展示；保留合同全部 id/时间/信源/原文/实体/embedding/status；NULL 时间必须有缺失/抽取标记。合同欠缺的 flags、抽取字段、summary 和结构化源 payload 见 Q10。
- submissions 原始记录、`earnings_events`、`form4_events`：供 M2 以及 M3/M4/M7；SEC filed/accepted 与 transaction_date、10-Q 财季日期不混用。
- `app_rank_snapshots`、`source_health`、`job_runs`：供 M10 展示和验收追踪；失败源不拖住别的源，缺失不能变成模拟成功。

## 5. 验收证明计划

| AC | 测试 / 证据 |
|---|---|
| AC-M1-01 | 原名14项 blocking：bar_window_to_20et、bar_window_from_04et、post_close_null_when_no_trade、wide_universe_rules、news_dedupe_and_times、earnings_reaction_day、earnings_fallback_flag、form4_parse_code_p、app_rank_jump、trends_unavailable_marked、source_level_mapping、info_item_contract、info_fields_extraction、llm_extraction_failure_degrades（均带 test_ 前缀）；每项扩充正常与误伤对照 |
| AC-M1-02 | 真源连续5个交易日 job_runs/source_health、73代码×日期覆盖、分钟覆盖分母/分子、北京完成时间；R5 未到位前不能以合成数据证明 |
| AC-M1-03 | 实际全量候选及排除原因导出、逐日/每月入选数；合成夹具验证阈值等号与四种排除，不调参数凑800–2,000 |
| AC-M1-04 | 10条新闻原文时间核对和5条转载证据链；同稿多URL正例、标题相同正文不同的反例 |
| AC-M1-05 | load_golden 的全部8用例及精确时段边界、后续申报回填不改变反应日；另核对10次真实8-K原始接收时间 |
| AC-M1-06 | 假HTTP故障与恢复、两源并行不互相拖累；真实配置故障演示需R5，健康 JSON 交给 M10，M1 不写页面 |
| AC-M1-07 | 每任务证明采集数=入库数+原生id去重数；转载、低重要性、字段抽取失败、向量失败都仍保留 |
| AC-M1-08 | 按实体标注/嵌入独立分母统计失败率、失败样例；录音证明机制，真实比率等待R4/R5 |

本模块负责 I22、I28 数据部分。真实 `test_ingest_live_smoke` 已在 pending；答复后只调整本模块依赖真源的原因为 **等待 R4/R5/R7**，真实测试仅显式 `-m phase1_live` 且 `INVES_COG_LIVE=1` 运行、永不进CI。当前不改 pending/milestones。不把5天真实证据写成已完成。

## 6. 疑问（A/B 与倾向，均未实施）

| 编号 | 文档位置、问题 | A / B、倾向与理由 |
|---|---|---|
| Q-M1-1 | §2/AC02：无成交分钟不产生 bar；覆盖率分母是什么？SIP 最近15分钟限制在夏令时可能赶不上北京08:00完成。标的代码包括SKHY，别名/CIK/是否可由Alpaca取到需确认 | A：960分钟×73作为固定分母，延迟也算完成；B：明确来源可用bar/无成交/采集缺失区分及 deadline/feed 权限，不能伪造空bar或改代码。倾向B，请给覆盖定义、R5 SIP权限和缺代码处理，不能先承诺99% |
| Q-M1-2 | §2/FR03：普通股候选如何识别？ADR是否允许？同CIK多类别、ADR换股比率、frames未覆盖本季度或旧股本怎么办？ | A：仅靠Assets名称猜类别并以发行人总股本乘单类价；B：确认证券类型/CIK映射、多类及ADR口径、股本新鲜度；无法可靠映射保留原因，不改用别的股本源。倾向B，避免倍数错误 |
| Q-M1-3 | FR02/03：ADV20不足20天、缺price/volume的排除码；每日跌破门槛后恢复/市值变动规则；adj_factor方向 | A：窗口不足按现有天数均值，日检查重新筛全部市值；B：完整20交易日、不补缺值，月度市值/每日成交额按文档分开并明确恢复策略。倾向B；复权倾向明确 raw×factor=split-adjusted，请确认新增原因码及历史口径 |
| Q-M1-4 | FR05：Atom最新100条可能不足全市场一天；submissions原始输出表未列在§4 | A：只保留当前Atom页；B：Atom增量加SEC官方日索引/accession补漏、保存可复用原始submissions分页给M2。倾向B，才可证明全量；请确认补漏接口、原始表合同和首次历史范围 |
| Q-M1-5 | FR06与golden：Alpha Vantage EARNINGS_CALENDAR是未来预计日历，没实际历史时刻；黄金休市时段是closed_day而合同是closed | A：只有日期就默认盘前并计算reaction_day，沿用两种时段；B：不编时刻，明确兜底可用字段/缺失状态与唯一枚举，由需求方同步文档或golden。倾向B；请决定是否保持closed并同步golden，开发不会改标准答案 |
| Q-M1-6 | FR04：source_root算法、规范URL/正文范围、更新稿处理没写 | A：相近标题/实体或LLM认为同事件就归并并删重复；B：采用上节可追溯的原生id/原始链接/完整正文哈希规则，根归并不丢条目，更新稿留版本。倾向B；请确认字段格式、正文归一规则、修订稿是否新根及同id更新的保存合同 |
| Q-M1-7 | FR15/规格5.5：官方FINRA公开consolidatedShortInterest声明OTC，CBOE免费daily为市场级；short/options专表不在输出合同 | A：用日度做空成交量或汇总期权推单股持仓/IV；B：限定已确认的FINRA/CBOE官方端点和粒度，缺单股值NULL、健康注明。倾向B，请给NYSE/Nasdaq所需FINRA接口、CBOE字段和是否需要专表，不换源 |
| Q-M1-8 | FR08/10：grossing官方feed当前可用性未核实；监控app_id/Trends关键词、US范围、90日均值是否含当天/partial日 | A：改用paid榜/其他趋势源或混合独立窗口值；B：仅用文档所指官方榜单和pytrends，同查询窗口下用此前90个有效完整日，缺90天不判突增。倾向B，请确认feed、监控清单及窗口不足/首次出现规则 |
| Q-M1-9 | §2宏观/规格4.1：FRED key未列R5，六个series单位和PIT版本、发布时间；美联储/EIA新闻稿是否在M1范围 | A：用最新修订值回填并把观测日当发布时刻；B：六series保留原始单位与版本，缺发布时间NULL，历史可见口径明确，范围不自行扩张。倾向B，请确认上表series（PAYEMS为就业人数水平）、FRED key及新闻稿范围 |
| Q-M1-10 | §4/FR12b/13/90天留存：flags、summary、guidance/rating细节和结构化payload没字段；嵌入模型、维度、长文切分没规定，摘要任务属M10 | A：只放headline/body，90天直接清正文，向量维度猜值；B：需求补充持久化字段及摘要责任，摘要未完成不清正文，embedding维度/切分由R5确认。倾向B，防止丢证据或M2读不到指引；请确认 M1/M10 和共享LLM客户端责任 |
| Q-M1-11 | §3/README权限：需要graph.monitored_entities/entities，但role_ingest在M0无graph读权限且ingest不能导入graph业务代码 | A：绕过权限直接连管理员/导入M6；B：M6供只读快照或明确读接口，M6前用人工初版，不修改M0权限。倾向B，请定实体id/别名/app/url/Trends及后续快照合同；M1创建job_runs/source_health，M2只按合同追加自己的任务记录 |
| Q-M1-12 | FR14与§6：两次失败degraded/一天unavailable与News首次失败unavailable、Trends未接通的优先级；重试次数、任务超时无参数 | A：不同段落任意择一，重试不受总预算约束；B：明确未配置/未接通/连续失败阈值的优先级、一天是自然24小时或交易日、恢复条件，并确认上表工程参数。倾向B，使健康状态和计数可验收 |

## 7. Muse 源码细节与后续步骤

M1 不实现 Muse 的计算，不导入或调用其代码，也不连接其数据库。最新 README R7 要求开发向 Muse 方申请 Form 4、VIX 历史的导出文件（pg_dump或CSV，附表结构和导出时间），文件放仓库外，由本项目导入。当前只提交复述单，不联系或操作Muse；联络对象/渠道和格式保真要求随答复确定，导出数据长期由Muse方保存。不能从成交日伪造 filed_at。

收到新版文档答复后：先提交失败测试和冻结夹具，再实现 `inves_cog.ingest` 内的采集/存储，独立 `phase1_m1_*` 迁移；未落实 R4/R5/R7 时用夹具和录音完成离线机制，真实证据登记待补。现在停在复述单与草稿 PR。
