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
