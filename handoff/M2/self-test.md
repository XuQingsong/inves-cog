# M2 自测报告

模块：M2；文档：v5（main d273b28）；代码提交：a52325591f0a3dde63a050d564fbd97d98b2403f；日期：2026-10-15。

真实 59 行健康页、59 份档案、59 只修复差异和五份原文对照已附。分部合计已修复。AC-M2-06的Muse导入、F2历史复算及失败如实显示已满足；两次59只真实采集按v5拆为非阻塞AC-M2-06b。PR #4在M1合并后合入共享基线、CI绿后转正式。

## 1. Harness

K16 最终验证：M2 blocking **25 passed，7.56 秒，0 failed，0 skipped**，replay **1 passed，5.37 秒，0 failed，0 skipped**；临时联合 blocking **39 passed，8.25 秒，0 failed，0 skipped**，replay **1 passed，5.17 秒，0 failed，0 skipped**。命令仍为 `PYTHONPATH=src .venv/bin/python -m pytest -q -m phase1_blocking` / `phase1_replay`；完整结果附四份 *-k16.xml。M0 本地通信探针在允许 AF_UNIX 的正常环境执行，门禁、测试名和标记未改。

独立 Muse 回放 30×3、90 组、2,255 字段差异 0，输入及 oracle 冻结哈希不动。七日期末 FX、FX 日期索引、预算部分完成计数、PIT 年报推财年、获准辅助维度、旧分部缓存刷新、资产/利息不冒充利润及 FASB 缓存复用均保留测试先行提交。没有修改 docs/、golden 或 milestones；本机无 Docker，不把直接 pytest 冒充干净容器 CI。

## 2. 不变量

| 不变量 | 测试 |
|---|---|
| I10 | test_revenue_tag_gap：标准/新增营收标签正反断言 |
| I11 | test_q4_derived_from_annual：Q2/Q3/Q4 累计推单季及缺数 |
| I12 | test_companyfacts_lag：三天边界、已有 accession、原件解析 |
| I33 | test_segment_extraction / recast / mapping_pending：批准的精确辅助轴放行，其余混合维度拒绝，1% 容差、原件缓存与审核状态；同轴层级和原件表格口径/权重均附正反用例；实源59只审计与离线测试分开登记 |
| I34 | test_consensus_derived_pit：可见时点、同财年、窗口、低基数；实际历史复算见下表 |

## 3. pending 和 milestones

15 项 blocking 和 legacy replay 已移除，只保留原名 test_fundamentals_live_smoke。R4/R5/R7 不是笼统缺 key：阻塞待补仅为M1合并后的共享基线及CI；Yahoo成功采集属于AC-M2-06b非阻塞、期限M5提交验收之前；K15/K16分别见Q-M2-18/19。没有改其他模块行或 milestones。

## 4. 逐条验收自评

| 条款 | 自评 | 证据 |
|---|---|---|
| AC-M2-01 | 本模块离线和独立回放通过；干净 CI 等 M1 修复基线合入 | blocking-v3.xml、replay-v3.xml、legacy-replay.json；M2 不越权复制 M1 的 M0 迁移清单修正 |
| AC-M2-02 | 59 只真实差异已形成；LITE/BE/COHR 均可打分 | v3-differences.json.gz、v3-coverage.json：59 行，两套字段差异和健康码均附 |
| AC-M2-03 | 真实 59 行通过健康一致性检查 | v3-health.json：不可打分但无原因 0 行，可交易但三个核心字段缺失 0 行；外国标的不可交易 |
| AC-M2-04 | 存在覆盖及已采分部营收合计达标 | v3-coverage.json、k16-original-audit.json.gz：51/54 = 94.44%；缺 NOW/XOM/CRWD；59只原件复核成功，segment_sum_mismatch 由14家降至0，1%阈值不变 |
| AC-M2-05 | 五只真实 10-Q 营收/利润对照均一致 | v3-segment-spot.json：AMD、WDC、NVDA、MSFT、COHR，原文 URL/sha256/显示金额/scale/context_ref 均附；独立读取 HTML inline facts，与实例数字逐条比，不用夹具冒充 |
| AC-M2-06 | v5阻塞条款通过：Muse导入、F2历史复算、失败如实显示 | 原 database-verification.json：两次导入均 180 行/30 只，哈希和幂等核对；v3-f2-history.json：5 只×3 日期 15 组窗口独立复算一致。真实两次共识均 59 次失败/0 成功；旧版及隔离最新版都实测 crumb 403、quoteSummary 429，不称为缺 key，不换源 |
| AC-M2-06b（非阻塞） | 尚未完成；期限为M5提交验收之前 | Q-M2-20：需求方已确认部署机腾讯云首尔AS132203出口被Yahoo封禁；不重试、不换源，待用户选代理或Alpha Vantage。v5-consensus-failure.json保留既有两次59只失败、59行窗口及健康状态；仅180条Muse快照，没有假造yfinance快照 |
| AC-M2-07 | 59 份真实 F3 档案已生成 | v3-profiles.json.gz；三个区块都有数据或明确理由。共识缺当日快照如实标记，不把 Muse 的 30 只充作 59 只当日采集 |
| AC-M2-08（非阻塞） | 审核队列接口/录音验证通过；实源草稿尚未生成 | M1 合并前按 Q-M2-14 用显式同接口替身；真实分部 mapping_gap 保留，不把替身称为 glm-5.3 真实映射 |

