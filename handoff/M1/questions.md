# M1 v2 开发中新问题（等待答复）

基线 main：4e217a0889c5c691e3e19510db15e0b573936d08。
已先提交失败测试：750e667d8e1124aa00eee55881fa0033181e761e；本任务 15 个测试全部存在，14 个 blocking 首次全部失败，尚未提交实现。

## K13：M0 里程碑负例依赖 M1 尚未开发

位置：`tests/harness/test_m0.py:test_milestones_consistency`（第 158–166 行）。第二个负例用临时文件删除全部 M1 pending，并声明 M1 已关闭，然后期望 `validate_registry` 因缺少 M1 测试而抛错。现在 M1 第 7 节 15 个测试已经全部存在，合法的“测试齐全、无 pending”场景自然不会抛错，反而使 M0 测试失败。

真实 CI：[失败运行](https://github.com/XuQingsong/inves-cog/actions/runs/38498091169)，job 115638370512。输出：

```text
collected 27 items / 3 deselected / 24 selected
FAILED tests/harness/test_m0.py::test_milestones_consistency
E Failed: DID NOT RAISE AssertionError
```

建议：将“模块关闭但测试缺失”的负例放在 docs 之外的最小临时仓库副本中，显式保留目录和规格但移除该模块的一项测试，使其不依赖真实 M1 当前开发状态。保留真实根目录的正例校验，并保留“已关闭模块仍有 pending”负例。测试名不变、不减断言、不改门禁实现和真实 milestones。

## K14：M0 干净环境断言写死迁移只有一个

位置：`tests/harness/test_m0_ci.py:13`：

```python
assert record['migrations'] == ['phase1_m0_0001_schemas_roles.sql']
```

`scripts/phase1.py:38–40,65` 实际执行并登记 migrations 下全部 SQL；这符合后续模块的迁移要求。因此加入任务要求的 `phase1_m1_0001_jobs_source_health.sql` 或任意 M2 迁移后，上述断言必然失败。这里不是请求隐藏迁移或伪造 bootstrap 记录。

建议：断言完整清单与仓库 migrations 实际排序后的 SQL 清单一致，并确保包含 M0 必需迁移。继续验证数据库身份、锁定依赖、PostgreSQL/pgvector、临时数据库和干净容器，不改测试名。

## 请求答复与停止位置

Q-M1-15 的唯一 M0 例外目前仅覆盖旧迁移中的 graph 只读授权和 permissions.py 的 READS，不覆盖这两个测试文件。我没有修改上述测试或任何 docs/milestones。请在 main 修正这两处基线，或明确扩展例外，授权在本 PR 只修这两处负例/清单断言；M2 同样受 K14 影响。按任务书 §4.1 第③步，此问题发布后暂停实现，等待答复。

共享 LLM/SEC 客户端与迁移已形成临时草稿，尚未写入或提交项目；不是可供 M2 正式使用的交付。R4/R5 真源验证仍未到位。

## 需求方答复（2026-10-14）

用户明确答复“授权在 M1 PR 修这两处”，将 M0 例外扩大至上述两项测试。按建议只改负例输入和完整迁移清单断言；测试名、门禁逻辑与真实 milestones 不变。已据此恢复开发。

## K15：pending 棘轮自测也依赖真实 M1 尚在 pending

`tests/harness/test_m0.py:test_pending_registry` 的子进程探针固定使用 `test_bar_window_to_20et`，直接读真实 pending。M1 的 14 项 blocking 实测通过后删除其登记，该探针的 `assert False` 不再自动 xfail，旧断言却仍期望退出码 0。完整离线门禁在 `5163684` 上因此失败（实际 1、期望 0）。

建议只为此探针传入临时 pending 和临时 milestones：显式登记该探针，验证失败自动 xfail、通过严格 XPASS 失败；不依赖真实模块是否关闭，不把已绿测试重新塞回真实 pending，也不改棘轮实现。此前授权只覆盖里程碑负例，未覆盖本函数，请确认补充授权。

## K16：模型名扫描误伤真实官网 URL

`config/monitored_entities.yaml` 必须起草 DeepSeek 的官方 URL。`tests/harness/tools/checks.py:236` 当前把 `https://www.deepseek.com/` 中的 `deepseek.com` 识别为模型名并拒绝；它是域名，没有调用其他模型。

完整门禁输出：

```text
FAILED tests/harness/test_m0.py::test_pending_registry
FAILED tests/harness/test_m0.py::test_llm_models_allowed
AssertionError: config/monitored_entities.yaml:30: I37/FR-M0-10: non-whitelisted model deepseek.com
2 failed, 22 passed, 3 deselected
```

建议精确区分 URL 中的品牌域名和模型 token；保留所有文本扫描及两个对话模型白名单，验证合法官网不误伤、非法模型值仍拒绝、URL 里的真实非法模型 token 仍拒绝。需要授权修改 `tests/harness/tools/checks.py` 的识别逻辑，并在原 `test_llm_models_allowed` 增加正反断言；不删除官网、不拆字符串躲扫描、不增加模型白名单。

K15/K16 发布后按任务书暂停 M1 后续实现，等待答复。M1 自身 14 项 blocking 已绿，但完整门禁仍红；核心提交不作为提交验收。

## K15/K16 需求方答复与测试先行（2026-10-14）

用户明确答复“授权这三项限定修正”：仅修改 `test_pending_registry` 的临时输入、`checks.py` 的品牌域名识别，并扩充原 `test_llm_models_allowed` 的正反断言。两个模型白名单、测试名、真实 milestones 均不变。

先提交扩充测试：pending 探针改为完整的合成登记和只含 M0 的临时 milestones，使其不依赖真实模块进度；品牌官网、端口 URL 为正例，模型字段及 URL 路径、查询参数、片段和模型型域名为负例。

修复识别逻辑前，定向运行结果为 `1 failed, 1 passed`：pending 棘轮正反探针均成立；官网正例仍因 `non-whitelisted model deepseek.com` 失败。随后才修扫描实现。

## K17：Q-M1-8 的 JSON 美东字面值假设与三个真源样例冲突

使用需求方已提供的 SEC_USER_AGENT，只读请求官方 submissions 与申报索引页，完成三个真实 Item 2.02 财报样例核对（均为盘后）。原始比较已冻结在 `tests/fixtures/phase1/m1/sec_acceptance_conflict.json`，登记 MANIFEST/CHANGELOG。未修改 golden 或 docs。

| accession | submissions acceptanceDateTime | 索引页 Accepted（美东） | 字面相差 |
|---|---|---|---|
| 0000320193-26-000018 | 2026-07-31T00:30:28.000Z | 2026-07-30 16:30:28 | 8 小时 |
| 0000320193-26-000011 | 2026-05-01T00:30:41.000Z | 2026-04-30 16:30:41 | 8 小时 |
| 0000320193-26-000005 | 2026-01-30T02:30:33.000Z | 2026-01-29 16:30:33 | 10 小时 |

官方索引：

- [2026-07-30](https://www.sec.gov/Archives/edgar/data/320193/000032019326000018/0000320193-26-000018-index.html)
- [2026-04-30](https://www.sec.gov/Archives/edgar/data/320193/000032019326000011/0000320193-26-000011-index.html)
- [2026-01-29](https://www.sec.gov/Archives/edgar/data/320193/000032019326000005/0000320193-26-000005-index.html)

Q-M1-8 要求“确认后按美东时间解析”，但三个样例都不能确认 JSON 字面值等于美东 Accepted。把 Z 去掉直接套纽约时区会将 accepted_at 错移 8/10 小时；直接按标准 UTC 解释也不能与索引页对齐。不能根据三个样例自行写死减 8/10 小时，更不能改期望值迎合已有解析器。

建议将官方申报索引页 `Accepted`（美东当地时间）设为权威接收时间，按纽约时区转换 UTC；submissions 的原始时间字符串照存证据。请需求方明确修改此处取数合同，包括 Accepted 不可取得时的缺口处理。M1 已有门禁从通过变为真实样例红灯，保留失败，不重加 pending、不跳过、不改黄金答案。

按任务书 §4.1 第③步“中途的新疑问写进 questions.md 并停下等答复”，暂停这项 SEC 时间规则修复与 M1 提交验收。此前 Token Plan 接入已按用户新的明确指示完成并真源验证，两个批准模型均 HTTP 200；这是 R4 配置落实，不推断或改写本问题的时间规则。

### K17 需求方答复与修复（2026-10-14）

用户选择“采用索引页 Accepted（推荐）”。按答复改为索引页 Accepted 的美东当地时间转 UTC；原 submissions `acceptanceDateTime` 仅保留证据，不直接生成 accepted_at。索引无法取得或格式异常时，保留原始申报和具体 URL/错误类别/HTTP 状态/待重试缺口，不生成未经核实的财报反应日。

先提交经答复更新的失败断言 `8fe8d0e`，随后实现；覆盖三个官方冻结样例、UTC 转换、JSON 带 Z 值不得进入美东解析器，以及索引缺口负例。全部 24 项离线门禁恢复通过。K17 已解决，不再作为开发停止项；没有改 docs、golden、pending 或 milestones。
