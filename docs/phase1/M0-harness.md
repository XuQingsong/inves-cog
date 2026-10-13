# M0 工程骨架与 Harness

| 项 | 内容 |
|---|---|
| 文档版本 | v2（答复开工复述 K01–K08） |
| 规格章节 | 16.2–16.6；本目录 README 第 3、4 节 |
| 依赖 | 无 |
| 关闭的不变量 | I01、I37 |
| 规模 | 小到中 |

## 1. 目标

让后面所有模块"没过测试就合并不了"，并且让那些已经发生过的问题无法再次溜进代码：测试访问网络、用系统时间、用 skip 把红灯变绿、改标准答案迎合实现、交易模块偷偷读估值、用了第三个 LLM。

对应需求："第一阶段的开发需求一定要有 harness，避免开发过程中反复出问题。"

## 2. 范围

**做**：

- 项目骨架与工程基线（README §3.11）：`pyproject.toml`、锁文件、`Makefile`、docker compose（PostgreSQL + pgvector）、`CODEOWNERS`；
- 测试目录、标记、断网、注入时钟、pending / milestones / CHANGELOG 机制；
- 需求方标准答案的哈希校验（直接读取 `docs/phase1/golden/`）；
- 导入防火墙（含"不得导入 stock-pm / Muse"）、时钟禁用、LLM 模型白名单这几类静态门禁；
- 业务包的空骨架、`Clock`、`params`、`llm` 任务注册表；
- 数据库 schema 和角色的迁移骨架（建 schema、建角色、REVOKE），以及权限检查的测试工具函数；
- CI：PR 跑 `phase1_blocking`，每晚跑 `phase1_replay` 和 `phase1_cases`。

**不做**：任何业务逻辑；任何表的业务字段（各模块自己建）；页面。

**边界澄清**：

- "断网"指测试进程内所有 socket 连接（含 DNS 解析）都失败，不是只拦 HTTP 库。
- 时钟门禁扫整个 `src/inves_cog/`（`clock.py` 除外）。
- LLM 白名单门禁扫 `src/`、`config/`、`tests/`（录音文件除外）、部署脚本；`docs/` 不扫（归档文档里有历史模型名）。

## 3. 输入

- `docs/phase1/golden/` 的全部文件和 `MANIFEST.sha256`；
- README §3 的通用约定。

## 4. 输出

