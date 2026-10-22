# M8→M9 合同消费自验（独立消费层阶段）

依据：已合并 main `6ee26bbbc52fc47ce8e88e4961d22378595dfa50` 的 A-015 补充一至六与 B036–B041 快照接口。
唯一 JSON SHA256：`72c05c6ed1fd793673ee4dd5ce572bb4f2d2e6eec49791cc59a07badd86a8fd3`。
JSON 由 main 合入，未编辑 docs。所有数据均为合同的合成输入，不是生产事件或持仓。
2026-10-22 20:47 北京重验：合同新增 `check_scope`，真实 M8 链路保留“无关系→纯共振”；evt-gap/NVDA 缺项仅作 M9 防御输入。原 M9 判定已符合，无业务规则修改；直接消费新版合同的15项测试通过，证据 `provider-scope-green.xml`。此前 up/down 版本的14项结果保留在 `provider-direction-green.xml`，不当作本次新head结果。

先失败提交：`4e6bc2ca954db6f46ce2f0ba343610d05af01919`，`provider-contract-red.xml` 为 10 failed / 2 passed；随后实现消费逻辑。
两项已有 A2 测试先通过：在原生发布截止后触发缺失处理，保留旧版本/生成时间，首次缺失不发布。没有改变调度门禁。

| 项 | 当前结果 | 测试和证据 |
|---|---|---|
| A1 | 合同消费与默认原生快照读取离线集成通过 | `test_a1_a3_a4_actual_contract_via_native_provider` 直接读取唯一 JSON，经 `scheduled(m8_provider=...)`，逐项消费 `expected_m9`，WDC/STX on、MU off、NVDA/AMD unknown。新增 `test_a1_pure_resonance_contract_is_off` 从同一JSON的 `expected_m9_pure_resonance` 取输入/预期，使用指定原事件经相同入口验证纯共振 NVDA off、无gap/无unknown，WDC/STX仍on、MU仍off；独立事件输入不混入evt-gap防御负例。未手抄期望值或加载未合并 B 代码。 |
| A2 | 通过 | `test_a2_incomplete_contract_retains_previous_generated_at`、`test_a2_first_incomplete_contract_has_no_overlay`；`test_incomplete_input_keeps_legacy_overlay_without_rewriting` 保留旧格式完整 payload。原 M4 `test_overlay_missing_marked` 仍验证缺失照常出纸面计划。 |
| A3 | 通过 | A1 同时断言 multiplier=1、stop_review_eligible=false、无订单/增买字段；`test_extended_delivery_rejects_inconsistent_diagnostics` 拒绝新增 buy 和不一致状态。 |
| A4 | 通过 | A1 对 `m8_completeness` 的 complete/source_events_asof/unknown_ticker_count/unknown_tickers 作精确比较；未知列表为 AMD、NVDA。 |
| A5 | 入口/离线隔离验证通过；真实五日数据未执行 | 新 `replay-m8` 入口调用已合并 `read_replay_snapshot`，只用 shadow 只读连接。合成五日存储由原生 `append_replay_snapshot` 生成，10-19 为空、其余为缺字段 unknown。输出为独立目录的 `replay_overlay_*.json` 封装（每份 replay=true、实际生成时间、overlay/来源/缺口），没有实时 FileDelivery 文件名；缺快照报告 unavailable/overlay=null。9项回放测试通过；未以合成输入冒称生产五日完成。真实 M8 回放仍等 B042 合并与费用确认。 |
| A6 | 本地最新70项相关回归通过，整仓以准确 head CI 为准 | 新版check_scope合同：`provider-scope-green.xml` 15 passed、Ruff check/format通过。此前 `provider-direction-green.xml` 14 passed、消费实现的 `provider-contract-green.xml` 58 passed / 3 deselected保留为历史阶段记录。本机 `make phase1-test` 明确因无Docker退出，未修改门禁、未宣称本地整仓通过。准确head CI链接由A状态及PR记录。 |

