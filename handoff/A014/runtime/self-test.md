# A014 续二/续三：每日任务接入

这次解决服务器缺少 M7 日级判定/盘前复核、M5 估值、M4 纸面计划调度的问题。只改调度脚本、安装登记和离线测试；不改任何模块业务逻辑、规则 A、参数、表结构或需求。

- 先提交失败测试 78dbe97；另以 2896144、022a0ea 冻结 M4 原生窗口和可见进程/互斥任务范围的失败断言。修前输出见 red.xml、m4-winter-red.xml、workers-red.xml。
- 54 项 ops 离线测试通过，见 green.xml。包括夏令时/冬令时、周末和窗口边界、原有任务未丢失、按交易日查询依赖、M4 使用上一交易日评分、失败隔离、日志不带计划正文、M7 close/post 原生判定、当日marketstate实体行缺失拒绝运行（e6080fc先红）、成功/失败后重启不重跑、M7 专用连接缺失时拒绝借用其他角色、持仓与活动事件的盘前范围及报价时间上界。
- M3/M6 原 daily_modules 继续存在；新增 anomaly_daily、valuation_v1、paper_plan 三个常驻 worker，均由同一调度封装执行互不重叠的 --tasks。其他旧进程保留，不重复登记同一业务任务。
- M7：美东20:55至21:00之间，在同交易日 bars_full 和 market_structure 完成后调用既有 DatabasePanel.detect(close/post)、write_anomalies 和 run_recorded；过截止时刻不伪称按时运行。M7 已有失败记录也不自动重试。盘前复核按美东08:00调用既有 review_premarket，报价限制为该日04:00至注入 Clock 的当前时刻，缺报价/剩余sigma如实写 degraded。
- M5：美东22:30那轮，在行情和最新财报采集完成后调用既有 scheduled；沿用模块自身 job_runs 护栏。冬令时按 README 顺延。
- M4：调用既有 execution.cli.scheduled，保持其已验收的**北京时间20:00–20:30**窗口，不修改 frozen 业务入口的冬令时行为（M4 self-test 原有北京固定窗口回归也保留）。盘前复核则按 M7 的美东08:00，冬令时对应北京21:00；两者分别测试，没有修改时钟或拿两者当同一时刻。
- M7 writer 使用 INVES_COG_PERCEPTION_DATABASE_URL，M5 使用已存在的 INVES_COG_VALUATION_DATABASE_URL，M4 使用原交易连接；业务角色权限不混用。新增接口仅是部署私有配置和 worker 任务过滤；不在服务配置中放私有环境值。

本机全仓 blocking 为382通过、6失败：1项AF_UNIX bind被沙箱拒绝，1项缺SciPy，4项缺Docker。没有skip、修改门禁或把这次结果写为全通过；完整容器 make phase1-test 和权限探针须由准确 head 对应的 GitHub CI 验证。

部署证据与历史补算进展另在 agent-status:ops/status/A.md 回报。此 PR 未合并前不安装服务器新 worker；历史验证不调用模型，不把补算或进程存活当作真实按时成功。
