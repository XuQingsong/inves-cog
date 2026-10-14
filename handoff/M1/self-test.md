# M1 自测报告

模块：M1；文档：v2；代码提交：7d566bc038b5c557988da7e4a215f00a9fd2df6e；日期：2026-10-14。

结论：代码、运行入口与离线验证已完成，真实接入已有下列证据；连续运行和原文抽查等阻塞证据尚未齐备，不能判定模块全部验收通过。PR 保持草稿供审查，未合并 main。

## 1. Harness

- `.venv/bin/python -m pytest -q -m phase1_blocking --junitxml=handoff/M1/blocking.xml`：24 项通过，失败/错误/skip 均为 0，6.874 秒；[blocking.xml](blocking.xml)。包含 M0 门禁与 M1 原名 14 项 blocking。
- 临时联合工作区合并两个模块的依赖、夹具清单及 pending，使用两个最新实现：39 项 blocking 通过、0 skip，7.520 秒；[integration-blocking.xml](integration-blocking.xml)。联合 replay 1 项通过；[integration-replay.xml](integration-replay.xml)。该临时合并未推送、未替代正式 PR。
- 新功能及本轮修复都保留先失败测试、后实现的独立提交。最近包括空正文转载归并、官方 PCR 保留、401 不重试、共享接口、调度截止与队列持久化。
- [database-verification.json](database-verification.json)：本项目独立 PostgreSQL + pgvector 真实写入；1024 维向量、版本记录、计数恒等式通过，夹具事务回滚。[extraction-queue-verification.json](extraction-queue-verification.json)：先持久保存原文，再回放抽取更新同一行；模型失败不丢原文、不重复增加采集计数。
- `git diff --check` 通过；docs/、golden、milestones 未修改。本机没有 Docker，直接 pytest 结果不冒充干净容器 `make phase1-test`；最终提交的 GitHub CI 另行核对。

## 2. 本模块不变量

| 不变量 | 结果 | 证据 |
|---|---|---|
| I22 盘后行情 | 绿 | test_bar_window_to_20et / from_04et、test_post_close_null_when_no_trade；按每个 ticker 最后有成交分钟取盘后价，无成交保留 NULL，半日市及合规分钟不误伤 |
| I28 财报反应时间（数据部分） | 绿 | test_earnings_reaction_day / fallback_flag；golden 经 load_golden，休市 closed、半日市、夏冬令时及索引缺口均覆盖 |

## 3. pending 与 milestones

移除本模块已通过的 14 项 blocking，保留原名 test_ingest_live_smoke；目前真实缺口是全部源运行/SEC 覆盖和规定嵌入接入，不能用离线夹具将其转绿。R4 两个 LLM 已真实验证；R7 已收到并导入，90 日新闻 bootstrap 已完成。没有改 milestones，也没有删除其他模块的 pending。

## 4. 逐条验收自评

| 条款 | 自评 | 证据与限制 |
|---|---|---|
| AC-M1-01 | blocking 通过 | blocking.xml；最终 CI 状态见 PR。live 尚在 pending |
| AC-M1-02 | 单日真实补采覆盖达标，五日及按时完成未证明 | bars-real-verification.json：73/73 日线，全部分页完成；常规分钟合计 99.9649%、最低 98.9744%；此为 10 月 13 日补采，结束超过 20:45 ET，status=degraded，不能作为按时完成或连续五日证据 |
| AC-M1-03 | 实源诊断入选数达标，启动快照待定时运行 | wide-real-verification.json：13,228 候选，1,302 入选，各排除原因有统计；使用真实前一已完成收盘做诊断、外层事务回滚，不伪造历史月初集合；K18 启动例外已获批准 |
| AC-M1-04 | 时间/归并机制通过，规定原文抽查未证明 | news-real-verification.json：10 条真实供应商 URL、发布时间和首次见到时间；这不是原文 ≤1 分钟核对表，也不是五条真实转载验收；空正文不错误归为同一个 root |
| AC-M1-05 | 三个真实时间冲突样例已冻结，十次抽查未证明 | tests/fixtures/phase1/m1/sec_acceptance_conflict.json；三次官方索引 Accepted，其中含盘后财报；夏令时 JSON 字面值差 8 小时、冬令时差 10 小时。按 K17 只认索引美东转 UTC，JSON 原样留证，不写死偏移。59 只十次历史财报原文抽查尚未完成 |
| AC-M1-06 | 故障隔离验证通过，部分真实源仍未接通 | test_trends_unavailable_marked / test_llm_extraction_failure_degrades；database-summary.json：新闻、App Store、Trends、FINRA、CBOE、FRED 为 ok；CompanyIR 的 403 为未接通，Alpaca 因迟到为 degraded；未运行的 SEC 等源不虚构健康记录 |
| AC-M1-07 | 计数恒等式、先存后抽取和真实回补已证明 | news bootstrap 第二段：24,038=23,199 入库+839 去重；累计真实新闻库 60,509 行，bootstrap_complete=true；history-import-verification.json：27,624=27,624+0。首次回补在 30 分钟限制后停止，保存进度再续跑，不伪称单次全部完成 |
| AC-M1-08（非阻塞） | 标注探针通过，嵌入不通过 | 十条真实标注 0 失败；十条嵌入均失败。Token Plan 嵌入返回 404，现有 key 在 DashScope 兼容端点返回 401 invalid_api_key。需匹配业务空间/地区且获该模型权限的嵌入地址和 key；不换模型，不把 60,499 条待抽取原文算成成功 |

真实来源补充：FRED 六系列 73,384 个历史版本；FINRA 5,082 行，CBOE 23 类，App Store 免费和畅销各 100，Trends 8 个关键词。修复前 FINRA 400、CBOE 解析失败的初始输出与修复后的输出分别留存，不以初始失败掩盖最终状态。R7 Form 4 18,335 行、VIX 9,289 行，重复导入新增 0；原始导出未提供的 filed_at/accession/历史发布版本明确标记未知，不伪造可见时间。

## 5. 边界与破坏性验证

保留原名断言，覆盖应拒绝和应放行两面：非普通股/完整合法股本、缺 ADV/完整 20 日、相同与不同正文（保留数字和否定）、空正文/原始 source ID、官方 PCR/没有官方比值才计算、401 不重试/5xx 允许重试、未知任务/注册任务、非法实体 ID/合法图谱 ID、索引缺失/真实合法 Accepted。M0 断网/时间/模型/golden 等门禁随 blocking 运行；没有修改标准答案或禁用门禁。模块文档没有独立编号的破坏性清单，不另造已完成记录。

## 6. 已知限制与依据

K17：索引 Accepted 为时间权威；索引暂缺记录 URL/错误并重试，不生成未核实反应日。K18：第一次空库可在当日收盘后建 startup_baseline，之后月初重算、每日只剔除。监控实体初版 config/monitored_entities.yaml 待需求方审核。M0 修改仅为已授权的权限矩阵和独立负例/迁移清单/模型品牌域识别，其他 M0 内容不动。

运行入口已实现：`python -m inves_cog.ingest.cli run --tasks ...`；`schedule` 按美东时间轮询并启动独立抽取进程；`enrich --once` 补处理已保存原文；`health` 输出健康记录。数据库已经运行，但没有安装开机服务，也没有将未运行的定时服务称为已部署。

## 7. 新需求问题与待证事项

已提出问题均有答复并实施；本次不新增未经答复的业务规则。剩余为真实验收证据：五交易日按时采集、十新闻和五转载原文核对、十次真实财报时间核对、全部源运行，以及嵌入接入。证据不足的条款保持待验，不写入 milestones。
