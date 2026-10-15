# M6 自测报告

模块：M6；冻结需求 v6（main be2137e）；日期：2026-10-15；实现提交：dd2d4c6（后续证据补充见 PR 提交历史）。

## 1. Harness

先提交 11 项实际失败测试（70537a6），再实现；后续输出有界、盘后和审核、中文标识各有独立失败提交。原名 12 个测试全部存在，11 blocking + 1 live。

- 全仓 blocking：50 passed、6 deselected，15.76 秒，blocking.xml。
- M6 blocking：11 passed，2.66 秒，blocking-module.xml。
- 显式 phase1_live、INVES_COG_LIVE=1：1 passed，93.04 秒，live-smoke.xml；本次真实覆盖 1,306 只，包括 59 只标的。只允许 live 联网，CI 不运行。
- 当前完整提交 dd2d4c6a13bcb51f96709f6ed2a3af410ec074c0 的 GitHub CI 成功：https://github.com/XuQingsong/inves-cog/actions/runs/38749207365 。后续提交须重新核对完整 SHA。

## 2. 不变量、pending 与 milestones

M6 无独立关闭的不变量；M0 导入防火墙、价格隔离、网络和时钟门禁同时通过。M6 的 12 行已在实际转绿后全部删除；其他模块 pending 保留。milestones.txt 未修改。

## 3. 验收条款（仍有未完成证据，PR 保持草稿）

| 条款 | 自评 | 当前证据 |
|---|---|---|
| AC-M6-01 | 通过 | 11 blocking 全绿，v5 marketstate golden 全命中；blocking-module.xml。 |
| AC-M6-02 | 部分 | 58/59 只每只至少 3 条引用关系；HD 首轮为空、单次重试得到 8 条。SKHY 无规定的年度申报，未编造引用，见 backlog.md。已建 16 个 L2、13 个 L3，AMD 主 AI 加速芯片，同时属于 CPU，graph-seed-task.json。 |
| AC-M6-03 | 补证中 | OpenAI 合作方美元暴露及 HDD 原件核对结果见后续 exposure 文件，不以任意融资金额代替业务暴露。 |
| AC-M6-04 | 待现场审核 | API 和 CLI 已提供按篮子列出、确认、驳回、修改及版本检查；开发未自动确认生产候选。 |
| AC-M6-05 | 通过，待需求方独立复核 | 2026-10-12/13/14 的 AMD、ANET、WDC 共 9 组；independent-qr-check.json 最大误差 9.02e-17 < 1e-6；real-three-days.json 保存全窗口、因子和回归输出。独立 QR 使用导出的因子，不调用生产回归函数；原始价格可由只读库查询。 |
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

backlog.md 列 SKHY 年度源缺口和现场审核；按 §4.7 不因此修改冻结文档或停掉其他开发。不修改 docs/golden/milestones；不运行 Muse；M7 尚未开工。正式常驻部署参数与审核入口在 handoff 交付，价格作业以美东时区配置，不能把显式回补当作准时运行。
