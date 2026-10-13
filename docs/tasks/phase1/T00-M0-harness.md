# T00 · M0 工程骨架与 Harness

> 交给：一个开发 agent。按第一阶段任务书第 4 节的工作规则执行，完成后提交验收。

## 你的任务

搭起项目骨架和 Harness：让后面每个模块"没过测试就合并不了"，并且从一开始就拦住几类已知问题——测试访问网络、用系统时间、用 skip 把红灯变绿、改标准答案、交易模块读估值、导入 stock-pm 或 Muse 的代码、使用第三个 LLM。本任务不写任何业务逻辑。

## 先读（按顺序）

1. [`../00-overall-brief.md`](../00-overall-brief.md) —— 整体需求与目标
2. [`00-phase1-brief.md`](00-phase1-brief.md) 第 4 节 —— 工作规则（分支、交接文件、共享文件、禁止事项）
3. [`../../phase1/README.md`](../../phase1/README.md) 第 3、4 节 —— 通用约定和 Harness 总则
4. [`../../phase1/M0-harness.md`](../../phase1/M0-harness.md) —— **你的需求文档，全文**
5. [`../../system-spec.md`](../../system-spec.md) 第 16.3–16.6 节 —— 公式和规则的出处

## 依赖

无。这是第一个任务，后面所有任务都依赖它。

## 交付物

- `pyproject.toml`、锁文件、`Makefile`（`phase1-test` / `phase1-replay` / `phase1-cases`）、`docker-compose.yml`（PostgreSQL + pgvector）、`.github/CODEOWNERS`、CI 配置
- `src/inves_cog/` 下各业务包的空骨架，以及 `clock.py`、`params.py`、`llm/registry.py`
- `config/llm_tasks.yaml`（与 README §3.8 完全一致）、`config/params/p-2026.10/`、`config/params/rule_a_v18.yaml`
- `migrations/phase1_m0_0001_schemas_roles.sql`（全部 schema、角色、REVOKE）
- `tests/harness/`：`conftest.py`（断网、注入时钟）、`pending.txt`（含 M1–M10 文档第 7 节的全部测试名）、`milestones.txt`、`CHANGELOG.md`、`tools/permissions.py`
- M0 文档第 7 节列出的全部测试

## 完成标准

1. 模块文档第 7 节的 12 个测试全部存在并转绿；`pending.txt` 里本模块的行全部删除。
2. 本模块负责关闭的不变量全部为绿：I01、I37。
3. `make phase1-test` 全绿，且没有把其他模块已绿的测试改红。
4. 下表中标为阻塞的验收条款都有证据（需求方验收时逐条判定，只按这张表）：

| 条款 | 判定标准 | 类型 | 阻塞 |
|---|---|---|---|
| AC-M0-01 | 干净环境 `pytest -m phase1_blocking` 全绿，耗时 ≤ 180 秒 | H | 是 |
| AC-M0-02 | 第 7 节 9 项破坏性自测都产生红灯，错误信息指明文件和规则 | E | 是 |
| AC-M0-03 | `pending.txt` 的条目与 README §5 和 M1–M10 第 7 节的测试清单逐一对应，模块字段正确 | E | 是 |
| AC-M0-04 | 需求方在本地改动 golden 的一个字节，测试变红；`CODEOWNERS` 已生效 | E | 是 |
| AC-M0-05 | 扫描范围内搜索不到 LLM 白名单以外的模型名；代码中搜索不到 `stock_pm` 和 Muse 模块的导入 | H + E | 是 |
| AC-M0-07 | 需求方在一台干净机器上执行 `make phase1-test` 一次跑通 | D | 是 |
| AC-M0-06 | CI 在 PR 上自动运行 `phase1_blocking`，每晚任务存在 | E | 否 |

类型：H = 自动测试；E = 证据（报告、数据、截图）；D = 现场演示。

## 自测报告要附的证据

- 干净容器里 `make phase1-test` 的完整输出
- 第 7 节 9 项破坏性自测，每项的红灯输出
- `pending.txt` 与各模块文档测试清单的对照表（可以用脚本生成）
- 按模板（模块文档 README 第 7.2 节）写 `handoff/M0/self-test.md`，逐条对应上表的验收条款

## 最容易出错的地方

- 断网要拦 socket 和 DNS，不能只拦 HTTP 库
- `pending.txt` 要能发现三种违规：未登记的 skip、已关闭模块的残留、测试名不存在
- 标准答案直接读 `docs/phase1/golden/`，所有模块用同一个加载函数，不另存副本
- 导入防火墙要覆盖相对导入和 `importlib.import_module("字面量")`

## 开工第一步

写 `handoff/M0/kickoff.md`（模板见模块文档 README 第 7.1 节），以草稿 PR 提交，然后**停下等答复**。复述单除了模板要求的内容，还必须写清：

- 你选用的依赖锁定工具、Web 框架、测试数据库方式（docker compose 或测试容器）
- `pending.txt` 的初始内容从哪里生成、怎么保证不漏

## 不要做

- 不改 `docs/` 下的任何文件，包括标准答案；
- 不导入、不调用 stock-pm 或 Muse 的代码，不读写它们的数据库；
- 不实现模块文档"不做"清单里的内容，也不顺手改其他模块；
- 文档没写的行为不自己决定，写进 `handoff/M0/questions.md` 等答复；
- 不跳过测试，不用真实 key 或网络做测试。
