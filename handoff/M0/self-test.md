# M0 自测报告

- 模块：M0 · 工程骨架与 Harness
- 文档版本：`docs/phase1/M0-harness.md` v2；答复 Q-M0-3 至 Q-M0-11
- 实现代码提交：`5322ac2511a484135e2db319b2bdbbbe8f973fe2`
- 需求基线：`6a62f9b8c53c3ce5a280dd9fe115e48e0adeb094`，任务分支已 rebase 到此提交
- 日期：2026-10-13（北京时间）
- 提交状态：开发自测完成，提交需求方验收；本报告不代替需求方验收报告

## 1. Harness：命令、数量、耗时和环境

### 测试先行

先提交了 12 项失败测试和合成 NULL 夹具，然后才提交实现。GitHub 上的顺序为：

1. `1c4e369`：开工复述单 rebase 到 M0 v2；
2. `902b418`：失败测试与冻结夹具，**12 failed**；
3. `5322ac2`：M0 工程与 Harness 实现。

初始红灯使用当时可用的隔离 Python 3.12 工具环境，仅证明实现缺失。正式开发和通过记录均使用批准的 **Python 3.11.17**。原始红灯证据：[日志](evidence/red-tests.log)、[JUnit XML](evidence/red-tests.xml)。

### 正式本地离线验证

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -m phase1_blocking -q --junitxml=.harness/local-blocking.xml
.venv/bin/python scripts/m0_selfcheck.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -m phase1_replay -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -m phase1_cases -q
```

- blocking：**10 passed，0 failed，2 deselected，2.69 秒**。这两项是模块文档标为 CI 的测试，在下面的干净容器中另行执行并通过；不是 skip/xfail。
- 九项破坏性自测：全部产生对应规则红灯。
- replay：退出码 **0**；原样输出 `NO TESTS COLLECTED — pending: 5` 和“无测试（待实现）”。
- cases：退出码 **0**；原样输出 `NO TESTS COLLECTED — pending: 3` 和“无测试（待实现）”。
- 本地没有 Docker，未声称在本机执行过数据库启动或 `make phase1-test`；这些由真实 GitHub CI 完成。

本地证据：[blocking JSON](evidence/local-blocking.json)、[blocking JUnit](evidence/local-blocking.xml)、[replay 状态](evidence/local-replay.json)、[cases 状态](evidence/local-cases.json)。

### 干净容器与临时数据库验证

[GitHub PR CI 运行](https://github.com/XuQingsong/inves-cog/actions/runs/38380965246)，head 为 `5322ac2`，`phase1-blocking` job 结论 **success**。GitHub 自动生成的 PR 合并提交为 `1b9dcdbd9e4982c23ed8368db4556ee9bf10d745`；同时验证了与当时 main 的兼容性。

容器中实际执行：

```bash
make phase1-test
.venv/bin/python -m pytest tests/harness/test_m0_ci.py -q --junitxml=.harness/m0-ci.xml
.venv/bin/python scripts/m0_selfcheck.py
```

| 项目 | 实际结果 |
|---|---|
| 环境 | Ubuntu 24.04 runner 上新建 Python 3.11 干净容器；锁定 uv 0.13.0、`uv sync --frozen` |
| Python / pytest | 3.11.17 / 9.1.1 |
| blocking | **10 passed，0 failed，3.54 秒**，小于 180 秒 |
| 两项 CI 测试 | **2 passed，0 failed，0.03 秒** |
| 规定的 M0 测试 | 12 项全部存在，全部实际执行并通过，无 skip/xfail |
| 数据库 | 独立临时库 `inves_cog`，执行角色 `inves_cog_admin` |
| 数据库版本 | PostgreSQL 16.15；pgvector 0.8.7 |
| 迁移 | `phase1_m0_0001_schemas_roles.sql` 实际执行完成 |
| 默认权限 | 管理员在十个 schema 新建临时探针表，八个角色 × 十个 schema，共 **80 组** SELECT/INSERT/UPDATE/DELETE 权限检查全部符合矩阵 |
| 清理 | 临时 compose 容器、网络已删除；没有访问共享或其他项目数据库 |
| 破坏性自测 | 9/9 预期红灯，真实 golden 哈希不变 |

完整证据：[干净容器输出](evidence/ci-clean-make.log)、[bootstrap 事实](evidence/ci-bootstrap.json)、[blocking JSON](evidence/ci-blocking.json)、[blocking JUnit](evidence/ci-blocking.xml)、[两项 CI JUnit](evidence/ci-tests.xml)、[80 组真实权限](evidence/ci-database-permissions.json)。

CI 原生证据包：[artifact 11802644266](https://github.com/XuQingsong/inves-cog/actions/runs/38380965246/artifacts/11802644266)。下载后核对 ZIP SHA-256 为 `14fec6a9f3dcb5afc1ee5b2c0d6768554866a22f7d02271c0f485bcdb30aebea`，与 CI 上传记录一致。

## 2. 本模块应关闭的不变量

| 不变量 | 测试 | 结果及证据 |
|---|---|---|
| I01 | `test_import_firewall` | 通过；普通导入、相对导入、字面量动态导入、marketstate 边界、订单写接口和外部项目导入负例均被拦截；CI JUnit 与破坏性日志 06/08/09 |
| I37 | `test_llm_models_allowed` | 通过；配置十个固定任务；只路由到 `glm-5.3` / `deepseek-v4.1-flash`；白名单式扫描及八类模型前缀负例通过；CI JUnit 与破坏性日志 07 |

业务包均为空骨架。M0 没有任何模型或真实数据请求；registry 负责注册与路由，未擅自实现接入 R4 的网络客户端。

## 3. pending / milestones 的变更

- 初始化 `pending.txt` 为 M1–M10 §7 的 **142 项**，不登记 M0 的 12 项、已删除的 I26、第二阶段 I29/I31。
- 按类型为 blocking 128 项、replay 5 项、cases 3 项、live 6 项。live 项原因登记“等待 R5”；其他项登记等待对应模块实现。
- 已有 pending 测试自动 strict xfail；失败继续公开为 xfailed，意外通过成为 XPASS(strict) 红灯，并提示“已转绿，请从 pending 删除”。开发手工 skip/xfail、重复行、非法模块、关闭模块残留与缺少真实测试定义均有负例验证。
- 初始覆盖满足 pending 142 项 + M0 12 项 = 文档清单并集 154 项；后续模块转绿时由真实测试定义接替 pending 覆盖，不能用不存在的测试冒称完成。
- `milestones.txt` 只有说明注释，**未写入 M0**；验收后由需求方维护。
- CHANGELOG 只新增合成 NULL 夹具的初始冻结记录，含路径、旧状态 absent、新 SHA-256 和 FR-M0-08；没有替换历史标准答案。

逐条对照：[pending-report.json](evidence/pending-report.json)。

## 4. 验收条款自评

| AC | 自评 | 对应测试 / 证据 |
|---|---|---|
| AC-M0-01 | 开发验证通过 | 干净容器 blocking 10 passed / 3.54 秒；`test_markers_registered`、`test_blocking_duration`；CI JSON 和 JUnit |
| AC-M0-02 | 开发验证通过 | 9 项破坏性自测全部非零退出且指出对应文件与规则；`evidence/destructive/`，CI 重复验证记录 |
| AC-M0-03 | 开发验证通过 | `test_pending_registry`、`test_milestones_consistency`；142 项模块归属与 154 项完整覆盖对照 |
| AC-M0-04 | 开发验证通过；需求方原目录复核待验收 | 临时副本 golden 修改字节后红灯，真实 golden 未变；`.github/CODEOWNERS` 为 `docs/** @XuQingsong`；R1 分支保护按 Q-M0-8 不计本条判定 |
| AC-M0-05 | 开发验证通过 | I01/I37 两项测试、扫描结果、十任务精确配置和负例；扫描范围中无其他模型名，无外部项目代码导入 |
| AC-M0-07 | 开发侧干净环境演示通过；需求方现场复跑待验收 | 真实新建容器 `make phase1-test` 一次跑通，`test_clean_env_bootstrap` 通过；完整输出和环境事实已附。需求方在自己的干净机器执行属于最终验收动作，未冒称已由需求方执行 |
| AC-M0-06（非阻塞） | PR 自动 CI 通过；夜间任务配置已提交 | PR 对应成功 Actions 运行；`.github/workflows/phase1.yml` 有每晚 replay/cases 调度、显式空集合摘要和证据上传。尚未到首次夜间调度，不冒称已发生夜间运行 |

## 5. 破坏性自测

所有破坏都发生在临时文件中，不提交破坏内容；测试后文件自动删除。真实 golden 始终未改动。

| 项 | 操作 | 实际结果 | 日志 |
|---|---|---|---|
| 1 | 测试尝试 socket 连接 | exit 1，FR-M0-03；被捕获的违规同样红灯，pending 也不能掩盖网络违规 | [01](evidence/destructive/01-network.log) |
| 2 | 临时 trading 源码直接读系统时间 | exit 1，FR-M0-04 | [02](evidence/destructive/02-clock.log) |
| 3 | 新增未登记 skip | exit 4，FR-M0-05，收集阶段拒绝 | [03](evidence/destructive/03-skip.log) |
| 4 | docs 外 golden 副本改变字节 | exit 1，FR-M0-07 | [04](evidence/destructive/04-golden.log) |
| 5 | 冻结输入副本改变而无 CHANGELOG | exit 1，FR-M0-08 | [05](evidence/destructive/05-frozen.log) |
| 6 | 临时 trading 导入估值 | exit 1，I01 | [06](evidence/destructive/06-valuation-import.log) |
| 7 | 扫描范围外临时构造非白名单模型 | exit 1，I37 | [07](evidence/destructive/07-model.log) |
| 8 | 临时 marketstate 导入归因 | exit 1，I01 | [08](evidence/destructive/08-marketstate-import.log) |
| 9 | 临时文本导入外部项目 | exit 1，I01；只做 AST 文本分析，没有实际导入 | [09](evidence/destructive/09-external-import.log) |

汇总：[summary.json](evidence/destructive/summary.json)，包含 `real_golden_unchanged: true`。

## 6. 已知偏差与限制

- 无未经 Q&A 批准的业务或范围偏差。
- 不存在的下游测试、strict xfail、空 replay/cases 处理均按 Q-M0-3/4；临时 golden 及模型负例按 Q-M0-5/7；管理员、默认拒绝权限按 Q-M0-9；live 双开关及 CI 隔离按 Q-M0-10。
- R1 用户设置与 R4 实际模型接入不是本次伪造的完成项。当前全部 M0 自测离线、没有真实 key，没有用空数据冒充真实接入。
- 尚无 M1–M10 实现：142 项 pending 仍在，不能据 M0 完成声称第一阶段已完成。
- Git CLI 写入认证未配置；通过已授权 GitHub 连接发布提交，并以文件树哈希核对、导入远端精确提交对齐本地分支。原本地开发历史完整保存在 `backup/m0-local-development`。

## 7. 新发现的需求问题

无需要另行决策的需求问题。此前八项问题均按 M0 v2 的书面答复实施。等待需求方按上述 AC 逐条验收及现场复跑，不自行写验收结论或关闭 milestone。
