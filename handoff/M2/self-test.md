# M2 自测报告

模块：M2；文档：v2；实现提交：018d168814d5270d998105369d860e93fa450cd2；日期：2026-10-14。

结论：业务实现与离线验证完成；真实覆盖证据尚未完成。本报告申请代码审查，不声称所有阻塞验收条款已经通过。

## 1. Harness

- `.venv/bin/python -m pytest -m phase1_blocking --junitxml=handoff/M2/blocking.xml -q`：25 passed，4 deselected，6.950 秒。包含 M0 门禁和 M2 原名 15 项 blocking；没有 skip，pending 棘轮正常启用。
- `.venv/bin/python -m pytest -m phase1_replay --junitxml=handoff/M2/replay.xml -q`：1 passed，28 deselected，6.07 秒。30 只 × 3 日期、90 组、2,255 字段，差异 0；[legacy-replay.json](legacy-replay.json)。输入及 oracle 哈希均核对，未修改冻结文件，未运行/导入/复制 Muse 代码。
- [database-verification.json](database-verification.json)：独立 inves_cog 数据库实际写入及 PIT 查找通过；夹具行在外层事务回滚。真实 Muse CSV.gz 导入两次均为 180 行、30 只、121 份 earnings_history。只离线读 CSV/COPY，不连接 quant。
- [fx-real-verification.json](fx-real-verification.json)：三币种真实 FRED 历史版本成功，2026-07-04 的有效报价日均为 2026-07-02；金额 100 仅为合成探针，不冒充公司财报。使用官方 output_type=1 的 real-time 行，避免将 output_type=3 的宽表误认成相同形状。
- `git diff --check` 通过。docs/、golden、milestones 没有修改。
- 本机未安装 Docker，因此没有将直接 pytest 称为 `make phase1-test` 的干净容器结果。M2 的旧 M0 基线还写死“只能有 M0 一个迁移”；该授权修复只在 M1 PR。M1 合并到 main 后，M2 必须合入并重新确认干净容器 CI。

临时联合工作区使用 M1 7d566bc038b5c557988da7e4a215f00a9fd2df6e 与 M2 018d168814d5270d998105369d860e93fa450cd2，39 项 blocking 通过、0 skip，7.520 秒；[integration-blocking.xml](integration-blocking.xml)。联合 replay 1 项通过；[integration-replay.xml](integration-replay.xml)。临时合并未推送。最新修复覆盖 graph.entity_id 的真实字段契约、分部合计与收入/利润的美元换算，以及确认/驳回对当前期间已缓存分部的即时生效；比较期间不误作当前期间，行 ID 不变。两次修复均保留先失败测试、后实现历史。

M2 最近干净环境 CI：[38532656679](https://github.com/XuQingsong/inves-cog/actions/runs/38532656679)。日志中 blocking 25 项通过；随后旧 M0 清单写死只有一个迁移而失败，该限定修复已授权放在 M1，不能在 M2 越权复制。

## 2. 不变量

| 不变量 | 结果 | 测试 |
|---|---|---|
| I10 营收新标签 | 绿 | test_revenue_tag_gap：旧标签正常不误伤，新标签缺口与 D1 修复 |
| I11 累计数推单季 | 绿 | test_q4_derived_from_annual：完整、缺季、6/9 月累计及标准答案 |
| I12 companyfacts 滞后 | 绿 | test_companyfacts_lag：第 2/3 天边界、已有 accession 不误标、实例来源 |
| I33 分部 | 绿 | test_segment_extraction / recast / mapping_pending：业务/产品/混合轴隔离、1% 边界、未确认禁用 |
| I34 共识 PIT | 绿 | test_consensus_derived_pit：未来 capture、窗口不足、3 日容差、同财年、低/零分母 |

## 3. pending 和 milestones

删除已转绿的本模块 15 项 blocking 和 1 项 replay。只保留 `test_fundamentals_live_smoke`，真实剩余原因是 M1 共享基线尚未合入 main，以及 59 只真实申报/分部验证尚未完成；R4/R5 接入已配置，R7 导出已收到。没有删除其他模块的行，没有改 milestones。

## 4. 验收自评

| AC | 自评 | 证据 |
|---|---|---|
| AC-M2-01 | 离线与 legacy 回放通过；干净环境 CI 待 M1 基线合入后复跑 | blocking.xml、replay.xml、legacy-replay.json |
| AC-M2-02 | 机制通过，59 只真实差异及 LITE/BE/COHR 真实可打分未证明 | checkpoint-data.json；D1–D5/D8 和影响矩阵测试 |
| AC-M2-03 | 59 行手写输入链路通过；真实 59 行未证明 | test_health_contract；可交易行核心字段非空、外国标的不可交易 |
| AC-M2-04 | 离线维度、抵销和容差通过；54 只真实覆盖率未证明 | test_segment_extraction；Arelle 本地桩 schema |
| AC-M2-05 | 尚未证明真实原文抽查 | checkpoint.md 中 AMD/WDC 分部明确为夹具 |
| AC-M2-06 | 真实 Muse 历史导入完成；59 只连续 5 交易日尚未形成 | database-verification.json；Muse 只有 30 只，不以此冒充 59 只 |
| AC-M2-07 | 59 份夹具 F3 通过；真实 59 份未证明 | test_health_contract，三个区块有数据或明确原因，3% 严格边界和指引原始 items |
| AC-M2-08 | 待审核/确认/驳回及板块过滤接口通过，页面属于 M10 | test_segment_mapping_pending；mapping.py |

## 5. 边界与破坏性验证

未来 filed/captured_at 不进入状态；未知 extractor 拒绝；单季缺失不补零；非 USD 无可见报价抛带币种、字段、期间、版本日和原因的 FXGap，停止金额写入；假日使用注明实际日期的期末聚合。图谱未知节点拒绝，空 reviewer 拒绝；未确认映射不可用于 segment_std；产品和混合轴不混入业务合计。已测合法标签、合法 180 天边界、正分母、1% 容差、严格 3% 不触发等“不误伤”方向。M2 文档没有另列破坏性自测清单，不虚构测试通过记录。

## 6. 已知限制与依据

Q-M2-14：M1 合并前用注入的同接口替身；没有自建 SEC/LLM 客户端或 job_runs/source_health 表。生产入口在 M1 基线可用后解析同一个客户端。Q-M2-7 的独立 oracle 已收到，等待 R7 不再用于该回放。Q-M2-8/12：旧导出没有的营收、coverage、目标 FY 等字段保留 NULL 与原因；F2 不用供应商 agoN 反推历史。用户 K14 答复只针对 FX，金融字段缺汇率不以 NULL 掩盖问题；其他允许的缺字段按原合同处理。

## 7. 需求问题

K14 的 FRED 方案已按用户答复实施并实测。K13 的共享基线问题已获得在 M1 修复的授权，等待 M1 合入；本模块没有越权改 M0。真实 5 日记录、59 只真实覆盖和分部原文仍为待验证事项，不列为已通过。
