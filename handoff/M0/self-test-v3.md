# M0 v3 补丁自测报告

模块：M0-v3　文档版本：v3　代码提交：`4f97f408ae4e039707e9bbf62e68b7948116e309`　日期：2026-10-13

## 1. Harness 与测试先行证据

基线为 PR #1 的合并提交 `b612a0c32e352ad17fea676b99c70f26174fccaa`。PR #1 使用 merge commit 合并；[main 的 phase1-blocking](https://github.com/XuQingsong/inves-cog/actions/runs/38390074486/job/115271407911) 为 success，合并 SHA 和运行链接已在 PR #1 留言。

先提交失败测试 `620f8936619f032e3145ea0d520ec47e1858edfc`，再提交实现 `4f97f408ae4e039707e9bbf62e68b7948116e309`。没有合并或改写这两个提交。

| 环境 / 操作 | 结果 | 证据 |
|---|---|---|
| 修复前本地 blocking | 4 failed、6 passed、2 deselected，33.51 秒 | 四项失败分别为网络、时钟、golden、模型扫描 |
| 修复前干净 CI | 4 failed、6 passed、2 deselected，33.94 秒 | [失败测试提交的 CI](https://github.com/XuQingsong/inves-cog/actions/runs/38391156114/job/115275002082) |
| 修复后本地 blocking | 10 passed、2 deselected，6.66 秒 | `pytest -m phase1_blocking`；JUnit 无失败、无 skip |
| 修复后干净容器 `make phase1-test` | 10 passed、2 deselected，9.26 秒 | [实现提交的 CI](https://github.com/XuQingsong/inves-cog/actions/runs/38391786352/job/115277097324) |
| 干净容器两项 CI 测试 | 2 passed，0.03 秒 | `test_clean_env_bootstrap`、`test_blocking_duration` |
| 原有九项破坏性自测 | 9/9 产生预期红灯，本地和 CI 一致 | 第 5 节与 CI 证据包 |

CI 使用全新 Ubuntu 24.04 runner 和 Python 3.11 容器。`bootstrap.json` 确认 Python 3.11.17、`clean_container=true`、`lock_frozen=true`、临时 PostgreSQL 16.15、pgvector 0.8.7、迁移由 `inves_cog_admin` 执行；80 组实际数据库权限探针符合矩阵。本机没有 Docker，干净机器和另外两项 CI 测试以该托管容器为证据。

[完整 CI 证据包](https://github.com/XuQingsong/inves-cog/actions/runs/38391786352/artifacts/11809078710) 包含 `.harness-clean.log`、`bootstrap.json`、`blocking.json`、`database-permissions.json`、`phase1_blocking.xml`、`m0-ci.xml`、九项破坏性日志及 `summary.json`。下载包 SHA-256：`1500a36ec2ab8f228aa42700ceda29539a9701e775dd91edd8965dc09f278353`；已实际下载并校验。JUnit 原文附在第 8 节。

## 2. 不变量与补丁覆盖

- I01：导入防火墙仍为绿；交易读估值、市场状态读归因、外部项目导入三个破坏性负例仍变红。
- I37：白名单仍为绿；八个模型前缀的负例仍变红。目录模式新增根目录 `Dockerfile.x`、`Makefile`、`.env`、`.env.test`、`docker-compose.test.yml`，以及 `scripts/Dockerfile.harness`、`config/a.txt/.ini/.cfg`、`src/a.md`、`tests/a.data`、`.github/workflows/a.yaml` 负例，每个都验证文件与行号。二进制和录音 JSON 对照通过。
- RD-01：socket 方法仅放行 AF_UNIX；AF_INET/AF_INET6 的 connect、connect_ex、send、sendall、sendto、sendmsg、listen 仍拦截，DNS 和 `socket.create_connection` 仍拦截。被捕获的违规仍导致测试失败。socketpair、跨线程 asyncio 自唤醒、进程内 TestClient 和 AF_UNIX 路径连接全部通过。
- RD-02：补充 datetime.today / datetime.datetime.today、time.time_ns、pandas.Timestamp.now / today / utcnow、numpy.datetime64("now" / "today")；属性引用和别名导入同样拦截。time.monotonic、time.perf_counter 和固定日期的 numpy.datetime64 通过。
- RD-03：golden 集合直接来自 MANIFEST，没有固定个数或文件名清单；在 docs 外的临时副本新增二进制文件并同步 MANIFEST 后通过，非 JSON 加载返回 bytes。原目录逐文件哈希未变。
- RD-04：指定目录中的文本不再按扩展名筛选，并纳入根目录部署文件及 `.env*`；二进制文件跳过。

测试函数名仍为原来的 12 个，仅扩充第 7 节标 v3 的四项测试；CI 共执行 10 项 blocking 和 2 项 CI 测试，全部通过，0 skip。

## 3. pending / milestones 与改动范围

`pending.txt`、`milestones.txt`、`docs/` 相对合并后的 main 均无 diff。M0 的 milestone 由需求方登记。代码改动仅在 `tests/harness/`、`pyproject.toml`、`uv.lock`；另按补丁任务要求新增本自测报告。TestClient 的 dev 依赖为精确版本 `httpx==0.28.1`，锁文件增加其传递依赖，没有更新原有运行依赖版本。

## 4. 验收条款自评

| AC | 自评 | 证据 |
|---|---|---|
| AC-M0-08 | 满足开发自测要求 | 干净 CI `make phase1-test` 全绿，10 blocking + 2 CI 测试；第 2 节逐项覆盖 v3 断言，JUnit 见第 8 节 |
| AC-M0-09 | 开发复跑通过，供需求方复跑 | 第 6 节三项探针均小于 30 秒；`socket.create_connection(("127.0.0.1", 1))` 被捕获后仍退出 1、诊断含 FR-M0-03；IPv6 回环和 DNS 同样变红 |
| AC-M0-10 | 满足开发自测要求 | 本地和干净 CI 的 9 项均 `red=True`，第 5 节逐项输出；真实 golden 保持不变 |

## 5. 九项破坏性自测

使用原有、未修改的 `scripts/m0_selfcheck.py`；源码负例只静态扫描，golden 和冻结输入只改 docs 外的临时副本，模型负例在扫描范围外拼接构造。CI 证据包保存每项完整日志，以下为本地执行输出：

```text
01-network: exit=1; FR-M0-03; red=True
02-clock: exit=1; FR-M0-04; red=True
03-skip: exit=4; FR-M0-05; red=True
04-golden: exit=1; FR-M0-07; red=True
05-frozen: exit=1; FR-M0-08; red=True
06-valuation-import: exit=1; I01; red=True
07-model: exit=1; I37; red=True
08-marketstate-import: exit=1; I01; red=True
09-external-import: exit=1; I01; red=True
real_golden_unchanged=true
```

诊断均带文件和行号。示例路径省略共同的临时目录前缀：

```text
probe-0/test_probe.py:3: FR-M0-03: forbidden socket/DNS operation create_connection
src/inves_cog/trading/bad_time.py:2: FR-M0-04: system time datetime.now; inject Clock
probe-2/test_probe.py:2: FR-M0-05: developer-added skip/xfail: test_probe
golden/m3_interp_points.json:1: FR-M0-07: SHA-256 mismatch
frozen/harness/sample.json:1: FR-M0-08: frozen hash mismatch; update manifest and CHANGELOG
import-0/src/inves_cog/trading/bad_valuation.py:1: I01/FR-M0-09: trading may not import inves_cog.valuation_v1
bad_model.py:1: I37/FR-M0-10: non-whitelisted model glm-5.2
import-1/src/inves_cog/marketstate/bad_attribution.py:1: I01/FR-M0-09: marketstate may not import inves_cog.perception.attribution
import-2/src/inves_cog/ingest/bad_external.py:1: I01/FR-M0-09: external project import stock_pm
```

## 6. RD-01 探针前后输出与复跑

同一份探针定义在 `tests/harness/tools/probes.py`，由 `run_probe` 启动独立 pytest 进程，加载真实 Harness 插件，`INVES_COG_LIVE=0`，每个进程 30 秒硬超时。耗时包括进程启动、收集和测试，不使用系统日期判定。

| 探针 | 修复前 | 修复后（进程总耗时） |
|---|---|---|
| socketpair | 退出 1；FR-M0-03 拦截 sendall | 退出 0，0.259 秒 |
| asyncio call_soon_threadsafe | 退出 1；FR-M0-03 拦截 send | 退出 0，0.210 秒 |
| FastAPI TestClient | 30.008 秒时触发 TimeoutExpired，子进程被终止 | 退出 0，0.348 秒；HTTP 200、`{"ok": true}` |

TestClient 修复前输出：

```text
TestClient: request started

TIMEOUT after 30 seconds
```

TestClient 修复后输出（告警原文与 JUnit 一并保留；没有屏蔽告警）：

```text
TestClient: request started
TestClient: status=200 body={"ok": true}
.
=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/fastapi/testclient.py:1
  /Users/xuqingsong/workspace/inves-cog/.venv/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 0.26s
```

需求方可从仓库根目录复跑三个探针：

```bash
PYTHONPATH=.:src .venv/bin/python - <<'PY'
import tempfile
from pathlib import Path
from tests.harness.tools.probes import LOCAL_COMMUNICATION_PROBES
from tests.harness.tools.testing import run_probe, output
with tempfile.TemporaryDirectory() as directory:
    for name, code in LOCAL_COMMUNICATION_PROBES.items():
        result = run_probe(Path(directory), code, arguments=('-s',))
        print(name, result.returncode, output(result))
        assert result.returncode == 0
PY
```

该入口不会开启 live。回环、DNS 和全部 INET 方法的负例可复跑 `pytest tests/harness/test_m0.py::test_harness_no_network -q`；所有请求在实际外发之前被门禁拦截。

## 7. 已知偏差与新问题

功能偏差：无。新需求问题：无。锁定的 Starlette 1.8.0 对 httpx TestClient 发出弃用告警，当前锁定组合实际通过本地和 CI；告警未隐藏，也未以 skip 处理。

补丁按任务书 §4.2 和 M0 v3 第 10 节提交验收，待需求方按 AC-M0-08–10 验收通过后合并；期限为 T01 或 T02 任一提交验收之前。

## 8. 干净 CI 的 JUnit 原文

<details>
<summary>phase1_blocking.xml</summary>

```xml
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="10" time="9.256" timestamp="2026-10-13T11:40:25.439299+00:00" hostname="246f789424a9"><testcase classname="tests.harness.test_m0" name="test_harness_no_network" time="7.503" /><testcase classname="tests.harness.test_m0" name="test_injected_clock_only" time="0.011" /><testcase classname="tests.harness.test_m0" name="test_pending_registry" time="1.140" /><testcase classname="tests.harness.test_m0" name="test_milestones_consistency" time="0.052" /><testcase classname="tests.harness.test_m0" name="test_requirements_golden_unchanged" time="0.015" /><testcase classname="tests.harness.test_m0" name="test_frozen_fixtures_changelog" time="0.002" /><testcase classname="tests.harness.test_m0" name="test_import_firewall" time="0.100" /><testcase classname="tests.harness.test_m0" name="test_llm_models_allowed" time="0.023" /><testcase classname="tests.harness.test_m0" name="test_schema_roles_migration" time="0.008" /><testcase classname="tests.harness.test_m0" name="test_markers_registered" time="0.323" /></testsuite></testsuites>
```

</details>

<details>
<summary>m0-ci.xml</summary>

```xml
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="2" time="0.035" timestamp="2026-10-13T11:40:35.256413+00:00" hostname="246f789424a9"><testcase classname="tests.harness.test_m0_ci" name="test_clean_env_bootstrap" time="0.001" /><testcase classname="tests.harness.test_m0_ci" name="test_blocking_duration" time="0.000" /></testsuite></testsuites>
```

</details>
