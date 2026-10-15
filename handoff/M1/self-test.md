# M1 自测报告

基线：main c52fcc0，M1 v7 / T01-T02-round3；2026-10-15。需求方已在 `docs/phase1/acceptance/M1-report.md` 有条件验收通过。全部阻塞条款完成；AC-M1-02b 的下一次准时调度仍待真实窗口，AC-M1-08 全量补齐现已完成。最新完整 SHA 和 CI 链接在 PR #3 核验，不用旧提交的绿灯代替。

## 1. 测试与工程证据

本地 M0+M1 blocking：24 passed，8.42 秒，0 skipped，见 blocking.xml。原测试名、网络/Clock/权限/模型/golden 门禁保留；正反断言均测。用临时副本执行九项破坏性自测，全部命中预期红灯，真实 golden 不变。先失败测试后实现的 Git 历史保留。

最新 main 新增 golden/v18 目录使旧完整性快照把目录当文件，CI 因 IsADirectoryError 中断；24 项测试及干净环境断言本身已通过。失败测试 c3c0da1、修复 753dbea：递归计算相对文件名与哈希，仍检查前后完全一致，不改任何 golden 或 MANIFEST。Ruff 只查本 PR 改动文件，E/F/B/W/I/C901、行宽120、复杂度25；已有 M2 复杂函数由 M2 登记。

## 2. 不变量

I22 的常规/半日市和缺交易双向断言通过；I28 只认官方索引 Accepted，缺索引不生成未经核实的反应日。十次真实核对见 sec-earnings.json。测试不用真实 key、外网或系统时间；LLM 用录音。M1 十四项已退出 pending，只保留原 live 测试；未修改真实 milestones。

## 3. 逐条验收

| 条款 | 结果 | 唯一最终证据 |
|---|---|---|
| AC-M1-01 | 本地24项通过；最新完整SHA的干净容器结果见PR | blocking.xml |
| AC-M1-02 | 正式回补5个交易日，每日73/73日线，分钟覆盖满足99%/95%，24–116秒/日 | market-bars.json |
| AC-M1-02b，非阻塞 | 尚待10月15日美东20:20真实窗口；旧21:02补采不算准时 | market-bars.json、service.json |
| AC-M1-03 | 正式startup_baseline：13,227候选、1,294入选、六类排除原因，165.37秒 | wide-universe.json |
| AC-M1-04 | 10条原文时间、5组真实转载审计完成；不同日期财报日历短模板已分根 | news-identity.json |
| AC-M1-05 | 10次Accepted/session/reaction_day核对完成，59只submissions持久化 | sec-earnings.json |
| AC-M1-06 | 真实断源/恢复、坏一个官网URL其余4个继续、5站恢复；Fed/EIA三源分别20/12/16条、等级1 | source-failure.json |
| AC-M1-07 | 不按重要性删信息；新增/去重及R7幂等核对通过，过期同根结论已移除 | info-archive.json |
| AC-M1-08，非阻塞 | GET /models=200，DASHSCOPE_API_KEY与Token Plan key比较不相等，10条真实样本通过；当前166,685/166,685条全部有向量，缺失0；全量165,369个去重输入失败0 | embedding.json |
| AC-M1-09 | 7交易日6,694条：第2层2,975、第3层3,719、初筛5,207；累计2,951,723 token，新闻日日均421,674.71；需求方30+30抽查及3,719条关键词扫描已通过 | news-tier-report.json |

## 4. 常驻运行

Supervisor 管理 scheduler、watchdog 和可恢复 embedding worker；LaunchAgent 登录自启，异常退出自动拉起。已实际杀掉旧 scheduler，4秒内恢复新PID，证据见 service.json。独立 watchdog 在交易日美东20:30检查 bars_full 是否已有20:20后的开始记录，缺失在 source_health 标红；开始记录在业务运行前即持久化。

本机为macOS，当前自动启动范围是用户登录后；无人登录的冷启动不在当前安装范围，不能冒称系统级开机服务。caffeinate 防止通电时闲置休眠。下一次真实窗口为北京10月16日08:20，08:45前完成；用户已授权08:50一次自动核对、更新和推送。

## 5. 嵌入模型、用量与预算

按用户最新授权验证六个替代模型，未再消耗已耗尽的v3，也未关闭用完即停。v1/v2/v4/qwen在同一98文档、8查询小样本均命中第1名，样本不足以宣布质量胜者。qwen批量结果的index重复，现严格单条调用；async-v2两次小样本均逐条InternalError，不交付无效向量。async-v1完成全量两批，实际12,090,797输入token，全部成功；另10条探针690 token。

替代模型放在 ingest.info_embeddings，按模型、维数和输入哈希隔离；旧info_items.embedding继续仅代表v3/1024维，不能跨模型混算。所有新调用记入 ingest.llm_calls，task=embedding，条数、token、耗时和状态可分开汇总；缺usage如实为NULL。全库七种信息均覆盖，不按新闻层级筛选。

历史v3抵扣前估算0.6589435元不是账单。原每月20元、历史另20元预算仍为方案，没有自动付费授权；实际免费额度由供应商停止开关约束。库存已补齐，不为了清空免费余额制造重复调用。自动v3开关继续关闭，后续新增数据的免费模型批量补齐与付费生产模型选择留待运行配置确认。

## 6. 已知限制与合并

除非阻塞AC-M1-02b外，关闭模块前还必须通过真实 live smoke 并退出 pending；本次不得把迟到补采改写为准时。M1按main中验收授权，在最新CI通过后用merge commit合并；milestones由需求方填写。M2已按用户新授权合入M1并完成第二轮六项，不再等待M1合并才开发。没有新的待答复问题。

## 7. 第三轮收尾现状（未冒充完成）

- 第10项：显式 `-m phase1_live` / `INVES_COG_LIVE=1` 的真实冒烟于北京时间14:41执行，日线73只、新闻938条；32.22秒后因 SEC/SECAtom/SECDailyIndex 健康记录不全失败，见 live-smoke.xml。pending 的 xfail 不算通过，未删除该行。之后正式 SECAtom 任务真实处理100条，另两项因尚未到20:45–21:15 ET窗口返回not_due；未伪造时钟、健康码或来源成功。pending原因已更正。
- 第11项：常驻scheduler已补入sec_submissions/sec_index/sec_atom。15:12现场确认caffeinate两项防睡眠断言均有效，AC供电；覆盖本次20:15–21:00 ET窗口，详见service.json。真实 bars_full 尚须在北京10月16日08:20触发并于08:45前完成；本报告不新增虚构job_runs。Mac需保持供电和开盖，登录自启不等于无人登录的冷启动。
- 第12项：独立数据库已创建继承role_web的inves_cog_review，只读登录和写权限否定检查通过；连接说明及凭据已在仓库外单独交付，不写入Git。
- 已授权10月16日08:50只执行一次自动核对；须等真实SEC健康记录和live smoke通过后才删除pending，再更新唯一market-bars.json并在PR #3留言。尚未完成的这两项不写成验收通过；milestones仍由需求方填写。