```
tests/harness/conftest.py
tests/harness/pending.txt
tests/harness/milestones.txt
tests/harness/CHANGELOG.md
tests/harness/tools/permissions.py          # assert_no_select(role, schema) 等工具
pyproject.toml、锁文件、Makefile（phase1-test / phase1-replay / phase1-cases）
docker-compose.yml                           # PostgreSQL ≥ 15 + pgvector，供本地和测试使用
.github/CODEOWNERS                           # docs/** → 需求方
src/inves_cog/{ingest,marketstate,trading,valuation_v1,perception,shadow,overlay,web}/__init__.py
src/inves_cog/clock.py                       # Clock、SystemClock、FrozenClock
src/inves_cog/params.py                      # 读取 config/params/*.yaml，暴露 params_version
src/inves_cog/llm/registry.py                # 任务名 → 档位 → 模型
config/llm_tasks.yaml
config/params/p-2026.10/m0.yaml              # 参数目录（各模块各自加文件）；加载器合并整个目录
config/params/rule_a_v18.yaml                # 规则 A 常量（I03 用）
migrations/phase1_m0_0001_schemas_roles.sql  # README §3.6 的 schema、角色、授权与默认权限
.github/workflows/phase1.yml
```

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M0-01 | 建立第 4 节列出的目录和文件；新包只有 `__init__.py` 和必要的接口占位 |
| FR-M0-02 | 注册标记 `phase1_blocking`、`phase1_replay`、`phase1_cases`、`phase1_live`；未注册的标记报错 |
| FR-M0-03 | 断网：`tests/` 下所有测试运行时，任何 socket 连接和 DNS 解析都抛错并使测试失败（即使业务代码捕获了异常，测试也要失败）。唯一例外：`phase1_live` 标记的测试，且只在显式执行 `pytest -m phase1_live` 并设置环境变量 `INVES_COG_LIVE=1` 时放开网络；live 测试永远不进 CI 和 `phase1_blocking`，时间仍经注入的 `Clock`（live 运行注入 `SystemClock`） |
| FR-M0-04 | 时钟门禁：扫描 `src/inves_cog/`，出现 `datetime.now(`、`datetime.utcnow(`、`date.today(`、`time.time(` 即失败；`clock.py` 本身除外 |
| FR-M0-05 | `pending.txt`：格式 `测试名 \| 模块 \| 原因`。规则：（1）测试被 skip / xfail 但不在文件中 → 失败；（2）文件中的测试其模块已在 `milestones.txt` → 失败；（3）重复行、模块编号不合法、格式错误 → 失败；（4）**测试名在代码里还不存在是允许的**（该模块尚未开发），但模块写入 `milestones.txt` 时它的全部测试必须存在；（5）**棘轮**：文件中登记、且代码里已存在的测试，由 `conftest` 自动标为 `xfail(strict=True)`——它一旦通过就变成失败，提示"已转绿，请从 pending 删除"；开发不得手工给它们加 skip / xfail |
| FR-M0-06 | 初始 `pending.txt` = M1–M10 文档第 7 节列出的全部测试名（共 142 个），模块字段与文档一致。README §5 的第一阶段不变量测试都已包含在这些清单里；**不登记** I26（已删除）和 I29、I31（第二阶段，`test_b2_hysteresis`、`test_s10_price_structure_review`）。M0 自己的 12 个测试不进 pending（本任务必须全部转绿）。另提供一个检查：pending 的测试集合 + M0 测试集合 = 各模块文档第 7 节测试集合的并集，双向相等 |
| FR-M0-07 | 需求方标准答案：测试直接读取 `docs/phase1/golden/`，校验每个文件的 sha256 与 `MANIFEST.sha256` 一致，且目录里没有清单之外的文件；各模块测试通过同一个加载函数读取，不得另存副本 |
| FR-M0-08 | 冻结输入：`tests/fixtures/phase1/` 下的文件登记在 `tests/fixtures/phase1/MANIFEST.sha256`；哈希变化而 `CHANGELOG.md` 没有包含该文件路径和新哈希的条目 → 失败 |
| FR-M0-09 | 导入防火墙（I01）：基于 AST 的导入图，按 README §3.7 的允许 / 禁止表判定；包括 `from x import y`、相对导入和 `importlib.import_module("字面量")`；任何位置导入 `stock_pm` 或 Muse 的模块名（`paper_trade_*`、`paper_tracker`、`factor_framework*`、`screen_asof_*`）即失败 |
| FR-M0-10 | LLM：`config/llm_tasks.yaml` 与 README §3.8 的表完全一致（10 个任务）；`registry` 只能返回 `glm-5.3` 或 `deepseek-v4.1-flash`；按第 2 节的扫描范围做**白名单式**检查：用正则匹配形如模型名的字符串（前缀至少包括 `glm`、`gpt`、`claude`、`qwen`、`gemini`、`deepseek`、`llama`、`mistral`，不区分大小写），凡不在白名单 {`glm-5.3`, `deepseek-v4.1-flash`} 中的一律失败；这样项目里不需要出现任何禁止模型名的清单。负例在扫描范围之外的临时文件里构造，用同一个扫描器验证红灯；所有 LLM 调用都经 `registry` |
| FR-M0-11 | 迁移骨架：建立 README §3.6 的 schema 和角色。权限策略为**默认拒绝**：每个角色对自己负责写入的 schema 有读写权；对"可读"列中的 schema 只授予 SELECT；其他一律没有权限，"不可读"列再显式 REVOKE 一次；`role_shadow` 对 `perception_shadow`、`factor_shadow` 可写，其余只读；`role_web` 全部只读。迁移由独立的管理员角色 `inves_cog_admin` 执行，并为每个 schema 写 `ALTER DEFAULT PRIVILEGES`，使以后各模块新建的表自动符合矩阵。`tools/permissions.py` 提供 `assert_no_select(role, schema)`、`assert_no_write(role, schema)`；`phase1_blocking` 里用迁移 SQL 的静态解析，不打开数据库连接 |
| FR-M0-12 | CI：PR 必跑 `phase1_blocking`；每晚跑 `phase1_replay`、`phase1_cases`；`phase1_blocking` 总耗时超过 180 秒即失败 |
| FR-M0-13 | 工程基线：`make phase1-test` 在只装了 Docker 和 Python 的干净机器上一次跑通（建环境、迁移、测试）；`CODEOWNERS` 把 `docs/**` 指定给需求方 |

