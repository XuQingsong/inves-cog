# B 线回报

> 只由 B 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## B-008  进行中  2026-10-16 23:22 北京

- 草稿 PR #18 head `38e8471`。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。
- 估值倍数类联动停在市场层，进入基本面核查会拒绝。供给、需求、竞争、客户融资仍可进入。东芝走查以供给进入核查。
- 经营证据的四项反例仍在 `f559023`，等需求方独立复核。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:12 北京

- 已读 main `31e8ceb` 对 `a028e59` 的四项反例。草稿 PR #18 head `f559023`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。
- 覆盖人数 NaN、修订人数无穷大、修订人数超过覆盖人数、EPS 变化 NaN，都保持条件风险。恰好 30% 和 3% 仍通过。空证据的条件风险不能靠普通赋值改成支持；截止日使用时会再核验。合法结构化证据仍能走到已验证。等需求方按这个 SHA 独立复核。
- `test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:04 北京

- 草稿 PR #18 head `7dbbca3`。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。`make phase1-cases`：1 passed，147 deselected。
- 空新闻路径已从 pending 删除。四个案例在标明 synthetic、新闻为空时状态都是「已发现·原因未明」，不调用模型。这不是真实源判定。
- `test_case_attribution` 继续 pending。真实冻结新闻仍缺 10-08 FT 年化营收、09-19 至 09-21 开盘前的 Muse 榜单、R1 或登顶。不开始下一条。

## B-008  进行中  2026-10-16 22:55 北京

- 已读 main `5ce0e6e` 上的经营证据预检和 M8 v7。草稿 PR #18 head `a028e59`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：137 passed，10 deselected。
- 经营已验证不再接受单独的 filing、股价、资金流、社交热度、市场共识度或二次命中。公司一级材料要有可定位引用，并且是 8-K 指引变更或电话会定量表述。EPS 修订要至少 30% 分析师同向、当年共识变化至少 3%、方向一致。产业数据要两个独立来源根。缺字段、未来材料、已证伪材料不通过。约束项仍未知时，另一条合格证据可以支持，未知项保留。截止日不能直接传入「支持」。
- 东芝走查用的是标明 synthetic 的 8-K 指引变更，不是真实公告。`test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 22:45 北京

- 草稿 PR #18 head `ed694dc`。没有合并进 main。本地 `make phase1-test`：136 passed，10 deselected。
- 感知表写入走调用方传入的连接，不打开数据库地址。广域异常只写回捞和报告，状态改成已记录。已评分但没有引用的候选会拒绝。一次性测试库里 `role_perception` 写入十张归因表成功，空引用被约束拦住，事务已回滚。`role_ingest` 插入被拒绝。没有 GRANT ingest，没有写共用库。真实补证入库仍停在 `Repository.put_info`。
- `test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。三处缺口仍缺冻结夹具。不开始下一条。

## B-008  进行中  2026-10-16 22:34 北京

- 草稿 PR #18 head `f2ddf45`。没有合并进 main。本地 `make phase1-test`：134 passed，10 deselected。
- 回放打标：`published_at` 不晚于回放时点、但 `first_seen_at` 更晚，标成「后补录历史复盘」，当时未采集，也不把向量算成当时已有。东芝 10-02 发布、10-14 才见到，在 10-02 当天是后补录；到北京 10-15 09:15 已可见，但没有向量时间戳时 `vectors_then` 为假。CPI 的 `first_seen_at` 在 10-15 14:35+08，09:15 的回放仍是后补录。
- `test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。三处缺口仍缺冻结夹具。下一步：感知表写入只在一次性测试库验证。真实补证入库仍停在 `Repository.put_info`。不开始下一条。

## B-008  进行中  2026-10-16 22:24 北京

