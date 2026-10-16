# M1 收尾自测报告

基线：main 3d7db6980c7898139a13c17636dcdbb761eb752c；冻结需求 M1 v8；日期：2026-10-16。本次为用户授权的北京时间 08:50 一次核对，沿用既有 PR #5，原 PR #3 已合并。

## 1. 本次实际检查

- 全仓 blocking：39 passed、5 deselected、0 skipped，9.64 秒，blocking.xml。
- 显式 INVES_COG_LIVE=1、-m phase1_live，且仅对 test_ingest_live_smoke 使用 --runxfail：1 passed、0 skipped，79.424 秒，live-smoke.xml。只在实际通过后删除 M1 这行 pending。
- 真实冒烟通过正式 Pipeline.runtime 执行：bars_full job 5288（交易日 2026-10-14），news_full job 5289（1,891 条）。它们属于显式冒烟，不计为 10-15 的准时调度。
- 原名测试、时钟注入、断网、包防火墙、模型白名单、权限及 golden 门禁通过；本次未修改实现、测试或门禁。先失败测试后实现的原历史保留。

## 2. 不变量与范围

I22 常规/半日市及缺交易正反断言、I28 官方索引 Accepted 契约保留。golden 通过 load_golden；没有修改 docs、golden、milestones，没有运行 Muse、连接其他项目数据库、增加账号或隧道。其他模块 pending 保留。

## 3. 验收条款

| 条款 | 当前结果 | 唯一最终证据 |
|---|---|---|
| AC-M1-01 | 本次全仓 39 项阻塞通过；干净容器 CI 以 PR #5 当前完整 SHA 为准 | blocking.xml |
| AC-M1-02 | 已验收的正式五日历史回补证据保留：73/73 日线，常规分钟合计及逐码达到原阈值，每日 24–116 秒。今日来源缺口单独披露，不将 81% 写成该门槛通过 | market-bars.json 的 formal_five_session_backfill |
| AC-M1-02b（非阻塞） | 时效通过：调度器 10-15 美东 20:20:04.533465 开始、20:20:58.848415 结束，耗时 54.31495 秒；20:30 看门狗实际为 ok。job 5280 原状态 degraded 保留 | market-bars.json 的 scheduler_evidence、service.json |
| AC-M1-03 | 原正式 startup_baseline 13,227 候选、1,294 入选保留；本次调度日常剔除后 1,292，startup_baseline=false、monthly=false，不冒称重新启动基线 | wide-universe.json |
| AC-M1-04 | 已验收的原文时间及五组真实转载审计保留，不同日期模板不误归根 | news-identity.json |
| AC-M1-05 | 已验收的十次 Accepted/session/reaction_day 对照保留；本次 submissions 实源任务失败如实列第 5 节 | sec-earnings.json |
| AC-M1-06 | 原真实断源/恢复及单站故障隔离证据保留；本次未写生产演示故障 | source-failure.json |
| AC-M1-07 | 不按重要性删信息，新增/去重及 R7 幂等原证据保留 | info-archive.json |
| AC-M1-08（非阻塞） | 原全量 166,685/166,685 有向量、去重输入失败 0；用户已决定 async-v1，未为耗额度重复处理 | embedding.json |
| AC-M1-09 | 七交易日 6,694 条分级及需求方抽查已验收；原证据保留 | news-tier-report.json |

## 4. 准时运行与真实分钟缺口

job 5280 的原始时间、状态、处理数和报告完整保存在 market-bars.json：日线 73/73、分页耗尽，常规分钟平均覆盖率 81.0151%、最低 80.2564%，因此数据质量状态仍为 degraded。只判 AC-M1-02b 的按时触发与完成通过，没有把缺失分钟补零、前填或改写成 99%。

数据库中 AAPL 常规分钟 316/390，缺美东 12:57–14:10 共 74 分钟。另一次直接请求同一官方 Alpaca SIP 端点，返回 HTTP 200、next_page_token=null，并同样缺这些时间戳；原始时间戳已冻结在 scheduler_evidence。未将未经核实的停牌原因当作结论。该运行缺口进入 backlog，不改已冻结的历史五日覆盖证据。

Supervisor 的 scheduler/watchdog 持续运行，caffeinate -i -s 进程在、AC 供电且两种防睡眠断言为 1。美东 20:30:16.946934 的真实看门狗日志为 ok。macOS 当前为登录自启，非无人登录冷启动；嵌入 worker 的 EXITED 是先前批量正常结束，不在本次重新启动。

## 5. SEC 时段核对：失败不冒充恢复

- sec_atom：正式 job 5287 成功处理 100 条。
- sec_index：正式 job 5286 在窗口内完成，状态 ok、0 条，保留实际零返回。
- sec_submissions：正式 job 5285 在美东 20:45:27 开始，HTTP transport failed after bounded retries，失败 0 行。
- 单条 Apple 官方 submissions 探针返回 HTTP 200。随后仅在允许窗口内做一次正式任务重试（job 5309，美东 20:56:27–20:58:55），已处理 1,744 行，但仍连接失败；source_health.SEC 为 degraded，last_success_at 仍 NULL。

全部原失败、部分进度和实际健康状态保留在 market-bars.json；没有用单条 200 或通过的 live 冒烟宣称完整 SEC 任务成功。没有超出美东 21:15 再发任务。当前 live 契约要求来源健康记录存在，不能将其测试通过解释为所有来源本日全部成功。SEC 运行缺口进入 backlog 供需求方复核。

## 6. 使用量及遗留

用户既有 key 保存在仓库外 .env，本次只读入进程环境，不输出 key、不索要新 key、不新增付费授权。嵌入使用量按 task=embedding 独立记账，缺 usage 仍为 NULL。D-14 主线已有实现，D-22 清理见 next-stage-audit.json；D-23 停止旧 embedding 列增量写仍为 M8 前待办，未冒称关闭。

本次收尾提交准时调度与真实 live 的证据；上述新实源缺口按冻结规则如实进 backlog，是否通过由需求方复核。milestones 仍由需求方填写。M2 收尾已通过并合并 PR #9，未重复实跑 M2；M3/M6 的验收和 M7 开工不属于本次自动核对。未创建后续自动化。