## 6. 异常与降级

不适用（本模块只有门禁）。门禁本身报错时必须给出可读原因：哪个文件、哪一行、违反哪条规则。

## 7. Harness 与自测

| 测试名 | 标记 | 断言 | 对应 |
|---|---|---|---|
| `test_harness_no_network` | blocking | 测试内发起 socket 连接、DNS 解析、`requests.get` 都失败 | FR-M0-03 |
| `test_injected_clock_only` | blocking | 扫描结果为空；对一个含 `datetime.now(` 的临时文件能报错 | FR-M0-04 |
| `test_pending_registry` | blocking | FR-M0-05 的三条规则 | FR-M0-05、06 |
| `test_milestones_consistency` | blocking | `milestones.txt` 中每个模块在 `pending.txt` 中没有残留 | FR-M0-05 |
| `test_requirements_golden_unchanged` | blocking | FR-M0-07 | FR-M0-07 |
| `test_frozen_fixtures_changelog` | blocking | FR-M0-08 | FR-M0-08 |
| `test_import_firewall` | blocking | I01 | FR-M0-09 |
| `test_llm_models_allowed` | blocking | I37 | FR-M0-10 |
| `test_schema_roles_migration` | blocking | 迁移脚本含全部 schema、角色、REVOKE | FR-M0-11 |
| `test_clean_env_bootstrap` | CI | 干净容器里 `make phase1-test` 通过 | FR-M0-13 |
| `test_markers_registered` | blocking | 四个标记已注册 | FR-M0-02 |
| `test_blocking_duration` | CI | 180 秒上限 | FR-M0-12 |

**破坏性自测**（自测报告里逐项附红灯输出，然后还原）：

