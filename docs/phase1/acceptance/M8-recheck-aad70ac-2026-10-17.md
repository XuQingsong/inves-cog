# M8 无新闻终局继承增量复验

准确版本：`aad70ac564c9082392a947da07582e677b35bc34`。只复验相对 `459d88c` 的新增两行；隔离工作树干净。report blob `cbf18de5e8da1367da3f58cc237ab20f933740a5`，chain blob `a53464038e943bc159c0b39c73849da9274dbabd`，Store blob `3eae359cf094b632c51dea864fdad59766b55d97`。Store 与已验 `6f4d199` 无变化。

结论：**该窄项通过，9 组、12 次阶段执行全部通过。** 原四个无新闻失败（支持、冲突、失效、周末支持）均已恢复已保存的基本面结论，且同日重复运行不丢失。用户原已看到的经营证据终局判断，不会因后续没有新新闻或模型不可用而变成空值。

验证从空内存存储开始，先调用实际 `Store.save` 保存合法完整终局（含阶段历史、非空未明项、到期结果、理由及是否证明经营影响），再由新的实际 `Store.prior` 读取；调用正常 `execute_stage('attribution_labels', ..., store=Store(...))`，随后实际保存和重新读取。没有直接注入 `prior_event`，也没有以调用方自填“支持”代替已保存来源。

| 控制 | 实际结果 |
|---|---|
| 原支持、冲突、失效：无新闻，各同日运行两次 | 三类结论、到期结果、理由、非空 unknowns、history、proven 均保留 |
| 周末无新闻：已保存支持 | 保留完整结论 |
| 有新闻但本地模型替身不可用 | 已保存支持保留，降级路径未清空原判断 |
| 有新闻但当前候选为空 | 已保存支持保留 |
| 未结案：模型不可用或无新闻，调用者伪填支持/proven | 仍未结案，不新增已证明经营影响 |
| 没有已存事件，调用者伪填支持/proven | 不生成验证结论 |

所有阶段执行均未产生 tracks 更新 SQL，继续符合已验 `459d88c` 的 labels 无 session 防覆盖门槛。未重跑那轮 10 组 guard；此处只是与当前增量相关的相邻控制。

证据模式：**实际函数 + 内存 SQL 捕捉投影**，无数据库连接、无真实模型调用。复用 `m8-6f4d199-persistence` 已通过的 12 项真实 PostgreSQL tuple/权限证据，未新增临时库，也不把当前内存投影说成重新通过实库。

可复查材料：`verify.py`、`results.json`、`source-and-diff.txt`。执行命令：

```sh
cd /home/claudeuser/inves-cog-reference/work/codex-m8-aad70ac-review-20261017
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/claudeuser/inves-cog-reference/work/m7merge/.venv/bin/python /home/claudeuser/inves-cog-reference/work/m8-aad70ac-no-news/verify.py
```

只关闭“合法已保存终局在无新闻/空候选时基本面结论丢失”这一项。dict_row、attribution_tracks 阶段默认日期、替代解释缺失值/候选范围、任务失败记账及主链真实输入、四真实案例、五日全池回放等其余已记录开放项均未因本次通过而关闭。本次没有判定 M8 整体通过。
