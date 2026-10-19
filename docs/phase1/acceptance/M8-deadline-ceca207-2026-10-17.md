# M8 Q16第1项到期门槛复验：ceca207（2026-10-17）

准确提交 `ceca20773f9de12f89cf49ad4f2215c40608d735`，开始前通过PR18元数据确认。仅对照c52dbc0到期问题，提取chain.py/tracks.py变化做独立反例；不重跑20项、17/13组或全CI。B明确Q16第2–5项未改，本次保持未关闭。

**核心结论：原先“不看期限就结案”的直接错误已被部分修复，但尚不能保证用户不会在证据尚待取得时被提前告知失效。新增日期比较仍可能早一个美股交易时段终结；到期缺字段和12:30结论继承也未闭环。因此Q16第1项暂不完全关闭。**

## 方法与证据

- 隔离detached worktree：`/home/claudeuser/inves-cog-reference/work/codex-m8-ceca207-review-20261017`。
- 实际命令：该目录内`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/claudeuser/inves-cog-reference/work/m7merge/.venv/bin/python /home/claudeuser/inves-cog-reference/work/m8-ceca207-deadline/verify.py`。
- 本地同内容脚本`verify.py`、结果`results.json`、准确blob及diff`source-and-diff.txt`。
- 只用构造的确定性客户端替身，无真实模型、数据库访问、业务采集或部署；源码工作区干净。
- 18个仅针对期限/任务边界的观察项：13符合、5不符合。不是整体M8通过率。

## 已通过的窄项

1. 原c52反例：10-15、明确期限10-30、经营记录为空时，继续基本面核查，历史不变，不写失效。
2. 最早日期：显式日期、财报周期、机制周期分别优先的三种情况均正确；20交易日上限正确。周末和感恩节闭市跳过正确。
3. 真正已过反应日后，09:30跟踪任务对空记录输出条件风险/失效，operating_impact_proven=false，不伪称经营已证实。
4. 09:15候选和12:30打标不推进生命周期，run_scheduled三时段确实调用对应阶段。

## 失败反例与业务影响

### D1：北京日期与美股反应日混用，仍会提前结案

最小输入：

- 异常起点：2026-10-14美东09:30（UTC13:30）；
- earnings_sessions=1，所以最早财报反应交易日计算为**2026-10-15（美股交易日）**；
- as_of=**2026-10-15北京09:30**，即**2026-10-14美东21:30**，10-15美股反应日还没开始；
- prior_event.lifecycle=基本面核查中，operating_records=[]。

实际输出：deadline_on=10-15，生命周期已衰减·无影响，基本面失效，触发“截止日仍未知”。用户在应等待的反应日还没开始前，已经看到终局结论。

原因：`tracks.py:74–76 deadline_reached`用`as_of.date()`直接和交易日日期比较；`_as_date:86–96`保留传入时区的日历日期，没有按同一个交易所日期/任务所处理的交易日对齐。应明确deadline代表哪一美股反应日、到哪个观察边界才允许结案，不能仅比较北京日历。

### D2/D3：非法期限会成为“最早有效期限”并导致即时失效

- earnings_sessions=-1：`range(-1)`不迭代，期限变成起点当天10-14，10-15晨间立即结案。
- deadline_on=10-01早于10-14事件：直接取为最小值，同样立即结案。

`tracks.py:59–82`没有校验周期为有效交易日计数，也没有拒绝事件开始前的期限。应拒绝/明确降级无效输入，不能把它当有效最早日期。这里未要求新增策略或参数。

### D4：到了期限，经营输入字段缺失时永不落三选一

同一个已到期对象：operating_records=[]会条件风险结案；仅省略operating_records字段，则一直基本面核查中、待验证、无deadline_outcome。`chain._lifecycle`仍要求records is not None。真实输入未接齐时必须留下正式缺口/到期状态，不能因缺字段静默无限跟踪。此项不要求把缺数变成支持或反证。

### D5：12:30虽不推进状态，却丢失09:30已形成的结论

先在09:30取得已衰减·无影响/条件风险/基本面失效，再把完整prior_event（含deadline_outcome、closing_reason、fundamental）传给12:30任务。

输出lifecycle仍是已衰减·无影响，但报告deadline_outcome和closing_reason变NULL，fundamental_standing退回待验证。`_lifecycle`在labels阶段直接返回state/history/None，后续报告重算而不继承已关闭结论。用户在同一天不同时间看到互相冲突的结论。即使不能推进生命周期，也应保留已有终局证据与结果。

## 判定范围

本次承认到期日期和阶段边界有实质修复，但D1直接触及“证据未等到就给终局结论”的核心问题；D2/D3暴露最早有效期限校验；D4/D5是期限流程的输入和结果继承缺口。建议留在原B-008修复并以这五个最小反例复验，不重复其他已关闭检查。

Q16第2–5项仍开放；四例真实调用、五日全池回放、整体AC和运维证据没有因本次窄项检查而通过。完成本次复验后停止，没有追逐更晚head。