- 草稿 PR #18 head `bb5fc2f`。没有合并进 main。本地 `make phase1-test`：133 passed，10 deselected。
- 已看到用户批准的导出分支 `data/m8-export` `cd02bdd`。核对后本机临时副本已删除。导出文件没有进入本 PR，也没有进入 main。
- 缺口在 `handoff/M8/source-gaps.md`。能对上标题的有东芝扩产、TDK 磁头、CoreWeave 债券收益率、巴克莱下调 Dell / HPE / NetApp、当天 CPI 同比 3.7% 对预期 3.6%。对不上的有 10-08 FT 约 500 亿美元年化营收、09-19 至 09-21 开盘前的 Muse 榜单、DeepSeek R1 或登顶。2026-09 至 10 月新闻最早 `first_seen_at` 在 2026-10-14，更早的异常日只能标成后补录历史复盘。巴克莱三条和 CPI 的 `first_seen_at` 在 2026-10-15 14:35+08，北京 10-15 09:15 的回放还看不见。
- 合成标题只检查案例方向。10-09 仍不能当作 10-14 之后的二次命中。`test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。下一步：等冻结夹具补上这三处缺口后再开案例测试。不开始下一条。

## B-008  进行中  2026-10-16 22:14 北京

- 草稿 PR #18 head `d42b06f`。没有合并进 main。本地 `make phase1-test`：132 passed，10 deselected。迁移在一次性测试库里建表成功。
- 新增 `migrations/phase1_m8_0001_attribution.sql`：回捞、说法、候选、联动事件、三轨、二次命中、冲击分解、系统性标签、标的代码、解释报告。没有 GRANT ingest，没有写共用库。
- 东芝中期走查是合成夹具，不是冻结新闻。候选引用日经扩产，机制为供给。2026-10-06 的 TDK 只做二次命中。生命周期从已发现走到已验证·有影响。报告写明终结原因，并保留未完成的约束项。标的代码为空，因为这条不是估值倍数连带、叙事冲击未变或原因未明。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。不假定 `data/m8-export` 已存在。下一步：把另外三个案例的候选排序接到同一份报告契约上，仍用合成或录音，等冻结新闻再开案例测试。不开始下一条。

## B-008  进行中  2026-10-16 22:09 北京

- 已读 `ops/answers/B-008.md`。草稿 PR #18 head `eaa3dae`，已合入 `origin/main` `c8fee63`。没有合并进 main。本地 `make phase1-test`：130 passed，10 deselected。
- 二次命中要求 `published_at` 晚于异常起点。2026-10-08 和 2026-10-09 对 2026-10-14 的 OpenAI 异常只作背景。负例已写进 `test_second_hit`。M8 v6 第 7.1 节仍写 10-09 做二次命中；`docs/` 和 golden 未改，冲突记在 `handoff/M8/kickoff.md` 第 12 节。
- 缺 EPS 共识或覆盖家数不是「未下修」。缺价格、基本面或联动状态时不生成情绪标签。条件风险报告写「截止日仍未知」、未知项，并且 `operating_impact_proven` 为假。
- 说法抽取和候选生成用录音。广域异常不调用模型。补证真实入库仍停：只打算走 M1 已有的 `Repository.put_info`，没有新增 ingest 写权限，也没有写共用库。`data/m8-export` 尚未按已到仓库处理。
- main 补上的两条 v6 pending 登记，对应测试在本分支已经转绿，合并时没有放回 pending。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。下一步：解释报告把东芝案例走到截止日所需的夹具，以及感知表迁移只在一次性测试库验证。不开始下一条。

## B-008  进行中  2026-10-16 21:59 北京

- 规则切片已推到草稿 PR #18，head `dc78efe`。没有合并。本地 `make phase1-test`：128 passed，10 deselected。
- 新转绿：`test_retrieval_recovers_low_rank_item`、`test_five_dims_rules`、`test_tracks_and_deadline`、`test_divergence_labels`、`test_systemic_event_tag_requires_level12`、`test_unexplained_recheck_5d`、`test_anomaly_contract`。低排序榜单按实体重合进入前 40，并被候选引用。截止日结果按复述第 6 节落入生命周期。只有四级信源时系统性标签为「无」。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。等冻结新闻和录音，不编造现场调用，不连接共用库。
- 下一步：说法抽取、候选生成和解释报告。不开始下一条。不等这条 head 的 CI 才写下一阶段。

## B-008  进行中  2026-10-16 21:44 北京

- 规则切片已推到草稿 PR #18，head `7eb7614`。没有合并。本地 `make phase1-test`：121 passed，10 deselected。
- 已转绿：`test_implied_magnitude_rules`、`test_evidence_scores`、`test_time_alignment_late_news`、`test_candidate_validation`、`test_retrieval_background_window`、`test_embedding_model_isolation`、`test_market_confirmation_four_conditions`、`test_lifecycle_transitions`、`test_second_hit`、`test_search_budget`、`test_verified_not_from_market_evidence`。golden 的隐含幅度和证据分全部命中。阈值在 `config/params/p-2026.10/m8.yaml`。
- 仍在 pending：`test_anomaly_contract`、`test_retrieval_recovers_low_rank_item`、`test_five_dims_rules`、`test_tracks_and_deadline`、`test_divergence_labels`、`test_systemic_event_tag_requires_level12`、`test_unexplained_recheck_5d`、`test_case_attribution`、`test_case_no_news_unexplained`。
- 下一步：继续这些测试和实现。不开始下一条。不等这条 head 的 CI 才写下一阶段。

## B-008  进行中  2026-10-16 21:34 北京

- 草稿 PR #18：https://github.com/XuQingsong/inves-cog/pull/18 ，分支 `phase1/m8-attribution-tracking`，head `bdb5ad8`。复述在 `handoff/M8/kickoff.md`。没有合并。没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- 没有必须停的问题。复述第 6 节按规格执行：截止日结果落入生命周期的方式、`search_daily_budget = 200`、向量只用 `text-embedding-async-v1` / 1536、M7 对象先用已验收夹具。要改写 `ops/answers/B-008.md`。
- D-28：三处都还在，但不改变 M8 要读的已入库关系和篮子 id。`draft_ticker` 的健康标签、多 L2 覆盖、STX/SKHY 硬编码列为 backlog，本模块不改 M6。
- 下一步：先提交失败的 blocking 测试和冻结夹具，再实现。不开始下一条任务。

## B-008  已收到  2026-10-16 21:30 北京

- 任务：M8 建连归因与三轨跟踪。先写开工复述和草稿 PR，分支 `phase1/m8-attribution-tracking`。没有「必须停」就直接开发。
- 依据：`origin/main` `2165c29`；`ops/control.md` 中 B 为「运行」。M8 用 v6。不连共用库，不改 `docs/`、golden、milestones，不合并。M7 尚未进 main，按已验收契约和夹具开发，不把未合并的 M7 实现混进本分支。
- 下一步：读 T08、M8 v6、M7 输出契约和 M6 图谱接口，写 `handoff/M8/kickoff.md`。

## B-007  已完成  2026-10-16 18:08 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `3102373`。没有合并。已合入 `origin/main` `e2c223c`，`MANIFEST.sha256` 和 `CHANGELOG.md` 自动合并，两边都保留。没有改阈值，没有改 M6，没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38885054082 （PR，phase1-blocking，122 passed，12 deselected，33.46s）。同头 push：https://github.com/XuQingsong/inves-cog/actions/runs/38885047902 。本地 `make phase1-test` 同样 122 passed、12 deselected。M7 blocking 12 个，含一致性测试 `test_file_and_database_views_match`。`test_case_detection` 通过。`test_anomaly_live_smoke` 仍等待 R5。
- 差异原因：`marketstate.baskets` 只从 2026-07-01 起。数据库模式用这段短窗口算收益 z，和文件模式 120 日 z 不是同一个数，关注级抢在 `A_linked` 前面；`数据中心电力与散热` 变成 `A_watch`，合并后把数据中心电力从 L3 抬到 L2。另外 `universe` 写死为 `pool`，BAC、LQDA、MMED、PGR、U 被算进池内。现在两种模式都用同一套日线重算篮子。广域只取不在 `config/universe.yaml` 和篮子成员里的 `marketstate.daily`。行业和风格 ETF 只参与轮动。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）四个数不变：非温和查全率 0.9459459459459459（70/74），样本外 0.9512195121951219（39/41），对照日篮子异常 0，平均每天对象 2.327445652173913（2208 个交易日，5139 条）。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。
- 已自行决定：无。
- 下一步：无。不合并。不开始下一条。

## B-007  进行中  2026-10-16 18:06 北京

- 实现已推到 PR #11，head `3102373`（先合入 `origin/main` `e2c223c`，`MANIFEST.sha256` 和 `CHANGELOG.md` 自动合并，两边都保留）。没有改阈值，没有改 M6，没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- 差异原因：`marketstate.baskets` 只从 2026-07-01 起。数据库模式用这段短窗口算收益 z，和文件模式 120 日 z 不是同一个数，关注级抢在 `A_linked` 前面；`数据中心电力与散热` 变成 `A_watch`，合并后把数据中心电力从 L3 抬到 L2。另外 `universe` 写死为 `pool`，BAC、LQDA、MMED、PGR、U 被算进池内。
- 现在两种模式都用同一套日线重算篮子。广域只取不在 `config/universe.yaml` 和篮子成员里的 `marketstate.daily`。行业和风格 ETF 只参与轮动，不当作广域个股。2026-10-14 文件模式仍是 2 条池内（含 `A_linked`，数据中心电力仍是 L3）；补上当日广域日线后，这 5 只是 `universe = wide` 的 L4，池内两条不变。
- 一致性测试：`test_file_and_database_views_match`。本地 `make phase1-test`：122 passed，12 deselected。M7 blocking 12 个，`test_case_detection` 通过。
- AC-M7-07（`--source file`）四个数不变：非温和查全率 0.9459459459459459（70/74），样本外 0.9512195121951219（39/41），对照日篮子异常 0，平均每天对象 2.327445652173913（2208 日，5139 条）。
- 下一步：等这条 head 的 CI。绿了再写已完成，并删除本机 `/tmp/m7-export`。不要重做实现。

## B-007  已收到  2026-10-16 17:40 北京

- 任务：M7 再修。数据库模式和文件模式不一致，违反 Q-M7-8。在 PR #11 上按 `config/universe.yaml` 和篮子成员划分池内 / 广域，查明篮子层差异并消除，加一致性测试，合入最新 main，重跑文件模式 AC-M7-07。
- 依据：`origin/main` `d339bff`；`ops/control.md` 中 B 为「运行」。不改阈值，不改 M6，不连库，不改 `docs/`、golden、milestones，不合并。
- 下一步：读 `data/m7-export` 的 `stored-marketstate/`，对照 2026-10-14 的两种快照。

## B-006  已完成  2026-10-16 17:12 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `b529480`。没有合并。已合入 `origin/main` `3f5d476`，冲突只在 `MANIFEST.sha256` 和 `CHANGELOG.md`，两边都保留。没有改 `docs/`、golden、milestones，没有改 M6，没有连接或写入共用库。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38878632674 （PR，phase1-blocking，109 passed，9 deselected，32.69s）。同头 push：https://github.com/XuQingsong/inves-cog/actions/runs/38878624666 。本地 `make phase1-test` 同样 109 passed、9 deselected。M7 blocking 11 个（含别名测试），`test_case_detection` 通过。`test_anomaly_live_smoke` 仍等待 R5。
- Q-M7-15：路径 B 不再用 4 个百分点分支，`m7.yaml` 已去掉 `path_b_gap`。其余阈值没改。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 2.327（2208 个交易日，5139 条）。四项都过线。
- 别名表：`NAND/DRAM` → `memory`。写在复跑代码和报告 `summary.basket_aliases`。`sector:XLF` 没有改判成 KRE。2026-07-27、07-29 仍未命中，因为当天 2 条和 5 条异常里没有 `basket_id = memory`。2023-03-10、03-13 的 `sector:XLF` 仍未命中。
- AC-M7-03 已按新结果重出，在 `handoff/M7/ac-m7-03.json`。自测在 `handoff/M7/self-test.md`。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。
- 已自行决定：无。
- 下一步：无。不合并。不开始下一条。

## B-006  进行中  2026-10-16 17:10 北京

- 实现已推到 PR #11，head `b529480`（先合入 `origin/main` `3f5d476`，冲突只在 `MANIFEST.sha256` 和 `CHANGELOG.md`，两边都保留）。路径 B 不再用 4 个百分点分支，`m7.yaml` 已去掉 `path_b_gap`。别名表只有 `NAND/DRAM` → `memory`，写在复跑代码和 `handoff/M7/ac-m7-07.json` 的 `summary.basket_aliases`。`sector:XLF` 没有改判。
- 本地 `make phase1-test`：109 passed，9 deselected。M7 blocking 11 个，`test_case_detection` 通过。
- AC-M7-07（`--source file`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 2.327（2208 个交易日，5139 条）。四项都过线。2026-07-27 和 07-29 仍未命中 `basket:NAND/DRAM`：当天 2 条和 5 条异常里没有 `basket_id = memory`。XLF 两天仍未命中。
- 下一步：等这条 head 的 CI。绿了再写已完成，并删除本机 `/tmp/m7-export`。不要重做实现。

## B-006  已收到  2026-10-16 17:00 北京

- 任务：M7 验收修复。在 PR #11 的分支上删除路径 B 的 4 个百分点分支（Q-M7-15，`m7.yaml` 去掉 `path_b_gap`），复跑程序加验证集篮子别名表（至少 `NAND/DRAM` → `memory`，Q-M7-16），合入最新 main，重跑 blocking、`test_case_detection`、`--source file` 的 AC-M7-07 和最近 5 天清单。
- 依据：`origin/main` `3f5d476`；`ops/control.md` 中 B 为「运行」。B-005 验收不通过是因为每天 3.33 个对象。不改别的阈值，不改 M6，不连库，不改 `docs/`、golden、milestones，不合并。
- 下一步：先改 `test_path_b_relative`，让 4 个百分点不再命中，确认测试失败后再改实现。

## B-005  已完成  2026-10-16 14:48 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ea089ff`。标题改为「[M7] 提交验收」，已取消草稿。没有合并。没有改 `docs/`、golden、milestones，没有改 M6，没有连接或写入共用库。迁移文件 `migrations/phase1_m7_0001_anomalies.sql` 只在一次性测试库里应用过，共用库留给 A 线在合并后执行。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38863086547 （phase1-blocking，75 passed，9 deselected，31.51s）。本地 `make phase1-test` 同样 75 passed、9 deselected。M7 的 10 个 blocking 测试通过，`test_case_detection` 通过。`test_anomaly_live_smoke` 仍留在 `pending.txt`，等待 R5。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 3.328（2208 个交易日，7349 条）。前三项过线。3.328 高于每天 2.5 的上限。多出来的主要是路径 B 的 4 个百分点分支，约每天 1.3 条只因个股和主 L3 留一收益差达到 4 个百分点、自身涨跌达到 3%。阈值没有下调。
- AC-M7-03：最近 5 个交易日 2026-10-08、10-09、10-12、10-13、10-14 的收盘和盘后清单在 `handoff/M7/ac-m7-03.json`。AC-M7-05：盘后价只从 2026-10-07 起，序列只有 6 个交易日，自身 120 日 z 为空，没有合适的盘后例子，留给 A 线在合并后补。自测逐条写在 `handoff/M7/self-test.md`。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。四个案例窗口留在 `tests/fixtures/phase1/m7/`。
- 已自行决定：无新决定。HDD、CPU、2026-10-14 的收益 z 落在关注级，又和 `|resid_z|≥3` 或路径 B 成员合并，严重级别按规则成为 `alert`，入口仍保留 `A_watch`。这是按冻结阈值改期望，不是改阈值。
- 下一步：无。不合并。不开始下一条。

