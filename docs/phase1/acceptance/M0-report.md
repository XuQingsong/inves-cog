# M0 验收报告

```
模块：M0 工程骨架与 Harness    文档版本：v2（判定依据）
被验收提交：b8f8585006d42770971da67a3c7a3ce5672a8f5b（PR #1「[M0] 提交验收」）
验收人：需求方    日期：2026-10-13
```

## 结论

**通过。** 全部阻塞条款（AC-M0-01 至 AC-M0-05、AC-M0-07）和非阻塞条款 AC-M0-06 均满足。

验收中另外发现 4 个需求缺陷 RD-01–RD-04。按 README §2 第 2 条，它们不计入本次判定，已写进 M0 v3（第 10 节），由补丁任务 `[M0-v3]` 完成，**期限：T01 或 T02 任一提交验收之前合并**。其中 RD-01 会让 FastAPI `TestClient` 卡死，T10 必须等补丁合并后再开工。

合并 PR #1 之后，需求方在 `tests/harness/milestones.txt` 写入 `M0`。

## 1. 复跑

| 项 | 环境与命令 | 结果 |
|---|---|---|
| 干净检出 | 从 `origin/phase1/m0-harness` 新建 git worktree，不复用开发的任何本地文件 | —— |
| 依赖 | 新建 venv 装 uv 0.13.0；`uv sync --frozen --python 3.11 --group dev` | Python 3.11.17、pytest 9.1.1，按锁文件安装成功 |
| blocking | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 INVES_COG_LIVE=0 .venv/bin/python -m pytest -m phase1_blocking` | **10 passed，2 deselected，3.77 秒**（墙钟 4.4 秒）；deselected 的两项是文档标为 CI 的测试 |
| replay / cases | `pytest -m phase1_replay`、`-m phase1_cases` | 退出码 0；输出"无测试（待实现）"；状态文件 `status=no_tests`，pending 分别为 5、3。没有显示成"通过" |
| 带数据库的 `make phase1-test` | 需求方本机 | **未执行**：验收机账号不在 `docker` 组，无法访问 Docker。改用 GitHub 托管 runner 的干净容器运行作为证据，见 AC-M0-07 |
| CI | GitHub API 查询 `b8f8585` 的 check-runs | `phase1-blocking`：success（2026-10-13 10:23:58–10:24:50 UTC，[运行记录](https://github.com/XuQingsong/inves-cog/actions/runs/38383076105/job/115248052307)）；`phase1-nightly` 在 push 事件上按设计跳过 |
| docs 未改动 | `git diff --name-only origin/main...origin/phase1/m0-harness \| grep ^docs/` | 空 |

## 2. 逐条判定

| AC | 判定 | 证据 |
|---|---|---|
| AC-M0-01 | 通过 | 干净 worktree 里 10 项 blocking 全绿，3.77 秒，不超过 180 秒；CI 干净容器 3.54 秒。`--strict-markers` 生效，未注册的标记报错（`test_markers_registered`） |
| AC-M0-02 | 通过 | 需求方**亲手**在 worktree 里逐项复现 9 项破坏性自测（不使用开发脚本），每项都变红，错误信息带文件:行号和规则编号，复现后 `git status` 为空。第 1 项：`FR-M0-03: forbidden socket/DNS operation create_connection`，即使业务代码捕获了异常也照样变红。第 2 项：`trading/__init__.py:3: FR-M0-04`。第 3 项：收集阶段报错 `FR-M0-05: developer-added skip/xfail`。第 4 项：见 AC-M0-04。第 5 项：`FR-M0-08: frozen hash mismatch`。第 6 项：`I01/FR-M0-09: trading may not import inves_cog.valuation_v1`。第 7 项：在 docs 之外的临时文件里构造 `qwen-max`，同一个扫描器报 `I37/FR-M0-10`。第 8 项：`marketstate may not import inves_cog.perception.attribution`。第 9 项：`external project import stock_pm` |
| AC-M0-03 | 通过 | 需求方用独立脚本解析 M0–M10 文档第 7 节：共 154 个测试，没有重名；其中 M0 12 个，其余 142 个。`pending.txt` 恰好 142 行，没有缺项也没有多余项，模块字段全部一致（M1 15、M2 17、M3 13、M4 15、M5 14、M6 12、M7 12、M8 18、M9 12、M10 14）。I29 和 I31 对应的 `test_b2_hysteresis`、`test_s10_price_structure_review` 没有登记；`test_f02_shadow_hysteresis`、`test_s10_eligibility_shadow` 已登记。README §5 只把不变量映射到模块，各不变量的测试都在对应模块的第 7 节里，已全部覆盖 |
| AC-M0-04 | 通过 | 需求方在 worktree 中给**真实的** `docs/phase1/golden/m3_interp_points.json` 追加 1 个字节，blocking 变红：`m3_interp_points.json:1: FR-M0-07: SHA-256 mismatch`；之后 `git checkout` 还原。开发提供的临时副本测试同样变红。`.github/CODEOWNERS` 内容为 `docs/** @XuQingsong`。R1 分支保护不计入本条 |
| AC-M0-05 | 通过 | 在 `src config tests scripts migrations .github Makefile pyproject.toml docker-compose.yml` 里 grep 形如模型名的字符串，除白名单两个模型以外，只命中扫描器自己的前缀词表（`checks.py:18`、`test_m0.py:181`，都是单独的前缀词，不是模型名）。grep `stock_pm\|stock-pm\|paper_trade_\|paper_tracker\|factor_framework\|screen_asof_`，除门禁本身外没有命中。`llm_tasks.yaml` 恰好 10 个任务，档位、超时、重试、失败状态都与 README §3.8 一致；registry 用逐字段的期望值校验 |
| AC-M0-07 | 通过（以 CI 干净机器为证据） | 条款原文要求"需求方在一台干净机器上执行"。验收机没有 Docker 权限，需求方无法在本机执行；改用以下证据：需求方通过 GitHub API 核对，`b8f8585` 在 GitHub 托管的全新 Ubuntu 24.04 runner 上运行成功；容器内执行 `make phase1-test`（uv 冻结锁、建临时 PostgreSQL 16.15 + pgvector 0.8.7、执行迁移、运行测试），`bootstrap.json` 记录 `clean_container: true`；80 组真实库权限探针（8 个角色 × 10 个 schema，对新建表检查 SELECT/INSERT/UPDATE/DELETE）全部符合矩阵。如果用户要求必须由需求方本机复跑，需要先把验收账号加入 `docker` 组，补跑一次不影响本结论 |
| AC-M0-06（非阻塞） | 通过 | `.github/workflows/phase1.yml` 在 `pull_request` 时运行 `phase1-blocking`，每晚 02:00 UTC 按计划运行 replay、cases 矩阵；空集合摘要显示"无测试（待实现）"。计划任务只在默认分支上触发，合并后的第一个夜间运行由需求方在下一个模块验收时顺带核对 |

另外核对的实现细节（不是条款，只记录）：

- 权限迁移与 README §3.6 一一对应：10 个 schema 都由 `inves_cog_admin` 持有。每个 schema 先对全部角色和 PUBLIC 做 REVOKE（含现有表、序列和默认权限），再按矩阵授权；每个 schema 都写了 `ALTER DEFAULT PRIVILEGES`；不存在角色之间的成员关系授予。
- 导入防火墙的允许表与 README §3.7 一致；`marketstate` 只能导入 `perception.graph`，能识别 `from .. import x`、`importlib.import_module("字面量")`、`__import__`。
- 棘轮：登记在 pending 里且已经存在的测试，会自动被标为 `xfail(strict=True)`；一旦意外通过就变红，并提示"已转绿，请从 pending 删除"。开发手工加的 skip 或 xfail，以及运行时调用 `pytest.skip()`，都会变红。

## 3. 需求缺陷（不计入本次判定，进入 M0 v3）

| RD | 复现命令与实际结果 | 期望 | v3 处理 |
|---|---|---|---|
| RD-01 | 在 worktree 中执行 `NetworkGuard().install()` 之后，用 FastAPI `TestClient` 请求一个本地路由：进程卡死，`timeout 60` 退出码 124；不装门禁时同一段代码立即返回 `{'ok': True}`。在 pytest 里，`socket.socketpair()` 收发报 `FR-M0-03 ... sendall`；asyncio `call_soon_threadsafe` 报 `FR-M0-03 ... send` | 进程内的本地通信（`AF_UNIX`）不算网络，应当放行；`AF_INET` / `AF_INET6`（含回环地址）和 DNS 解析继续拦截 | 第 2 节边界澄清；扩充 `test_harness_no_network` 的断言 |
| RD-02 | 扫描器对 `datetime.today()`、`time.time_ns()`、`pd.Timestamp.now()`、`f = datetime.datetime.now; f()` 都不报错 | 这几种写法同样是在读系统时间，应当拦截 | 扩充 FR-M0-04 的清单 |
| RD-03 | `test_requirements_golden_unchanged` 里断言 `len(validate_golden(real)) == 8` | 文件集合以 MANIFEST 为准，需求方增加 golden 文件后测试不应变红 | FR-M0-07 补充说明 |
| RD-04 | `scan_models` 只扫 7 种扩展名，`scripts/Dockerfile.harness`、`Makefile`、`.env*` 不在扫描范围内 | 部署脚本全部要扫 | 第 2 节边界澄清 |

RD-01 和 RD-02 的根源在需求方：v2 只写了"任何 socket 连接"和 4 个函数名，没有说明本地通信是否算网络，也没有把清单写全。RD-03 和 RD-04 是实现上的取舍，v2 也没有明令禁止。4 个都不算开发返工。

## 4. 后续

1. 用户合并 PR #1。
2. 需求方在 `tests/harness/milestones.txt` 写入 `M0` 并提交。
3. 原 M0 开发 agent 按 M0 v3 第 10 节完成 `[M0-v3]` 补丁，需求方按 AC-M0-08 至 AC-M0-10 验收。
4. T01、T02 可以立即在合并后的 main 上开工。
