# M7 自测

复跑输入是 `data/m7-export` 的导出，命令 `--source file`。成员在导出里从 2015-01-01 起不变，报告按「成员按导出日的名单回看」。Q-M7-15 删掉路径 B 的 4 个百分点分支，其余阈值没改。

B-007：文件模式和数据库模式原先不一致，有两个原因。一是数据库模式用 `marketstate.baskets` 的短窗口（导出只有 2026-07-01 起）计算收益 z，120 日文件模式的 z 不同，关注级抢在联动前面，`数据中心电力与散热` 被标成 `A_watch`，合并后把数据中心电力从 L3 抬到 L2。二是 `universe` 写死为 `pool`，广域股票 BAC、LQDA、MMED、PGR、U 被算进池内。现在两种模式都用同一套日线重算篮子；广域只取不在 `config/universe.yaml` 和篮子成员里的 `marketstate.daily`。行业和风格 ETF 只参与轮动，不当作广域个股。一致性测试是 `test_file_and_database_views_match`。

| 验收 | 结果 |
|---|---|
| AC-M7-01 | 合入 `origin/main` `e2c223c` 后，本地 `make phase1-test` 122 passed、12 deselected。其中 M7 blocking 12 个（含别名测试和 `test_file_and_database_views_match`）和 `test_case_detection` 通过。`test_anomaly_live_smoke` 仍留着，原因等待 R5 |
| AC-M7-02 | 四个案例只读冻结行情、篮子、宏观和 SIC。`src/inves_cog/perception/anomaly` 没有 `info_items` |
| AC-M7-03 | 最近 5 个交易日 2026-10-08、10-09、10-12、10-13、10-14 的收盘和盘后清单在 `handoff/M7/ac-m7-03.json`。每条有层次、篮子、成员、入口、数据质量。已按去掉 4 个百分点分支后的结果重出 |
| AC-M7-04 | 不在本次跑。只读库复跑用 `--source db`，连接串由调用方放在 `INVES_COG_DATABASE_URL`，仓库不保存 |
| AC-M7-05 | 2026-10-07 至 2026-10-14 有盘后价。指数盘后涨跌都小于 1%，不够 `C_abs`。盘后序列只有 6 个交易日，自身 120 日 z 为空，盘后篮子和个股都没有检出。合适的盘后例子留给 A 线在合并后补 |
| AC-M7-06 | 每条异常都有 `amplification`。踩踏、轧空和缺数由 blocking 测试覆盖。指数调整日历文件不存在，非到期日写「指数调整未接通」。月度期权到期按第三个周五 |
| AC-M7-07 | 非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 2.327（2208 个交易日，5139 条）。四项都过线。别名表在报告 `summary.basket_aliases`：`NAND/DRAM` → `memory`。`sector:XLF` 没有改判 |

四个案例相对第 7.1 节的补充：HDD、CPU、OpenAI 合作方的收益 z 都落在关注级（约 −2.2、+2.8、−2.4），入口有 `A_watch`。HDD 的篮子 `resid_z` 是 −3.02，CPU 是 +3.45，合并后严重级别成为 `alert`。10-14 的合作方篮子和同一天的路径 B 个股成员相交，合并后也是 `alert`。10-08 没有篮子异常。META 是个股 `alert`。DeepSeek 日的 AI 加速芯片方向向下，NVDA 在成员里。

未命中的 4 条非温和事件仍是：2023-03-10、2023-03-13 的 `sector:XLF`（当天命中的是 KRE，按任务不把 KRE 算成 XLF），2026-07-27、2026-07-29 的 `basket:NAND/DRAM`。这两天分别有 2 条和 5 条异常，篮子是软件、工业、AI 服务器、半导体设备，没有 `basket_id = memory`，所以别名表对不上。别名只在对象带有 `memory` 时命中。
