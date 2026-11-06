# A-032 数据期望与时限依据

当前配置共 59 项。时间均为美东；release_days 为数据日期后日历天偏移。代码调度能证明计划时间，不能证明来源按时成功。标注估计或待核实的来源缺少连续实际到位分布，保留为未完成验证，不能据此宣称 T1 全通过。

|数据|频率|截止/宽限|日期偏移|依据|
|---|---|---|---|---|
|监控池日线|trading_day|20:45 / 30分钟|0|src/inves_cog/ingest/market.py:schedule_times full_deadline=20:45 ET|
|宽池日线|trading_day|20:45 / 30分钟|0|src/inves_cog/ingest/runtime.py:wide_universe 20:20；20:45 日线截止|
|指数与半导体基金日线|trading_day|20:45 / 30分钟|0|src/inves_cog/ingest/market.py:schedule_times full_deadline|
|监控池盘中快照|intraday:1|09:30 / 20分钟|0|src/inves_cog/ingest/runtime.py:intraday_snapshots 1 分钟；仅在交易时段查最近窗口；ingest/intraday.py合同延迟15分钟，宽限20分钟包含报价延迟与轮询余量|
|宽池盘中快照|intraday:5|09:30 / 20分钟|0|src/inves_cog/ingest/runtime.py:wide_snapshots 5 分钟，09:30–16:00；ingest/intraday.py合同延迟15分钟，宽限20分钟包含报价延迟与轮询余量|
|新闻新增|intraday:120|09:30 / 0分钟|0|A-032 §1 交易时段两小时无新增；runtime.py:news_poll|
|波动率日线|trading_day|20:45 / 30分钟|0|src/inves_cog/ingest/runtime.py:vix_daily 20:45 ET|
|利率信用与跨资产日线|trading_day|17:00 / 30分钟|0|src/inves_cog/flows/backfill.py:backfill_yahoo_px/published_at 17:00 ET；这是现有代码的估计发布时间，缺少连续到位分布，验收前待核实|
|看跌看涨成交比|trading_day|19:00 / 30分钟|0|scripts/schedule_flows.py:cboe_pc 19:00 ET|
|短期波动与偏斜|trading_day|17:00 / 30分钟|0|flows/backfill.py:published_at(cboe_idx)=17:00；估计发布时间，待实际到位核实|
|基金份额|trading_day|09:00 / 30分钟|1|scripts/schedule_flows.py:22:30开始采集，次日09:00仍陈旧则degraded；采用最终期限，不把启动时间当到位期限|
|期权日成交量|trading_day|07:00 / 30分钟|0|scripts/schedule_flows.py:OCC 次日 07:00 ET，查询过去交易日|
|期权未平仓量|trading_day|07:00 / 30分钟|0|scripts/schedule_flows.py:OCC 次日 07:00 ET|
|期权链|trading_day|16:30 / 30分钟|0|scripts/schedule_flows.py:eod 16:30 ET|
|空头成交量|trading_day|18:00 / 30分钟|0|FINRA 官方日文件页承诺当日18:00 ET发布；UD-A-59新增入口|
|期货持仓|weekly|15:30 / 30分钟|3|flows/backfill.py:backfill_cftc release_at 周五15:30，报告日周二|
|央行与财政流动性|weekly|16:30 / 30分钟|1|src/inves_cog/flows/backfill.py:published_at_fred（现有估计发布规则，待到位记录核实）|
|货币基金规模|weekly|16:30 / 30分钟|3|src/inves_cog/flows/backfill.py:published_at_fred（现有估计发布规则，待到位记录核实）|
|金融压力周报|weekly|10:00 / 30分钟|6|src/inves_cog/flows/backfill.py:published_at_fred（现有估计发布规则，待到位记录核实）|
|隔夜逆回购|trading_day|17:00 / 30分钟|0|flows/backfill.py:published_at_fred rr pontsyd=17:00 ET|
|隔夜融资利率|trading_day|08:00 / 30分钟|0|flows/backfill.py:published_at_fred SOFR 下一交易日08:00 ET|
|准备金利率|trading_day|00:00 / 30分钟|0|flows/backfill.py:published_at_fred IORB 当日00:00 ET；政策利率不应作逐日变化检查|
|金融压力日报|trading_day|09:00 / 30分钟|0|flows/backfill.py:published_at(ofr_fsi) 下一交易日09:00 ET（估计规则，待核实）|
|晴雨表日报|trading_day|20:45 / 30分钟|0|scripts/schedule_flows.py:_barometer 等待当日日线20:20后；日线截止20:45|
|晴雨表盘中|intraday:15|09:45 / 15分钟|0|scripts/schedule_flows.py:_intra_slots 09:45起每15分钟|
|财报状态|trading_day|21:45 / 30分钟|0|scripts/schedule_financials.py:21:15–21:45；财报是事件驱动，不要求每日新财报，按股票索引读取截至当日最新状态|
|一致预期新增快照|trading_day|23:59 / 30分钟|0|scripts/schedule_consensus.py 全天轮询受每日额度限制；按当日成功批次检查，不强制所有股票每日更新|
|估值区间|trading_day|22:30 / 30分钟|0|scripts/schedule_daily_modules.py:22:30 ET 依赖财报与日线后运行|
|增长透支判断|trading_day|22:30 / 30分钟|0|scripts/schedule_daily_modules.py:22:30 ET 依赖财报与日线后运行|
|规则评分|trading_day|22:30 / 30分钟|0|scripts/schedule_daily_modules.py:22:30 ET 依赖财报与日线后运行|
|纸面计划|trading_day|09:05 / 30分钟|0|trading/execution/cli.py:08:35–09:05 ET 轮询，截止09:05|
|日线采集任务|trading_day|20:45 / 30分钟|0|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|波动与宏观采集任务|trading_day|20:45 / 30分钟|0|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|基本面采集任务|trading_day|21:45 / 30分钟|0|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|晚间评分估值任务|trading_day|22:30 / 30分钟|0|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|纸面计划任务|trading_day|09:05 / 30分钟|0|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|市场归因日报任务|trading_day|21:45 / 30分钟|0|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|归因跟踪任务|trading_day|00:00 / 30分钟|1|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|归因标签任务|trading_day|07:30 / 30分钟|1|runtime.py / schedule_daily_modules.py / attribution.morning:stage_bounds 对应任务窗口|
|融资账户月报|monthly|17:00 / 60分钟|21|flows/backfill.py:published_at(finra_margin) 月末观察日+21天17:00；现有估计规则，验收前需核实|
|事件日历采集任务|trading_day|06:00 / 30分钟|0|ingest/runtime.py:06:00每日|
|早间预采集任务|trading_day|08:10 / 30分钟|0|ingest/runtime.py:08:00–08:10窗口|
|盘前检查任务|trading_day|08:30 / 30分钟|0|scripts/schedule_daily_modules.py:08:00–08:30|
|申报与索引任务|trading_day|21:15 / 30分钟|0|ingest/runtime.py:20:45–21:15|
|行情结构任务|trading_day|20:45 / 30分钟|0|scripts/schedule_daily_modules.py:20:45依赖日线|
|每日异动任务|trading_day|21:10 / 30分钟|0|scripts/schedule_daily_modules.py:20:55–21:10|
|全量新闻任务|trading_day|20:20 / 30分钟|0|ingest/runtime.py:20:20每日|
|一致预期采集任务|trading_day|23:59 / 30分钟|0|schedule_consensus.py全天受额度限制轮询|
|晨间覆盖任务|trading_day|08:30 / 30分钟|0|m9.yaml:08:00–08:30发布窗口|
|影子评估任务|trading_day|09:05 / 30分钟|0|shadow/scheduling.py:等纸面计划，M4截止09:05|
|次日复盘任务|trading_day|07:30 / 30分钟|1|perception/review/schedule.py:_DAILY与D+1 01:00–07:30窗口|
|盘中快照采集任务|intraday:1|04:00 / 15分钟|0|ingest/runtime.py相应任务的真实轮询间隔与窗口|
|宽池快照采集任务|intraday:5|09:30 / 15分钟|0|ingest/runtime.py相应任务的真实轮询间隔与窗口|
|新闻巡检任务|intraday:10|10:00 / 15分钟|0|ingest/runtime.py相应任务的真实轮询间隔与窗口|
|新闻采集轮询任务|intraday:10|00:00 / 15分钟|0|ingest/runtime.py相应任务的真实轮询间隔与窗口|
|申报轮询任务|intraday:10|00:00 / 15分钟|0|ingest/runtime.py相应任务的真实轮询间隔与窗口|
|全部定时任务失败记录|intraday:10|00:00 / 0分钟|0|现有调度器任务名注册表；包括条件性周月任务，只报真实失败或超时，不把待机视为缺跑|
|每周复盘任务|weekly|07:30 / 30分钟|1|perception/review/schedule.py:due_tasks，周/月最后交易日D，D+1 01:00–07:30|
|每月复盘任务|monthly|07:30 / 30分钟|1|perception/review/schedule.py:due_tasks，周/月最后交易日D，D+1 01:00–07:30|

原始只读汇总位于本次 handoff 的来源证据；只含公开市场序列和任务到位汇总，不含账户、连接信息或日志原文。
