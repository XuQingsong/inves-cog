# M8→M9 合同消费自验（独立消费层阶段）

依据：main `aefc62ba9eb8953a0d7905af77b21a50dbdf9adf` 的 A-015 补充四至六。
唯一 JSON SHA256：`72c05c6ed1fd793673ee4dd5ce572bb4f2d2e6eec49791cc59a07badd86a8fd3`。
JSON 由 main 合入，未编辑 docs。所有数据均为合同的合成输入，不是生产事件或持仓。
2026-10-22 20:47 北京重验：合同新增 `check_scope`，真实 M8 链路保留“无关系→纯共振”；evt-gap/NVDA 缺项仅作 M9 防御输入。原 M9 判定已符合，无业务规则修改；直接消费新版合同的15项测试通过，证据 `provider-scope-green.xml`。此前 up/down 版本的14项结果保留在 `provider-direction-green.xml`，不当作本次新head结果。

先失败提交：`4e6bc2ca954db6f46ce2f0ba343610d05af01919`，`provider-contract-red.xml` 为 10 failed / 2 passed；随后实现消费逻辑。
两项已有 A2 测试先通过：在原生发布截止后触发缺失处理，保留旧版本/生成时间，首次缺失不发布。没有改变调度门禁。

| 项 | 当前结果 | 测试和证据 |
|---|---|---|
| A1 | 独立消费层通过；真实 provider 接线待 B-041 验收合并 | `test_a1_a3_a4_actual_contract_via_native_provider` 直接读取唯一 JSON，经 `scheduled(m8_provider=...)`，逐项消费 `expected_m9`，WDC/STX on、MU off、NVDA/AMD unknown。新增 `test_a1_pure_resonance_contract_is_off` 从同一JSON的 `expected_m9_pure_resonance` 取输入/预期，使用指定原事件经相同入口验证纯共振 NVDA off、无gap/无unknown，WDC/STX仍on、MU仍off；独立事件输入不混入evt-gap防御负例。未手抄期望值或加载未合并 B 代码。 |
| A2 | 通过 | `test_a2_incomplete_contract_retains_previous_generated_at`、`test_a2_first_incomplete_contract_has_no_overlay`；`test_incomplete_input_keeps_legacy_overlay_without_rewriting` 保留旧格式完整 payload。原 M4 `test_overlay_missing_marked` 仍验证缺失照常出纸面计划。 |
| A3 | 通过 | A1 同时断言 multiplier=1、stop_review_eligible=false、无订单/增买字段；`test_extended_delivery_rejects_inconsistent_diagnostics` 拒绝新增 buy 和不一致状态。 |
| A4 | 通过 | A1 对 `m8_completeness` 的 complete/source_events_asof/unknown_ticker_count/unknown_tickers 作精确比较；未知列表为 AMD、NVDA。 |
| A5 | 未执行；仍有上游依赖 | 真实 `read_replay_snapshot` 待 B-041 代码验收合并，真实五日模型回放仍须准确 dry-run 估算和需求方确认。`test_empty_complete_input_publishes_empty_overlay` 仅验证空输入消费，不能冒充五日回放或10-19生产验证。 |
| A6 | 本地相关回归通过，整仓以准确 head CI 为准 | 新版check_scope合同：`provider-scope-green.xml` 15 passed、Ruff check/format通过。此前 `provider-direction-green.xml` 14 passed、消费实现的 `provider-contract-green.xml` 58 passed / 3 deselected保留为历史阶段记录。本机 `make phase1-test` 明确因无Docker退出，未修改门禁、未宣称本地整仓通过。准确head CI链接由A状态及PR记录。 |

消费语义：缺失只来自 provider 的 `missing.fields`。不根据 null、deadline_on 或日期自行重判缺失。逐标的 exposure gap 即使标的不在 affected 中也保留该标的 unknown；展示字段缺失保留 NULL 和结构化 gap，但不阻断冷静期；direction 只在“已验证·有影响”时为判定字段。

多个事件仍按原冷静期并集：任一完整事件触发则 on；没有已知触发但有必需字段缺失则 unknown；全部完整且未触发才 off。某事件的未知不抹掉另一个完整事件已经成立的冷静期，全部 gap 仍随事件保留。没有新增买入、卖出或影子动作。

新增输出受原投递验证器约束，并兼容读取旧格式覆盖层。真实M8来源读取、数据库迁移、M9部署、M4时序与规则A均未改变；本阶段不等于模块验收或上线。
