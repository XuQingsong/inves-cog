# M2 自测报告

模块：M2；文档：v3（main e7db5a9）；代码提交：10a1e191ea805dc15b2389730d6e4fd5820be93c；日期：2026-10-14。

真实 59 行健康页、59 份档案、59 只修复差异和五份原文对照已附。分部合计及 Yahoo 的两次真实采集尚未满足全部阻塞条款，PR #4 保持草稿，不提前称为验收通过。

## 1. Harness

最终 blocking / replay 命令为 `PYTHONPATH=src .venv/bin/python -m pytest -q -m phase1_blocking --junitxml=handoff/M2/blocking-v3.xml` 及相同命令的 phase1_replay / replay-v3.xml。最终 **25 passed，0 failed，0 skipped，7.52 秒**；replay **1 passed，5.87 秒**。临时联合 **39 blocking passed，8.46 秒**，**1 replay passed，5.85 秒**；附 integration-blocking-v3.xml / integration-replay-v3.xml。受限进程曾禁止 AF_UNIX bind，原 M0 本地通信探针因此失败；没有改门禁或 skip，改在允许本地通信的正常环境复跑并保留最终结果。

独立 Muse 回放 30×3、90 组、2,255 字段差异 0，输入及 oracle 冻结哈希不动。七日期末 FX、FX 日期索引、预算部分完成计数、PIT 年报推财年、获准辅助维度、旧分部缓存刷新、资产/利息不冒充利润及 FASB 缓存复用均保留测试先行提交。没有修改 docs/、golden 或 milestones；本机无 Docker，不把直接 pytest 冒充干净容器 CI。

## 2. 不变量

| 不变量 | 测试 |
|---|---|
| I10 | test_revenue_tag_gap：标准/新增营收标签正反断言 |
| I11 | test_q4_derived_from_annual：Q2/Q3/Q4 累计推单季及缺数 |
| I12 | test_companyfacts_lag：三天边界、已有 accession、原件解析 |
| I33 | test_segment_extraction / recast / mapping_pending：批准的精确辅助轴放行，其余混合维度拒绝，1% 容差、原件缓存与审核状态；真实合计缺口另列，离线绿不冒充实源全部正确 |
| I34 | test_consensus_derived_pit：可见时点、同财年、窗口、低基数；实际历史复算见下表 |

## 3. pending 和 milestones

15 项 blocking 和 legacy replay 已移除，只保留原名 test_fundamentals_live_smoke。R4/R5/R7 不是笼统缺 key：真实待补为 M1 合并后的共享基线、分部合计及 Yahoo 成功响应。没有改其他模块行或 milestones。

## 4. 逐条验收自评

| 条款 | 自评 | 证据 |
|---|---|---|
| AC-M2-01 | 本模块离线和独立回放通过；干净 CI 等 M1 修复基线合入 | blocking-v3.xml、replay-v3.xml、legacy-replay.json；M2 不越权复制 M1 的 M0 迁移清单修正 |
| AC-M2-02 | 59 只真实差异已形成；LITE/BE/COHR 均可打分 | v3-differences.json.gz、v3-coverage.json：59 行，两套字段差异和健康码均附 |
| AC-M2-03 | 真实 59 行通过健康一致性检查 | v3-health.json：不可打分但无原因 0 行，可交易但三个核心字段缺失 0 行；外国标的不可交易 |
| AC-M2-04 | 存在覆盖达标，合计不全部达标 | v3-coverage.json：51/54 = 94.44% 有分部或 single_segment；缺 NOW/XOM/CRWD；14 家 segment_sum_mismatch 明确列出，未改阈值、未凑数消红 |
| AC-M2-05 | 五只真实 10-Q 营收/利润对照均一致 | v3-segment-spot.json：AMD、WDC、NVDA、MSFT、COHR，原文 URL/sha256/显示金额/scale/context_ref 均附；独立读取 HTML inline facts，与实例数字逐条比，不用夹具冒充 |
| AC-M2-06 | Muse 导入及 F2 历史通过；两次 59 只共识成功采集未通过 | 原 database-verification.json：两次导入均 180 行/30 只，哈希和幂等核对；v3-f2-history.json：5 只×3 日期 15 组窗口独立复算一致。真实两次共识均 59 次失败/0 成功；旧版及隔离最新版都实测 crumb 403、quoteSummary 429，不称为缺 key，不换源 |
| AC-M2-07 | 59 份真实 F3 档案已生成 | v3-profiles.json.gz；三个区块都有数据或明确理由。共识缺当日快照如实标记，不把 Muse 的 30 只充作 59 只当日采集 |
| AC-M2-08（非阻塞） | 审核队列接口/录音验证通过；实源草稿尚未生成 | M1 合并前按 Q-M2-14 用显式同接口替身；真实分部 mapping_gap 保留，不把替身称为 glm-5.3 真实映射 |

## 5. 边界与破坏性验证

未改测试名/标记，不使用 skip；测试无真实 key、网络或系统时间，LLM 用录音。七日含边界、跨年与八日过期，未来 filed/captured_at 排除，假日记录实际报价日。主轴加获准辅助轴可取数，地域/产品/仿造 namespace 与三维混合仍拒绝；资产和利息不会混作利润。空 reviewer/未知图谱节点拒绝，未确认映射不进入 segment_std。未知 taxonomy 版本正常下载，已存在原件复用；不是断网门禁放宽。

## 6. 实源结果与偏差

ASML 最初失败为本项目 FX 历史只导入 2009 年后，而源公司披露包含 2007 年金额。已用同一 FRED 源补入 2006 年起的 real-time 版本，重跑写入真实状态，没有以 NULL 隐藏 FX 缺口；v3-fx-history.json、v3-real-runs.json。外国 6-K 中部分原件无 XBRL 的历史缺口逐号保留。

原件 taxonomy 反复网络刷新曾使解析 50 只达到 30 分钟预算。真实原件缓存审计已完成 59 只，正式路径也补缓存复用和失败先行测试；不将缓存审计写成一次新的完整联网财报采集。原超时失败日志不改写。

仍遵守严格单业务维度与已批准辅助成员。当前 14 家合计异常包含同轴的汇总成员/子成员、利润专用抵销行、其他未批准的经营分部辅助成员；具体原件事实见 questions.md，不自行放宽或给 NULL 填 0。

## 7. 新问题

K15 精确辅助轴已获用户答复并实施。新 K16 的原件汇总/抵销规则及 GEV 辅助成员需答复；等待时不扩大维度或改变营收加总合同。Yahoo 当前路由的 403/429 是实测响应；不反复重试、换源或伪造快照。M1 验收合并后，M2 再按共享文件并集规则合入 main、重生成 uv.lock、复跑 CI。