1. 在任意测试里 `socket.create_connection(("example.com", 80))`；
2. 在 `src/inves_cog/trading/` 里加一行 `datetime.now()`；
3. 新增一个 `@pytest.mark.skip` 的测试，不登记 `pending.txt`；
4. 把 `docs/phase1/golden/` 复制到 `docs/` 之外的临时目录，改其中一个文件的一个字节，用同一个校验入口指向临时目录，得到红灯（**不改动真实的 golden**）；
5. 改一个冻结输入文件，不写 CHANGELOG；
6. 在 `src/inves_cog/trading/` 里 `import inves_cog.valuation_v1`；
7. 在扫描范围之外的临时文件里构造一个非白名单模型名（例如运行时拼接字符串），用同一个扫描器扫描该文件，得到红灯；
8. 在 `src/inves_cog/marketstate/` 里 `import inves_cog.perception.attribution`；
9. 在任意业务包里 `import stock_pm`。

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应 | 阻塞 |
|---|---|---|---|---|
| AC-M0-01 | 干净环境 `pytest -m phase1_blocking` 全绿，耗时 ≤ 180 秒 | H | FR-M0-02、12 | 是 |
| AC-M0-02 | 第 7 节 9 项破坏性自测都产生红灯，错误信息指明文件和规则 | E | FR-M0-03–10 | 是 |
| AC-M0-03 | `pending.txt` 的条目与 README §5 和 M1–M10 第 7 节的测试清单逐一对应，模块字段正确 | E | FR-M0-06 | 是 |
| AC-M0-04 | 需求方在本地改动 golden 的一个字节，测试变红；开发提供的临时副本破坏性自测为红灯；`.github/CODEOWNERS` 内容为 `docs/** @XuQingsong`。（GitHub 分支保护是否开启属于用户的前置条件 R1，不计入本条判定） | E | FR-M0-07、13 | 是 |
| AC-M0-05 | 扫描范围内搜索不到 LLM 白名单以外的模型名；代码中搜索不到 `stock_pm` 和 Muse 模块的导入 | H + E | FR-M0-09、10 | 是 |
| AC-M0-07 | 需求方在一台干净机器上执行 `make phase1-test` 一次跑通 | D | FR-M0-13 | 是 |
| AC-M0-06 | CI 在 PR 上自动运行 `phase1_blocking`，每晚任务存在 | E | FR-M0-12 | 否 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M0-1 | 能不能从 stock-pm 或 Muse 拷代码过来改？ | 不能。本项目独立；Muse 源码只作计算细节的参照，在本项目内重写 |
| Q-M0-2 | 权限测试要不要连真实数据库？ | 不连。`phase1_blocking` 里静态解析迁移脚本 |
| Q-M0-3（K01） | pending 要登记 142 个尚未实现的测试，又要求测试名必须存在，矛盾怎么办？ | 按 FR-M0-05 v2：尚未开发的模块允许只登记测试名；已存在的 pending 测试自动按 `xfail(strict=True)` 运行（棘轮）；模块关闭时全部测试必须存在。`make phase1-replay` / `phase1-cases` 收集到 0 个测试时以退出码 0 结束，但必须打印 `NO TESTS COLLECTED — pending: N`，CI 摘要显示"无测试（待实现）"，不得显示为"通过" |
| Q-M0-4（K02） | I29 / I31 进不进第一阶段 pending？ | 不进。它们属于第二阶段 A+。M9 的 `test_f02_shadow_hysteresis`、`test_s10_eligibility_shadow` 是第一阶段测试，照常登记 |
| Q-M0-5（K03） | golden 破坏性自测与"不改 docs"冲突？ | 采用临时副本方案（见第 7 节第 4 项）；真实 golden 的改动由需求方在验收时执行 |
| Q-M0-6（K04） | 迁移文件名？ | `migrations/phase1_m0_0001_schemas_roles.sql`（含模块编号），与任务书一致 |
| Q-M0-7（K05） | 白名单负例怎么写？ | 白名单式扫描（FR-M0-10 v2），不需要禁止清单；负例在扫描范围外的临时文件里构造。外部项目的禁止导入负例同样只做源码文本分析，不实际导入 |
| Q-M0-8（K06） | CODEOWNERS 写谁？ | `@XuQingsong`。分支保护由用户设置（R1），开发不需要、也不能证明它已开启 |
| Q-M0-9（K07） | 未列明的权限怎么处理？ | 默认拒绝，见 FR-M0-11 v2；迁移由 `inves_cog_admin` 执行并设置默认权限 |
| Q-M0-10（K08） | `phase1_live` 能否联网？ | 能，但只在显式执行 `-m phase1_live` 且 `INVES_COG_LIVE=1` 时；永不进 CI；时间仍经注入的 `Clock`。M0 自身不发起任何真实请求 |
| Q-M0-11 | 工程选型？ | 确认：uv + `uv.lock`、Python 3.11、FastAPI（M0 只登记依赖和空 `web` 包）、docker compose 提供 PostgreSQL + pgvector 测试库 |