## 5. 边界与破坏性验证

未改测试名/标记，不使用 skip；测试无真实 key、网络或系统时间，LLM 用录音。七日含边界、跨年与八日过期，未来 filed/captured_at 排除，假日记录实际报价日。主轴加获准辅助轴可取数，地域/产品/仿造 namespace 与三维混合仍拒绝；资产和利息不会混作利润。空 reviewer/未知图谱节点拒绝，未确认映射不进入 segment_std。未知 taxonomy 版本正常下载，已存在原件复用；不是断网门禁放宽。

## 6. 实源结果与偏差

ASML 最初失败为本项目 FX 历史只导入 2009 年后，而源公司披露包含 2007 年金额。已用同一 FRED 源补入 2006 年起的 real-time 版本，重跑写入真实状态，没有以 NULL 隐藏 FX 缺口；v3-fx-history.json、v3-real-runs.json。外国 6-K 中部分原件无 XBRL 的历史缺口逐号保留。

原件 taxonomy 反复网络刷新曾使解析 50 只达到 30 分钟预算。真实原件缓存审计已完成 59 只，正式路径也补缓存复用和失败先行测试；不将缓存审计写成一次新的完整联网财报采集。原超时失败日志不改写。

K16 已按用户答复实施。利润专用行保留 NULL 营收并排除于营收加总，确有营收元素但 nil 的行仍触发未知金额门禁；同轴父成员按 definition 关系保留为 summary。含内部交易的分部口径按同一原件表格区块和列选择抵销，权重引用原件括号或 gross/intersegment/net 顺序。GE 的原件表明确列出 Corporate & Other revenue 175 百万美元，引用原件标签、期间及 XBRL 金额锚定单位，未用合并额减分部额反推；原利润专用行仍保留。ORCL 的营收分类明细继续排除，避免把已有营收分解重复加总。GEV 例外只适用于获准公司 namespace 和成员，三维子分部及其他公司相似成员仍拒绝。59只审计的原件哈希、逐行纳入/排除理由、权重和前后结果见 k16-original-audit.json.gz。

## 7. 新问题

K15、K16 均已获用户答复并实施；没有待答复的分部规则问题。Q-M2-20已明确Yahoo 403/429原因为部署机腾讯云首尔AS132203出口被封，不是调用频率；停止重试，等用户选定代理或Alpha Vantage，不擅自换源或伪造快照。M1 验收合并后，M2 再按共享文件并集规则合入 main、重生成 uv.lock、复跑 CI。


## 8. K16 测试先行证据

失败测试提交：3686ace（汇总/利润专用/括号权重）、3467b2b（GEV限制）、bb4ff6a（编码声明/不同区块/计算组件）、33ae338（colspan及2023计算关系）、b045c6c（无inline标签原件表）、fb5fc76（ORCL分类明细不得重复加总）。实现分别在353982f和a523255提交。所有断言加在原 test_segment_extraction 内，辅助函数不新增收集名；测试输入为docs之外的手写临时副本。错误期间、未锚定单位、三维混合、错误公司/namespace、reported nil、缺少标准核心营收计算关系均有拒绝断言。

最终全量原件审计：59/59完成、失败0；原14家合计异常全部消除，ORCL重复计数回归也已修复。没有修改docs、golden、milestones、M0门禁或容差。


## 9. v5验收与合并顺序

main d273b28已合入，Q-M2-18/19对应开发K15/K16，docs保持main原样。v5-consensus-failure.json为只读生产库检查，不发Yahoo请求：source_health为degraded，note已补入Q-M2-20确认的出口封禁诊断（只更新note，原尝试时间/状态/计数不变，无新Yahoo请求）；真实两次采集均59只失败，59只window_status有当日失败原因，consensus_snapshot只有180条muse_import，yfinance为0；未以历史导入冒充当天快照。

等待M1验收合并后，再合入新的main：pending各留本模块行，CHANGELOG和fixtures MANIFEST取并集，pyproject依赖取并集，uv.lock用uv lock重新生成。CI绿后把PR #4转正式「[M2] 提交验收」；当前M0迁移清单CI断言的修正只由M1带入，M2不越权复制。