消费语义：缺失只来自 provider 的 `missing.fields`。不根据 null、deadline_on 或日期自行重判缺失。逐标的 exposure gap 即使标的不在 affected 中也保留该标的 unknown；展示字段缺失保留 NULL 和结构化 gap，但不阻断冷静期；direction 只在“已验证·有影响”时为判定字段。

多个事件仍按原冷静期并集：任一完整事件触发则 on；没有已知触发但有必需字段缺失则 unknown；全部完整且未触发才 off。某事件的未知不抹掉另一个完整事件已经成立的冷静期，全部 gap 仍随事件保留。没有新增买入、卖出或影子动作。

新增输出受原投递验证器约束，并兼容读取旧格式覆盖层。真实M8来源读取、数据库迁移、M9部署、M4时序与规则A均未改变；本阶段不等于模块验收或上线。

## 2026-10-22 已合并接口集成与 A5 入口

- 已继承 main 6ee26bb（含验收 merge3326a3b）；默认读取器保持使用现有 scoped shadow 账号，只读不可变快照表，不回退到可变事件表。fixture 使用原生 capture_if_ready 生成存储形态。`test_native_scheduled_default_reads_real_provider` 同时覆盖空日和真实非空字段缺口；`test_native_snapshot_field_gap_publishes_unknown_and_keeps_source_ids` 与 `test_native_missing_stage_snapshot_keeps_old_overlay` 明确区分逐字段 unknown 和整日不完整。权限失败不换账号的回归仍通过。
- 继承新读取器后原旧B035夹具真实2失败2通过，`immutable-integration-red.xml`；更新夹具/旧合同断言后 M9/M4 61 passed、3 deselected，`immutable-integration-green.xml`。不是业务逻辑失败后改成空夹具。
- 新 A5 回放测试先失败提交 `1d13d10`，5 failed（模块不存在），`m8-replay-red.xml`，后实现 `shadow/replay.py` 及 CLI `replay-m8`。新增路径重叠/未来或重复日期/已有证据目录/独立账号边界验证。最新 M9/M4 **70 passed、3 deselected**，`m8-replay-green.xml`；Ruff check/format通过。
- 扩展相邻 B036 数据库检查的一次本机结果为95通过、1项因Docker不存在失败、3 deselected，保留 `immutable-integration-local-environment.xml`；未改测试/跳过/门禁，不将该集合称全绿。干净容器整体结论以新完整head CI为准。
- 真实运行方式（仅在M8回放完成并获既有批准后）：`python -m inves_cog.shadow.cli replay-m8 --trade-dates 2026-10-15 2026-10-16 2026-10-19 2026-10-20 2026-10-21 --output-directory <本项目新的隔离目录>`。必须配置 INVES_COG_SHADOW_DATABASE_URL 和实时 INVES_COG_OVERLAY_DIR 用于目录隔离校验。摘要不输出事件/私人持仓；文件私有0600。无模型调用、业务写表、M4读写或实际服务安装。

## B042 依赖集成（2026-10-22 22:46 北京）

已继承 main 661b0ff（运行代码0096d5f、B042准确head4ea2e39），M9自身业务代码未变。新双连接依赖下 M9/M4仍 **70 passed / 3 deselected**，Ruff check/format通过，b042-integration-green.xml。相对main的docs/golden/milestones、M4、M8均无A新增修改。新完整head CI由PR/A状态另核。

A014已完成M8每日服务实际安装，用户也已确认27次逻辑调用上限的一次五日回放，费用授权不再是A5停点。执行前原生CLI只读核对发现历史loader复用实时generated_at过滤，漏掉10-22补算的10-15/16/20记录；已在PR49评论6343508016直接交需求方最小限定修复。模型/回放快照尚未写入，A5真实结果仍不能以本地合成五日替代。已完成安装、迁移、四日M7不重复执行。