## B-005  进行中  2026-10-16 13:48 北京

- 测试先红：`8f0f7ed` 提交了失败的 blocking 测试和四个案例窗口夹具。检测代码还没写。

## B-005  已收到  2026-10-16 13:40 北京

- 任务：在 PR #11 上开发 M7。先红后绿。不连库，不执行迁移，不改 M6、`docs/`、golden、milestones，不合并。
- 依据：`origin/main` `344deab`；`ops/control.md` 中 B 为「运行」。M7 v8 已冻结。K01 只计 `close`+`pool` 合并后对象；K02 迁移只授予 `job_runs` 的 INSERT/UPDATE；K03 轮动按答复 A，主题轮动是 `alert`。
- 下一步：读 `data/m7-export` 的 README，先提交失败测试和四个案例夹具。

## B-004  已完成  2026-10-16 13:16 北京

- 草稿 PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ac7c252`。复述在 `handoff/M7/kickoff.md`。没有写实现，没有改 `docs/`、golden、milestones，没有改 M6，没有合并。
- 必须停，等答复后再写代码：
  1. AC-M7-07 每天的异常对象，我倾向只计 `close` 且 `universe = pool`、合并之后的对象。把盘后和广域算进去会超过每天 2.5 个。
  2. `role_perception` 对 `ingest.job_runs` 只有 SELECT。我倾向只给这张表补 INSERT，任务名 `anomaly_detect` 和 `premarket_review`。
  3. 轮动单独命中时的 `severity`。我倾向风格价差 `|z| ≥ 3` 为 `alert`，只有行业极差 ≥ 4 为 `watch`。
- 数据申请（不含凭证，不含新闻；导出放 PR 分支 `handoff/M7/export/`，合并前删除）：
  1. `ingest.bars_daily`：篮子成员加 SPY、QQQ、IWM、RSP、11 只行业 ETF、SMH、IGV、KRE、MTUM、VLUE；列 `ticker, trade_date, open, high, low, close, volume, post_close, adj_factor, source`；2017-01-03 至 2026-10-14。
  2. `ingest.macro_observations`：`VIX_CBOE`、`VIX3M_CBOE`、`VIXCLS`、`DGS2`、`DTWEXBGS`、`DCOILWTICO`；列 `series_id, observation_date, value, units, realtime_start`；同一日期。
  3. `graph.baskets` 全表，成员保留生效区间。
  4. `ingest.issuer_profiles` 的 `ticker, sic`，范围是日线里出现的代码。
  5. `ingest.short_interest`：池内代码，`publish_date` 2018-01-02 至 2026-10-14；缺的不要填 0。
  6. `graph.cluster_suggestions` 有行才导。
- 已自行决定：见复述第 6 节。没有连接工厂或阈值之外的新决定。
- 下一步：停下。不开始实现。

## B-004  已收到  2026-10-16 13:10 北京

- 任务：M7 开工复述。只写 `handoff/M7/kickoff.md`，开草稿 PR，分支 `phase1/m7-anomaly-detection`。提交后停下，不写实现。
- 依据：`origin/main` `4c92710`；`ops/control.md` 中 B 为「运行」。用户已于 2026-10-16 批准开工（G1）。B-003 已通过，PR #8 已合并（`38510bc`）。
- 下一步：读 T07、M7 v7、验证报告、golden 77 个事件，以及 M6 的输出表和 Q-M6-15、Q-M6-18。复述三条路径、数据接口、数据申请和 AC-M7-07 复跑方式。

## B-003  已完成  2026-10-16 12:26 北京

- 已把最新 `origin/main` `b0f5eb1`（含 M3 合并 `9bbf151`）合进 PR #8。head `c144899`。没有合并 PR。
- 冲突只动了三个文件。`pyproject.toml` 依赖取并集，保留 `scipy>=1.14,<2`，其余与 main 相同。`uv lock` 已按这份依赖重算，`uv.lock` 没有变化。`tests/fixtures/phase1/MANIFEST.sha256` 两边条目都保留，Harness `validate_frozen` 通过（162 条，无缺、无多余、无哈希不符）。`tests/harness/CHANGELOG.md` 只追加，M6 `draft.json` 与 M3 `timeline.json` 两行都在。
- blocking：本地 `make phase1-test` 65 passed，7 deselected，1 warning，19.43s，退出码 0。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38850453859 （PR，65 passed / 7 deselected / 22.15s）。push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38850448970 。
- 已自行决定：无。没有改 `docs/`、golden、milestones 里原有内容；main 带进来的文档和 M3 代码原样保留。
- 下一步：无。不开始 M7。

## B-003  已收到  2026-10-16 12:21 北京

- 任务：把最新 `origin/main` 再合进 PR #8。不合并 PR，不改别的文件。
- 依据：`ops/control.md` 中 B 为「运行」。B-003 写明 B-002 第 1–5 项已通过，第 6 项取消。
- 下一步：解决 `pyproject.toml`、`tests/fixtures/phase1/MANIFEST.sha256`、`tests/harness/CHANGELOG.md`，跑 blocking。

## B-002  已完成  2026-10-16 12:21 北京

- 需求方在 B-003 中确认第 1–5 项通过。第 6 项按 Q-M6-20 取消：B 线不写共用库，三天重算改由 A 线在 PR #8 合并后执行。
- 交付仍是 PR #8，head `d5d0587`，CI https://github.com/XuQingsong/inves-cog/actions/runs/38848165567
- 已自行决定：无。

## B-002  阻塞  2026-10-16 11:59 北京

- PR #8，head `d5d0587`。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38848165567 （push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38848160877）。本地 `make phase1-test`：53 passed，6 deselected，1 warning，19.53s，退出码 0。
- 新增测试：`test_l3_same_as_l2_drops_theme_factor`（相同成员 → `m+s`、`l3_same_as_l2`、`beta_t` 为空；不同 → `m+s+t`）、`test_sic_review_additions`、`test_draft_all_does_not_share_one_connection`（复现原来 3 个线程叠在一条连接上，修完后深度为 1；有连接工厂时每个线程一条新连接）。
- 冲突：`src/inves_cog/llm/transport.py` 按任务名分开保留。`segment_mapping_draft` 仍是 `max_tokens=4096`、`reasoning_effort=low`；`graph_seed_draft` 和 `exposure_draft` 仍是 `8192` 和 `low`。模型名没改。分支已合入 `origin/main` `0035c26`。
- 第 6 项：阻塞：等待数据库连接信息。要重算 2026-10-12、13、14 并写入共用库的 `marketstate`。这台环境到不了 Mac 上的 `127.0.0.1:25432`，现有 `inves_cog_review` 又只能读。需要一份能写 `marketstate`、不写 `ingest` / `fundamentals` / `trading` 的连接，放在未跟踪的 `.env`，不提交。
- 已自行决定：无。没有连接工厂时 `draft_all` 改为串行；命令行传入工厂后才并行，每个线程自己的连接。
- 变更：无新表、无新数据源。因子口径和 SIC 映射按已经写进文档的 Q-M6-18、Q-M6-19。
- 下一步：1–5 已在 PR #8，不合并。等连接到位后只做第 6 项，不重做前面的修复。

## B-002  已收到  2026-10-16 11:40 北京

- 任务：M6 合并前修复（PR #8，分支 `phase1/m6-graph-baskets-marketstate`）。不合并 PR。
- 依据：`origin/main` `0f6371f`；`ops/control.md` 中 B 为「运行」。验收报告有条件通过。
- 下一步：合入 main 并解决 `transport.py`；Q-M6-18 先红后绿；补 `sic_to_etf.yaml`；`draft_all` 每线程一条连接；跑 blocking。第 6 项重算共用库需要可写的 `marketstate` 连接，当前只有一份到不了的只读说明。

## B-001  已完成  2026-10-16 11:08 北京

- `make phase1-test`：在 `origin/main` `273be4a` 上退出码 0。**39 passed**，5 deselected，1 warning，**10.66s**。Python 3.11.17。用的是脚本自带的一次性 docker compose 库，没有连生产库。M6 还在 PR #8，不在这条 main 上，所以这 39 个是 M0–M2 的 blocking，不是 M6 的 11 个。
- 复述：B 线做感知和解释，顺序是 M6 验收后的修复、M7、M8。M7 在每个交易日收盘后发现个股、篮子、行业、大盘的异常，对应目标 A1。M8 给每个异常找候选原因、证据和置信度，对应目标 A2、A3。代码只写 `inves_cog.perception`（含 `graph`）和 `inves_cog.marketstate`；`ingest` 只读，例外只有 M6 文档已经授权的采集。不改 A 线的 `trading`、`valuation_v1`，不改 `docs/`、`golden/`、`milestones.txt`，不合并 PR（用户批准后由需求方合并）。必须停的情况：跨模块表结构或接口、golden、规则 A 或交易行为、新数据源或付费、key 或权限、不可逆删改数据，以及仓库里的定时服务和共用库迁移。一次只做信箱里还没「已完成」的最小编号；`ops/control.md` 里 B 为「暂停」就停。
- PR #8 印象（只读，head `acf4856`，分支 `phase1/m6-graph-baskets-marketstate`，没有改）：价格层在 `inves_cog.marketstate`，按留一篮子、含截距、信号日之前 120 日的 SVD 回归算剩余涨跌，轮动和 v5 警戒分开；图谱在 `inves_cog.perception.graph`，原文切片、无引用就丢、审核日志和已确认视图是分开的。schema 在 `migrations/phase1_m6_0001_graph_marketstate.sql`，授权的采集收在 `ingest/market_structure.py`。main 上这两个包仍只有空 `__init__.py`。风险大的地方：`draft_all` 默认 3 个线程共用一条数据库连接；同一 ticker 有多条 L2 时 `active_baskets` 后写覆盖先写；`draft_ticker` 把所有异常收成 degraded，和「没有年报」分不开；STX 单一业务和 SKHY 四季 TTM 写死在图谱服务里；`handoff/M6/` 里多份证据是单行 JSON，diff 不好看。
- 疑问：这台机器没有生产库 URL 和 API key。本次测试不需要，所以没有停。下次要读共用库或跑 live，需要用户把值给我，我放进未跟踪的 `.env`，不提交。文档和 M6 v6 没有要停下来的疑问。
- 用户决策 UD-B-01：用户说每次做完任务后开启定时任务，监控 `ops/inbox/B/` 里还没完成的任务，有就直接开始开发。打算照做，但只作为这个 agent 的唤醒：每 10 分钟看一次信箱（与 A 线 UD-A-01 同一间隔），仍按 README 第 3 节一次只做一条；B 为「暂停」就什么也不做。不在仓库里加定时服务，不改调度代码。复用同一个定时器，不在每次完成时再挂一个。
- 已自行决定：无。
- 下一步：没有下一条信箱任务。不碰 PR #8，等需求方发 B-002。

## B-001  已收到  2026-10-16 11:02 北京

- 任务：入门（搭环境、读文档、复述）。不写业务代码，不开 PR。
- 依据：当时的 `origin/main` `d4afbaa`；`ops/control.md` 中 B 为「运行」。
- 下一步：读任务书 §4、M6 v6、M7 验证报告、M2 验收报告；跑 `make phase1-test`；读 PR #8。
