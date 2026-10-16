# M6 自测报告

模块：M6；冻结需求 v6（main be2137e）；日期：2026-10-15；实现提交：dd2d4c6（后续证据补充见 PR 提交历史）。

## 1. Harness

先提交 11 项实际失败测试（70537a6），再实现；后续输出有界、盘后和审核、中文标识各有独立失败提交。原名 12 个测试全部存在，11 blocking + 1 live。

- 全仓 blocking：50 passed、6 deselected，11.22 秒，blocking.xml。
- M6 blocking：11 passed，2.14 秒，blocking-module.xml。
- 显式 phase1_live、INVES_COG_LIVE=1：1 passed，93.04 秒，live-smoke.xml；本次真实覆盖 1,306 只，包括 59 只标的。只允许 live 联网，CI 不运行。
- 实现及引用审计完整提交 f733d29537730350677264f0a52e70e87f9f05f4 的 GitHub CI 成功：https://github.com/XuQingsong/inves-cog/actions/runs/38757142390 。审核证据提交的最新 CI 以 PR 检查为准。

## 2. 不变量、pending 与 milestones

M6 无独立关闭的不变量；M0 导入防火墙、价格隔离、网络和时钟门禁同时通过。M6 的 12 行已在实际转绿后全部删除；其他模块 pending 保留。milestones.txt 未修改。

## 3. 验收条款（按用户本次答复提交验收）

| 条款 | 自评 | 当前证据 |
|---|---|---|
| AC-M6-01 | 通过 | 11 blocking 全绿，v5 marketstate golden 全命中；blocking-module.xml。 |
| AC-M6-02 | 58/59；SKHY 缺口按用户答复不阻塞 | 58 只每只至少 3 条引用关系，HD 重试得到 8 条；SKHY 无年度业务原文，未编造关系。按用户本次答复改读 M2 interim_results，缺连续四季则明确“无法检验”。已建 16 个 L2、13 个 L3，AMD 主 AI 加速芯片，同时属于 CPU，graph-seed-task.json。 |
| AC-M6-03 | 通过 | MSFT、NVDA、ORCL、CRWV 四家已有来源金额候选；WDC HDD 年度 129.19 亿美元对应 M2 原始分部行。STX 按用户确认的单一业务口径，以合并年营收 121.95 亿美元起草 HDD 暴露，exposure_basis=分部收入，保留 single_business_consolidated_revenue 标记和来源。structured-exposures.json / final-graph-audit.json。SKHY 不属于本条要求。 |
| AC-M6-04 | 通过 | 用户明确答复“确认这7条候选”后，按 hdd-review-batch.json 的完整编号和版本执行确认。生产已确认视图核验 7 条“观察到”，其中 1 条 WDC 分部收入 129.19 亿美元；7 条审核日志及审核时间见 hdd-review-result.json。 |
| AC-M6-05 | 通过，待需求方独立复核 | 2026-10-12/13/14 的 AMD、ANET、WDC 共 9 组；independent-full-check.json 从原始调整行情、成员关系独立重建全部因子，再以 QR 回归，最大误差 6.25e-17 < 1e-6；independent_reference.py 未导入生产计算。real-three-days.json 保存生产窗口和因子，另留早期的仅回归 QR 检查。 |
| AC-M6-06 | 通过 | 已审种子及 Toshiba 官网/趋势；graph-monitored-task.json 新增 156 个篮子上游实体，均至少有趋势关键词。Toshiba 官方新闻频道已实际打开核实。 |
| AC-M6-07 | 运行记录具备 | graph-cluster-task.json 实跑为空，sample_days=3、insufficient_history；建议保存在 graph.cluster_suggestions，不自动建立篮子。 |

## 4. 真实输入与计算

只使用本项目独立数据库。广域行情回补 702,069 行（wide-history-warmup.json），不伪称准时调度。CBOE VIX/VIX3M 和七只 ETF 共 13,637 行（price-inputs.json）；SIC 本轮 1,207 只、复用当月 99 只，无失败（issuer-profiles.json）。日常月度采集可续跑，不每日重复 1,306 次。

个股收益来自 close×adj_factor，不前填；盘后来自 post_close/close，空值不代替为收盘。逐级正交和个股 OLS 均用信号日前窗口，含截距，至少 60 个共同有效样本，SVD 求解；缺系数不填 0。价格层 SQL 限于规定的价格、篮子、VIX 和 SIC 表，不读新闻、LLM、估值或 graph.relations。选取广域成员发生在入口适配层，未作为特征。

