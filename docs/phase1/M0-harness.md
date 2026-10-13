# M0 工程骨架与 Harness

| 项 | 内容 |
|---|---|
| 文档版本 | v1 |
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
config/params/p-2026.10.yaml                 # 先放规格第 17 节的初始值
config/params/rule_a_v18.yaml                # 规则 A 常量（I03 用）
migrations/phase1_0001_schemas_roles.sql     # README §3.6 的 schema 和角色
.github/workflows/phase1.yml
```

## 5. 功能需求

| 编号 | 需求 |
|---|---|
| FR-M0-01 | 建立第 4 节列出的目录和文件；新包只有 `__init__.py` 和必要的接口占位 |
| FR-M0-02 | 注册标记 `phase1_blocking`、`phase1_replay`、`phase1_cases`、`phase1_live`；未注册的标记报错 |
| FR-M0-03 | 断网：`tests/` 下所有测试运行时，任何 socket 连接和 DNS 解析都抛错并使测试失败；`phase1_live` 标记的测试除外 |
| FR-M0-04 | 时钟门禁：扫描 `src/inves_cog/`，出现 `datetime.now(`、`datetime.utcnow(`、`date.today(`、`time.time(` 即失败；`clock.py` 本身除外 |
| FR-M0-05 | `pending.txt`：格式 `测试名 \| 模块 \| 原因`；被 skip 或 xfail 但不在文件中 → 失败；文件中的测试其模块已在 `milestones.txt` → 失败；文件中的测试名在代码里不存在 → 失败 |
| FR-M0-06 | 初始 `pending.txt` 包含 README §5 中除 I01、I26、I37 之外的全部不变量测试，以及 M1–M10 文档第 7 节列出的全部测试名，模块字段与文档一致 |
| FR-M0-07 | 需求方标准答案：测试直接读取 `docs/phase1/golden/`，校验每个文件的 sha256 与 `MANIFEST.sha256` 一致，且目录里没有清单之外的文件；各模块测试通过同一个加载函数读取，不得另存副本 |
| FR-M0-08 | 冻结输入：`tests/fixtures/phase1/` 下的文件登记在 `tests/fixtures/phase1/MANIFEST.sha256`；哈希变化而 `CHANGELOG.md` 没有包含该文件路径和新哈希的条目 → 失败 |
| FR-M0-09 | 导入防火墙（I01）：基于 AST 的导入图，按 README §3.7 的允许 / 禁止表判定；包括 `from x import y`、相对导入和 `importlib.import_module("字面量")`；任何位置导入 `stock_pm` 或 Muse 的模块名（`paper_trade_*`、`paper_tracker`、`factor_framework*`、`screen_asof_*`）即失败 |
| FR-M0-10 | LLM：`config/llm_tasks.yaml` 与 README §3.8 的表完全一致；`registry` 只能返回 `glm-5.3` 或 `deepseek-v4.1-flash`；按第 2 节的扫描范围，除 `config/llm_tasks.yaml` 和测试录音外不得出现其他模型名字符串（至少包括 `glm-5.2`、`GLM-5.3-Flash`、`gpt-`、`claude-`、`qwen`、`gemini`）；所有 LLM 调用都经 `registry` |
| FR-M0-11 | 迁移骨架：建立 README §3.6 的 schema 和角色，按"不可读"列执行 REVOKE；`tools/permissions.py` 提供 `assert_no_select(role, schema)`、`assert_no_write(role, schema)`，供后续模块的权限测试使用（测试用迁移脚本的静态解析或临时数据库，不连生产库） |
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
4. 改 `docs/phase1/golden/m3_interp_points.json` 的一个数字（只在本地分支做，不提交）；
5. 改一个冻结输入文件，不写 CHANGELOG；
6. 在 `src/inves_cog/trading/` 里 `import inves_cog.valuation_v1`；
7. 在 `config/llm_tasks.yaml` 里把一个任务的模型改成 `glm-5.2`；
8. 在 `src/inves_cog/marketstate/` 里 `import inves_cog.perception.attribution`；
9. 在任意业务包里 `import stock_pm`。

## 8. 需求方验收

| AC | 判定标准 | 类型 | 对应 | 阻塞 |
|---|---|---|---|---|
| AC-M0-01 | 干净环境 `pytest -m phase1_blocking` 全绿，耗时 ≤ 180 秒 | H | FR-M0-02、12 | 是 |
| AC-M0-02 | 第 7 节 9 项破坏性自测都产生红灯，错误信息指明文件和规则 | E | FR-M0-03–10 | 是 |
| AC-M0-03 | `pending.txt` 的条目与 README §5 和 M1–M10 第 7 节的测试清单逐一对应，模块字段正确 | E | FR-M0-06 | 是 |
| AC-M0-04 | 需求方在本地改动 golden 的一个字节，测试变红；`CODEOWNERS` 已生效 | E | FR-M0-07、13 | 是 |
| AC-M0-05 | 扫描范围内搜索不到 LLM 白名单以外的模型名；代码中搜索不到 `stock_pm` 和 Muse 模块的导入 | H + E | FR-M0-09、10 | 是 |
| AC-M0-07 | 需求方在一台干净机器上执行 `make phase1-test` 一次跑通 | D | FR-M0-13 | 是 |
| AC-M0-06 | CI 在 PR 上自动运行 `phase1_blocking`，每晚任务存在 | E | FR-M0-12 | 否 |

## 9. 已决定的问题

| # | 问题 | 决定 |
|---|---|---|
| Q-M0-1 | 能不能从 stock-pm 或 Muse 拷代码过来改？ | 不能。本项目独立；Muse 源码只作计算细节的参照，在本项目内重写 |
| Q-M0-2 | 权限测试要不要连真实数据库？ | 不连。可以静态解析迁移脚本，或在测试里起临时数据库（需在开工复述里说明用哪种） |