篮子自身至少 2 个有效成员，个股留一后 1 个可用；0 个少一个因子并记录原因。close/post 均持久化股票、篮子、轮动行，五日值不跨缺失观测凑数。市场字段采用 v5 规则，VIX 和期限缺失如实标明。

## 5. 正反断言与审核安全

原名测试同时覆盖：真线性恢复/秩不足、59/60 样本、当日污染不影响 β、留一本股修改不污染篮子、单成员因子可用/独立篮子不足、盘后有价/无价、beta_share 边界、价格白名单允许/拒绝、有效引用/更换原文引用无效、候选不进入已确认视图、确认/驳回/非法修改、中文不同实体不产生空标识或合并。

审核仅在用户明确动作后生效，记录前后快照、时间和版本，修改证据或身份会拒绝。中文空标识的本轮一条候选已原位修复并保留引用；数据库增加非空约束。非法暴露口径的未审草稿保留原值证据并驳回，没有静默变为已确认金额。

GLM 首轮三次触及默认 65,536 输出上限导致无 JSON，真实失败用量已如实记入 ingest.llm_calls；随后仅图谱两个任务设 max_tokens=8192、reasoning_effort=low，未换模型。全部真实起草均由共享客户端记账，候选在审核前不供隐含幅度使用。

## 6. 待办与边界

用户本次已确定两项缺口的处理：STX 单一业务使用合并营收；SKHY 四季拼不出则标“无法检验”，不阻塞。backlog.md 保留真实 SKHY 季度缺口，HDD 实际审核已完成。按 §4.7 不因此修改冻结文档或停掉其他开发。不修改 docs/golden/milestones；不运行 Muse；M7 尚未开工。正式常驻部署参数与审核入口在 handoff 交付，价格作业以美东时区配置，不能把显式回补当作准时运行。

## 7. 最终引用与金额审计

62 份实际 SEC 原件重新下载复核，444 条候选引用均定位到规范化完整原文；fetch_failures=0、unresolved=0，见 canonical-sources.json。已修复“正文交叉引用被当成章节标题”和 Unicode 解析问题，先失败回归见 headings-red.xml。final-graph-audit.json 已只读重审全部未驳回关系（含已审核）：58/59 只至少三条关系、无无效引用、19 条带来源金额关系、162 个监控实体。包括原七条确认及本轮 STX 新候选；SKHY 缺口如实保留。

金额口径分别保留：MSFT 的已披露收入、应收和投资承诺；NVDA 对 OpenAI 使用园区的附条件担保上限；CRWV 的合同承诺；ORCL 是现有新闻信息 id 对应的约 3000 亿美元合同报道，属于待核验候选。它们不相加成统一“已实现收入”。WDC 采用 M2 HDD 原始分部，保留 row_id、申报、期间、币种和数值，不虚构原文句子。非结构化金额的 asof 由实际披露日确定，结构化金额对应原件期间，模型推测日期不入库。

HDD 七条具体候选已发布 hdd-review.md / hdd-review-batch.json：六条关系和一条 WDC 金额。用户在本线程确认后，于北京时间 2026-10-15 23:07:42 完成实际审核，7 条均进入“观察到”视图，并产生 7 条 confirm 审核日志。hdd-review-batch.json 保留审核前版本，hdd-review-result.json 保存授权、完整编号、确认结果和时间。测试、docs、golden 和 milestones 的范围遵循原任务。

## 8. 本次明确的来源口径

先提交 6555cb0 的失败回归，再实现 source_exposures.py。STX 仅对明确的单一业务白名单使用 fixed 年报合并营收；非 USD、未知币种、未来披露、缺收入或非有限数值均拒绝。共享 glm-5.3 起草后按 M2 来源金额逐项校验，不把未审核的新候选自动确认。原有七条用户确认未改。

SKHY 读取 interim_results，按期间去重并选截止日可见的最近四季，季度间隔须 80–120 天，每季用 M2 FRED 历史可见汇率转换后相加；缺季度、重复季度、间隔断裂或缺汇率均标“无法检验”并保留具体原因。真实现有期间为 2025-03-31、2025-06-30、2026-03-31、2026-06-30，中间间隔 274 天，缺 2025 年第三、四季度，故不生成假 TTM。实际结果在 structured-exposures.json。

接口提供 graph CLI 的 structured 动作，可重复起草该两种有来源的暴露。新增断言同时验证合法四季、重述替换、未来版本不可见、非法单一业务及 JSON 请求/JSONB 来源日期序列化；原 12 个测试名不变。
