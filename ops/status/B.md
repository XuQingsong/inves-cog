# B 线回报

> 只由 B 线 agent 写。格式见 main 上的 ops/README.md 第 4 节，最新的写在最上面。

## B-041  进行中  2026-10-22 20:41 北京

- 收到 20:10 裁定（main `aefc62b`，`ops/answers/B-041.md`）。停下报告是对的，错在合同样例。保留 `report._exposure`：没有关系就是「纯共振」。不改 N 码，不改方向词。
- V1 逐键比较只针对 evt-toshiba 和 evt-expired。evt-gap 不要求 M8 产生。夹具里没有关系的 NVDA 输出 `exposure=纯共振`，不进缺失。其余 V2–V10 不变。
- 按这条继续交 V1–V10 的证据。不标已完成。不合并。

## B-041  进行中  2026-10-22 17:19 北京

- 停下。V1 要求 NVDA 只出现在 `missing.fields[event]["NVDA.exposure"]`。同一条链实测做不到，而且和已经生效的暴露规则冲突。没有改暴露规则，没有新造 N 码，没有改写方向。不标已完成。不合并。
- 交易日 2026-10-20，09:15 时点 `2026-10-21T09:15:00+08:00`，内存 store，计数客户端。东芝这条（WDC/STX 关系「直接/观察到」，MU 关系「概念关联/候选」，`deadline_on` 2026-11-06，每只标的一条假设链）可以：lifecycle `假设中`，mechanism `供给`，direction `down`，affected 为 WDC/STX「直接」、MU「概念关联」，`deadline_on` 2026-11-06，`deadline_outcome` 空，`ticker_status` 不写。样例里的「基本面核查中」仍只是示例。
- NVDA 没有关系、同一套打分：scope 和 affected 的暴露都是「纯共振」，不进缺失。这是 `report._exposure` 的现有规则：没有关系的价格成员是纯共振。`tests/m8/test_attribution.py` 的 `test_scope_is_a_relation_label_and_tracking_is_not_evidence` 锁着这条。
- 候选受影响名单里不放 NVDA：NVDA 不进 scope、affected、`ticker_status`，也不进缺失。快照上看不到这只标的。
- 说法不合格、候选没有生成（只调用了 `move_card` 和 `claim_extraction`）：lifecycle 停在「已发现」，不写 linkage，`ticker_status` 是 NVDA 的 N6 且没有暴露。实时快照从 `linkage_events` 起读，这条事件不出现，缺失暴露也不会出现。给已经打分的供给再写 N6，会新造现在 `ticker_codes` 不写的码；`n_code` 又不能空。
- 所以「只在缺失里出现 NVDA.exposure」要改纯共振规则，或者改 N 码规则。两处都没有这次任务的授权。V1–V10 不逐项标通过。等这条怎么取舍。

## B-041  进行中  2026-10-22 17:14 北京

- 收到 17:10 裁定（main `fe0b451`，`ops/answers/B-041.md`）。停下报告是对的。方向采用 M8 实际词表：`direction` 取 `up`/`down`，不改写成中文。`down` 即 M9 规格里的“方向不利”。合同样例已改为 `down`（evt-toshiba、evt-expired）。不改写链上的方向。
- 按这条裁定继续交 V1–V10，不再等其他答复。不标已完成。不合并。

## B-041  进行中  2026-10-22 15:45 北京

- 草稿 PR #48 head `ce819d8` 的 phase1-blocking 已绿：https://github.com/XuQingsong/inves-cog/actions/runs/39742264835 。462 passed、21 deselected，用时 122.74 秒，nightly 跳过。没有合并。
- 草稿 PR #47 head `6ffd86b` 此前已绿。两个 head 的检查都过了，仍不标已完成。
- 方向词仍停着：合同样例是「不利」，链上实测是 `down`。没有改写。V1–V9 的合同夹具仍不逐项交齐。

## B-041  进行中  2026-10-22 15:41 北京

- PR #48 与基线 `cursor/m8-b036-pit-snapshot-e013` 冲突，所以 `e380b03` 和空提交都没有生成检查。合并基线后 head `ce819d8`，可以合并。phase1-blocking 正在跑：https://github.com/XuQingsong/inves-cog/actions/runs/39742264835 。没有合并进 main。
- 不标已完成。方向词仍停着：合同样例是「不利」，链上实测是 `down`。没有改写。

## B-041  进行中  2026-10-22 15:31 北京

- `e380b03` 推上 PR #48 后没有生成检查。空提交 `6c7b85e` 只为重新触发，代码与 `e380b03` 相同。https://github.com/XuQingsong/inves-cog/pull/48 。没有合并。
- 这一版的 phase1-blocking 还在等。不标已完成。
- 方向词仍停着：合同样例是「不利」，链上实测是 `down`。没有改写。

## B-041  进行中  2026-10-22 15:21 北京

- 草稿 PR #47 head `6ffd86b` 的 phase1-blocking 已绿：https://github.com/XuQingsong/inves-cog/actions/runs/39739524758 。452 passed、21 deselected，用时 89.05 秒，nightly 跳过。没有合并。
- 草稿 PR #48 head `e380b03` 还没有这一版的 CI。不标已完成。
- 方向词仍停着：合同样例是「不利」，链上实测是 `down`。没有改写。V1–V9 的合同夹具仍不逐项交齐。

## B-041  进行中  2026-10-22 15:19 北京

- 截止日语义已写上，还没标已完成。草稿 PR #47 head `6ffd86b`，https://github.com/XuQingsong/inves-cog/pull/47 。草稿 PR #48 head `e380b03`，https://github.com/XuQingsong/inves-cog/pull/48 。没有合并。
- `deadline_on` 取报告里已有的日期。空的 `deadline_outcome`：日期晚于 cutoff 的纽约日历日则不进缺失；不晚于该日则原因「截止日已到（日期）但没有支持/反证/条件风险结果」；没有日期则「截止日未知」。已有结果原样保留。来源时间晚于 cutoff 的日期看不见。回放用同一条规则。
- 证据：`tests/m8/test_b041.py` 覆盖未到期、到期、当天、未知、支持/反证/条件风险、后一个 cutoff，以及回放四种情形。PR #47 上这条和 `test_b036`、`test_b038` 本地 28 passed。PR #48 上 `test_b041`、`test_b039_run`、`test_b040` 本地 19 passed。两个新 head 的 phase1-blocking 还在等。
- 停下的一项：V1 要求 Toshiba 的 direction 与合同样例一致，样例是「不利」。同一条链实测写入的说法方向是 `down`。说法校验只接受 up/down。没有把 `down` 改写成「不利」。
- 下一步：等方向词怎么对齐。V1–V9 的合同夹具在这之前不逐项交齐，也不标已完成。

## B-041  已收到  2026-10-22 15:15 北京

- 任务：截止日语义，并按 `ops/answers/B-041.md` 的 V1–V10 交付。仍在草稿 PR #47 和草稿 PR #48，不新开 PR。授权沿用 UD-COORD-26/27。不新增 schema、角色、数据源。不部署，不在生产执行。不改合同文件 `docs/phase1/contracts/m8-m9-provider.json`。不改 M9、M4、规则 A。
- `deadline_on` 用报告里已经算好的 `report.deadline_on`（`earliest_deadline` 的结果）。实时读取走现有 reports，不加列。每个事件输出这个 ET 日期字符串。格子带来源时间：实时是注入时钟，回放是该阶段 as_of。读取时来源时间晚于 cutoff，这项为空，原因「来源时间晚于 cutoff」。
- `deadline_outcome` 为空时，用 cutoff 的 America/New_York 日历日比较。`deadline_on` 晚于该日：值为空，不进 `missing.fields`。不晚于该日：进缺失，原因「截止日已到（日期）但没有支持/反证/条件风险结果」（与合同样例一致）。`deadline_on` 为空或看不见：原因「截止日未知」。有值则原样输出，不进缺失。结果自己的来源时间晚于 cutoff 时，仍是「来源时间晚于 cutoff」，不用未到期把这条盖掉。读取时按这次 cutoff 重算。
- 回放 `_event` 用同一套判断。过期夹具的 `trade_date` 放在当天，`started_at` 不晚于 `deadline_on`，避免现有规则拒绝「期限早于事件」。不把这条推进到「基本面核查中」，避免链在到期时自动填上结果。
- V1 的方向：说法入库是 up/down，合同样例是「不利」。先实测。对不上就停下写明，不自行改方向词。
- 下一步：先写会失败的截止日例子。

## B-040  已完成  2026-10-22 13:36 北京

- 草稿 PR #47，head `2389ebb`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39727391542 。`phase1-blocking` 443 passed、21 deselected，用时 115.30 秒，nightly 跳过。没有合并。https://github.com/XuQingsong/inves-cog/pull/47
- 草稿 PR #48，head `ffde349`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39728350138 。`phase1-blocking` 452 passed、21 deselected，用时 80.77 秒，nightly 跳过。没有合并。https://github.com/XuQingsong/inves-cog/pull/48
- members 恢复每只标的自己的背离标签和下一份财报时间。事件级时间晚于 cutoff 时，这一项仍按缺失。
- 09:15 对有盘前新闻的 pool 先问一次 move_card，再走完整链落库。09:30 和 12:30 不再问模型。dry-run 与同一计数客户端实测一致。本地 `make phase1-test`：PR #47 443 passed、21 deselected，用时 68.76 秒；PR #48 452 passed、21 deselected，用时 68.98 秒，`make phase1-cases` 7 passed、1 xfailed，用时 25.34 秒。
- 有盘前新闻的 pool：09:15 是 `move_card` 1、`claim_extraction` 1、`anomaly_candidates` 1。没有盘前新闻的 pool 是 0。wide 三个阶段都是 0。09:30 和 12:30 都是 0。五日合计 3 次，全部在 10-15 的 09:15。不估费用。
- 证据分达到假设的供给异常，现有 N1/N2/N6 规则不写 `ticker_status`。lifecycle、mechanism、exposure 在快照上。没有新迁移，没有新角色。没有改 M9、M4、规则 A。没有部署，没有在生产执行。
- 下一步：等需求方验收。不取新任务。

## B-040  进行中  2026-10-22 13:33 北京

- 草稿 PR #47，head `2389ebb`，https://github.com/XuQingsong/inves-cog/pull/47 。members 恢复每只标的自己的背离标签和下一份财报时间。事件级时间晚于 cutoff 时，这一项仍按缺失。本地 `make phase1-test` 443 passed、21 deselected，用时 68.76 秒。CI 还在跑。没有合并。
- 草稿 PR #48，head `ffde349`，https://github.com/XuQingsong/inves-cog/pull/48 。09:15 对有盘前新闻的 pool 先问一次 move_card，再走完整链落库。09:30 和 12:30 不再问模型。dry-run 与同一计数客户端实测一致。本地 `make phase1-test` 452 passed、21 deselected，用时 68.98 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.34 秒。CI 还在跑。没有合并。
- 有盘前新闻的 pool：09:15 是 `move_card` 1、`claim_extraction` 1、`anomaly_candidates` 1。没有盘前新闻的 pool 是 0。wide 三个阶段都是 0。09:30 和 12:30 都是 0。不估费用。
- 证据分达到假设的供给异常，现有 N1/N2/N6 规则不写 `ticker_status`。lifecycle、mechanism、exposure 在快照上。没有新迁移，没有新角色。没有改 M9、M4、规则 A。没有部署，没有在生产执行。
- 下一步：两个 head 的 phase1-blocking 都绿了再写已完成。不取新任务。

## B-040  已收到  2026-10-22 13:13 北京

- 任务：B-039 验收修复。暂不验收、不合并。仍在草稿 PR #47（`cursor/m8-b036-pit-snapshot-e013`）和草稿 PR #48（`cursor/m8-b039-persist-replay-e013`）。授权沿用 UD-COORD-26/27。不新增 schema、角色、数据源。不部署，不在生产执行。
- 第 4 点先改 PR #47：`_flatten` 的 members 恢复每只标的自己的 `divergence_tag` 和 `next_filing_at`。字段时间晚于 cutoff 时这一项仍按缺失。补回归测试。然后把这一提交拣到 PR #48，不 force-push。
- 第 1、2、3 点只改 PR #48。09:15（`attribution_candidates`）对有盘前新闻的 pool 异常：先做一次 move_card（不把薄报告当最终落库），再走现有 `_score_one` 完整链落库，并把 daily_text、move_card 抄到这条结果上，早页文字不变。未排程、stage 为空的旧路径仍只走 move_card，不额外加调用。09:30 和 12:30 不再进 `_phase1_move`。tracks 复用 09:15 分析，不覆盖结构化报告，模型调用为 0。wide 若 tracks 会再调模型，改为复用；不能复用就记下、不再调。labels 保持 0 次。
- 删掉手写 `expected_calls`。dry-run 与真实运行同一路径，注入只计数不调用的客户端，store 用内存、不写库。同一夹具上 dry-run 计数等于三阶段实测，并断言 09:30 和 12:30 为 0。回放的 pool 结构化事件进内存 store，快照 events 来自完整链。
- 不改 M9、M4、规则 A。不调真实模型。
- 下一步：先写会失败的例子。

## B-039  已完成  2026-10-22 11:25 北京

- 第 1 部分：草稿 PR #47，head `f4f4223`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39715004161 。`phase1-blocking` 442 passed、21 deselected，用时 115.52 秒，nightly 跳过。没有合并。
- 第 2、3 部分：草稿 PR #48，head `2b6dc89`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39716433062 。`phase1-blocking` 448 passed、21 deselected，用时 117.22 秒，nightly 跳过。没有合并。https://github.com/XuQingsong/inves-cog/pull/48
- 证据：第 1 部分本地 `make phase1-test` 442 passed、21 deselected，用时 66.64 秒。第 2、3 部分本地 `make phase1-test` 448 passed、21 deselected，用时 66.58 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.79 秒。
- 三个阶段在时钟前 ok 就写 complete。字段缺口留在事件和 `missing.fields`。09:15 用现有 store 落库，不额外加模型调用。09:30 和 12:30 不调模型，读上一阶段并保存，labels 成功后写快照。五日回放用内存 store，不写生产 M8 实时表。`--dry-run` 不调模型。
- 没有新迁移，没有新角色。没有改 M7、M9、M4、规则 A。没有部署，没有在生产执行回放。
- 下一步：等需求方验收。不取新任务。

## B-039  进行中  2026-10-22 11:23 北京

- 第 2、3 部分：草稿 PR #48，head `2b6dc89`，分支 `cursor/m8-b039-persist-replay-e013`，叠在 PR #47 上。没有合并。https://github.com/XuQingsong/inves-cog/pull/48
- 09:15 用现有 store 落库，不额外加模型调用。保存失败则作业失败，页面仍写出。09:30 和 12:30 读上一阶段并保存；上一阶段没成功就记失败，不改钟，也不再跑一次冒充成功。labels 成功后写快照。supervisor 只加定义，不部署。
- 五日回放用内存 store，不写生产 M8 实时表。`snapshot_generated_at` 是实际运行时钟。`--dry-run` 不调模型。09:15 问法不变。09:30 和 12:30 的模型调用是 0。
- 证据：本地 `make phase1-test` 448 passed、21 deselected，用时 66.58 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.79 秒。
- CI 还在跑：https://github.com/XuQingsong/inves-cog/actions/runs/39716433062
- 第 1 部分仍是 PR #47 head `f4f4223`，CI 已绿。
- 下一步：这一版 phase1-blocking 绿了再把第 2、3 部分交给验收。不把 B-039 标成已完成。

## B-039  进行中  2026-10-22 11:11 北京

- 第 1 部分可验收。草稿 PR #47，head `f4f4223`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39715004161 。`phase1-blocking` 442 passed、21 deselected，用时 115.52 秒，nightly 跳过。没有合并。
- 证据：本地 `make phase1-test` 442 passed、21 deselected，用时 66.64 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.41 秒。三个阶段在时钟前 ok 就写 complete。字段缺口留在事件和 `missing.fields`。没有可见 lifecycle 的事件保留。阶段缺失、失败或晚于时钟仍不写快照。
- 第 2、3 部分另开 PR，从这一版接着做。早页用现有 store 落库，不额外加模型调用。09:30 和 12:30 读上一阶段并保存，labels 成功后写快照。五日回放用隔离存储，不写生产 M8 实时表。
- 下一步：不把 B-039 标成已完成。第 2、3 部分的 head 上 phase1-blocking 绿了再交。

## B-039  进行中  2026-10-22 11:08 北京

- 草稿 PR #47，head `f4f4223`，分支 `cursor/m8-b036-pit-snapshot-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/47
- 第 1 部分：三个阶段在快照时钟前以 ok 结束就写 complete。字段缺口留在事件和 `missing.fields`，不再把整日降级。没有可见 lifecycle 的事件保留，lifecycle 为空并写原因。读取只拒绝晚于 cutoff 的时间。阶段缺失、失败或晚于时钟仍不写。
- 改过的旧断言：`test_fields_without_a_source_time_stay_null`、`test_one_missing_field_keeps_the_others`、`test_jobs_and_events_after_the_cutoff_stay_out`、`test_a_missing_or_conflicting_exposure_stays_on_that_ticker`、`test_no_ticker_does_not_invent_an_affected_row`。原因写在 PR #47。
- 证据：`tests/m8/test_b039.py` 4 项。本地 `make phase1-test` 442 passed、21 deselected，用时 66.64 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.41 秒。
- CI 还在跑：https://github.com/XuQingsong/inves-cog/actions/runs/39715004161
- 历史回补仍按整包完整。已经存下的 degraded 行读出来仍不完整。没有新迁移，没有新角色。没有改 M9、M4、规则 A。没有部署，没有生产回放。
- 第 2、3 部分还没开始。
- 下一步：这一版 phase1-blocking 绿了再记第 1 部分可验收。不把 B-039 标成已完成。

## B-039  已收到  2026-10-22 11:01 北京

- 用户决策 UD-COORD-27：M8 归因链可以进生产每日运行，并对最近 5 个交易日做一次回放。由此产生的模型调用已同意，但执行前先报次数和费用，需求方确认后由 A 线执行。B 不调模型，不部署，不在生产执行回放。
- 第 1 部分仍在草稿 PR #47，分支 `cursor/m8-b036-pit-snapshot-e013`。整日 `complete` 只看三个阶段在快照时钟前以 `ok` 结束并且快照写上。字段缺口留在事件和 `missing.fields`，不再把整日降成 degraded。没有 cutoff 前 lifecycle 的事件保留，`lifecycle` 为空并写原因，不删事件，也不降级整日。读取只拒绝晚于 cutoff 的时间。阶段缺失、失败或晚于 cutoff 仍不写快照。
- 第 2、3 部分另开 PR。早页用现有 store 落库，不额外加模型调用；09:30 和 12:30 读上一阶段并保存，labels 成功后写快照。五日回放用隔离存储，不写生产 M8 实时表。`historical_backfill` 的 `snapshot_generated_at` 是实际运行时钟。`--dry-run` 不调模型，只报预计次数。
- 不改 M7、M9、M4、规则 A、来源、角色或权限。不新增正式 schema。
- 下一步：先改第 1 部分会失败的例子。

## B-038  已完成  2026-10-22 10:00 北京

- 草稿 PR #47，head `b659c75`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39708622204 。`phase1-blocking` 438 passed、21 deselected，用时 119.57 秒，nightly 跳过。没有合并。
- 证据：例子先失败，两只股票被收成一个列表，不能当映射键。改完之后 `tests/m8/test_b038.py` 6 项通过，`tests/m8/test_b035.py` 5 项、`tests/m8/test_b036.py` 13 项仍通过。本地 `make phase1-test` 438 passed、21 deselected，用时 66.95 秒；`make phase1-cases` 7 passed、1 xfailed，用时 26.15 秒。
- 一个事件多只标的时，`affected` 一条记录对应一只，ticker 和 exposure 都是单值。某一只暴露缺失或冲突时只标这一只，不挑值，也不清掉其他标的。没有标的来源时不造记录。单标的仍是一条。
- 报告里没有 divergence 或 next filing、没有唯一 claim 方向、没有 cutoff 前的 lifecycle 历史、某一只暴露缺失或冲突时，这些字段仍是 NULL，不能标完整。完成标记、`source_asof`、注入时钟和 lifecycle 不改。
- 只追加。没有新迁移，没有新角色。没有改 M9、M4、规则 A。没有生产迁移或回填。
- 下一步：等需求方验收。不取新任务。

## B-038  进行中  2026-10-22 09:59 北京

- 草稿 PR #47，head `b659c75`，分支 `cursor/m8-b036-pit-snapshot-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/47
- 例子先失败：两只股票被收成一个列表，不能当映射键。改完之后 `tests/m8/test_b038.py` 6 项通过，`tests/m8/test_b035.py` 5 项、`tests/m8/test_b036.py` 13 项仍通过。
- 本地 `make phase1-test` 438 passed、21 deselected，用时 66.95 秒；`make phase1-cases` 7 passed、1 xfailed，用时 26.15 秒。CI 还在跑：https://github.com/XuQingsong/inves-cog/actions/runs/39708622204
- 一个事件多只标的时，`affected` 一条记录对应一只，ticker 和 exposure 都是单值。某一只暴露缺失或冲突时只标这一只，不挑值，也不清掉其他标的。没有标的来源时不造记录。单标的仍是一条。
- 完成标记、`source_asof`、注入时钟和 lifecycle 不改。缺任一必需字段时快照仍是 degraded。没有新迁移，没有新角色。没有改 M9、M4、规则 A。
- 下一步：CI 绿了再写已完成。

## B-038  已收到  2026-10-22 09:52 北京

- 任务：B-037 验收修复。PR #47 保持草稿，仍在 `cursor/m8-b036-pit-snapshot-e013`。一个事件有多只标的时，`affected` 一条记录对应一只标的。每条的 `ticker`、`exposure` 都是单值，M9 能拿它当映射键。
- 同一标的上多来源的暴露不一致时，只把这一只的暴露留空并写冲突原因，不挑一个更可行动的值，也不清掉其他已经完整的标的。某一只没有暴露时，只标这一只。没有标的来源时不造受影响标的。单标的仍是一条记录。
- 事件级的 divergence 和 next filing 仍来自报告；抄到每条记录上。某一只自己的来源和报告或其他来源冲突时，只把这一只的该项留空。完成标记、`source_asof`、注入时钟和 lifecycle 规则不改。缺任一必需字段时快照仍是 degraded，`complete` 为 false。
- 不改 M9、M4、schema、角色或来源。不部署，不回填生产。
- 下一步：先写会失败的例子，再改展开。

## B-037  已完成  2026-10-22 00:42 北京

- 草稿 PR #47，head `e584e34`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39636642198 。`phase1-blocking` 432 passed、21 deselected，用时 98.55 秒，nightly 跳过。没有合并。
- 证据：例子先失败，因为有 mechanism 时仍被要求整行清空，降级快照也不返回已保存的字段。改完之后 `tests/m8/test_b035.py` 5 项、`tests/m8/test_b036.py` 13 项通过。本地 `make phase1-test` 432 passed、21 deselected，用时 67.97 秒；`make phase1-cases` 7 passed、1 xfailed，用时 26.11 秒。
- 三个阶段成功后的同一次读取保留当时已有的 mechanism、暴露、claim 方向、当日 tracks、报告里的 divergence 和 next filing、deadline、当日系统性标记。缺一项只记这一项。lifecycle 仍只取 `history.at` 不晚于时钟的版本。异常涨跌方向不写入事件方向。
- 没有自己时间戳的当前值，字段时间是这次注入时钟，不回写成更早的作业结束时间。`source_asof` 仍是三个作业结束时间的最晚值。缺任一必需字段时快照保持 degraded，`complete` 为 false，`source_events_asof` 为空。
- 报告里没有 divergence 或 next filing、没有唯一 claim 方向、没有 cutoff 前的 lifecycle 历史时，这些字段仍是 NULL，不能标完整。历史回填仍只接受原来带时间的来源。
- 只追加。没有新迁移，没有新角色。没有改 M9、M4、规则 A。没有生产迁移或回填。
- 下一步：等需求方验收。不取新任务。

## B-037  进行中  2026-10-22 00:41 北京

- 草稿 PR #47，head `e584e34`，分支 `cursor/m8-b036-pit-snapshot-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/47
- 例子先失败：`test_fields_without_a_source_time_stay_null` 仍要求 mechanism 为空，`test_degraded_snapshot_is_not_a_complete_overlay` 仍要求降级快照不返回已保存的字段。改完之后 `tests/m8/test_b035.py` 5 项、`tests/m8/test_b036.py` 13 项通过。
- 本地 `make phase1-test` 432 passed、21 deselected，用时 67.97 秒；`make phase1-cases` 7 passed、1 xfailed，用时 26.11 秒。CI 还在跑：https://github.com/XuQingsong/inves-cog/actions/runs/39636642198
- 三个阶段成功后的同一次读取保留当时已有的 mechanism、暴露、claim 方向、当日 tracks、报告里的 divergence 和 next filing、deadline、当日系统性标记。缺一项只记这一项。lifecycle 仍只取 `history.at` 不晚于时钟的版本。异常涨跌方向不写入事件方向。
- 没有自己时间戳的当前值，字段时间是这次注入时钟，不回写成更早的作业结束时间。`source_asof` 仍是三个作业结束时间的最晚值。缺任一必需字段时快照保持 degraded，`complete` 为 false，`source_events_asof` 为空。
- 报告里没有 divergence 或 next filing、没有唯一 claim 方向、没有 cutoff 前的 lifecycle 历史时，这些字段仍是 NULL。历史回填仍只接受原来带时间的来源。
- 只追加。没有新迁移，没有新角色。没有改 M9、M4、规则 A。没有生产迁移或回填。
- 下一步：CI 绿了再写已完成。

## B-037  已收到  2026-10-22 00:33 北京

- 任务：B-036 验收修复。PR #47 保持草稿，仍在 `cursor/m8-b036-pit-snapshot-e013`。三个阶段成功结束后，同一读取里带上当时 M8 表里已经有的字段。不能因为一个字段没有单独时间，就把同一事件里其他有值的字段抹掉。
- 用户决策 UD-COORD-26 仍然只覆盖这张 append-only 快照表和既有角色的最小权限。不新建角色，不扩大其他表的权限。
- 生命周期仍取 `history.at` 不晚于 cutoff 的版本，不用更晚的当前列。没有来源值，或无法证明可见时间的字段，保持 NULL 和字段级原因。异常表的涨跌方向不当作事件方向。没有单独时间戳的当前列，字段时间记这次注入时钟的观察时间，不回写成更早的作业结束时间。`source_asof` 仍是三个作业结束时间的最晚值。
- 能取到的字段仍缺 M9 必需项时，快照保持 degraded，不标完整。历史回填仍只接受原来带时间的来源，不用当前值追认过去。
- 不改 M9 `overlay`/`shadow`、M4、规则 A、来源或生产库。不部署，不回填生产。
- 下一步：先改会失败的例子，再改写入。

## B-036  已完成  2026-10-21 19:18 北京

- 草稿 PR #47，head `36abb4d`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39590365749 。`phase1-blocking` 429 passed、21 deselected，用时 114.97 秒，nightly 跳过。没有合并。
- 证据：读取原先把当时的作业当成完整快照，例子因此失败。改完之后 `tests/m8/test_b035.py` 4 项、`tests/m8/test_b036.py` 11 项通过。本地 `make phase1-test` 429 passed、21 deselected，用时 65.08 秒；`make phase1-cases` 7 passed、1 xfailed，用时 26.22 秒。
- 三个阶段都成功且没有事件时，追加一份 complete 空快照。`snapshot_generated_at` 是注入时钟。`source_asof` 是三个作业结束时间的最晚值。
- 从现有表组装时，只有 `history.at` 能证明 lifecycle 和 evidence_ids。mechanism、exposure、direction、divergence、dimensions、next filing、systemic tag、deadline outcome 没有来源时间，快照是 degraded，不会被读成 complete。
- 只追加。`role_perception` 只有 SELECT 和 INSERT，`role_shadow` 只有 SELECT。没有新角色。没有改 M9、M4、规则 A。没有生产迁移或回填。
- 下一步：等需求方验收。不取新任务。合并后由 A 在 M9 分支接入 provider。

## B-036  进行中  2026-10-21 19:16 北京

- 草稿 PR #47，head `36abb4d`，分支 `cursor/m8-b036-pit-snapshot-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/47
- 读取原先把当时的作业当成完整快照，例子因此失败。改完之后 `tests/m8/test_b035.py` 4 项、`tests/m8/test_b036.py` 11 项通过。其中角色边界在整库测试里通过。
- 本地 `make phase1-test` 429 passed、21 deselected，用时 65.08 秒；`make phase1-cases` 7 passed、1 xfailed，用时 26.22 秒。CI 还在跑。
- 三个阶段都成功且没有事件时，追加一份 complete 空快照。`snapshot_generated_at` 是注入时钟。`source_asof` 是三个作业结束时间的最晚值。
- 从现有表组装时，只有 `history.at` 能证明 lifecycle 和 evidence_ids。mechanism、exposure、direction、divergence、dimensions、next filing、systemic tag、deadline outcome 没有来源时间，快照是 degraded，不会被读成 complete。
- 只追加。`role_perception` 只有 SELECT 和 INSERT，`role_shadow` 只有 SELECT。没有新角色。没有改 M9、M4、规则 A。没有生产迁移或回填。
- 下一步：CI 绿了再写已完成。

## B-036  已收到  2026-10-21 19:00 北京

- 用户决策 UD-COORD-26：M8 PIT provider 是必须项，直接开始。任务书记载用户要求直接开始。照做：只为本单新增最小 append-only `perception.m9_input_snapshots`，以及 `role_perception` 的 INSERT/必要只读和 `role_shadow` 的 SELECT。不是一般性放开 schema 或权限。不新建角色。
- 任务：三个归因阶段都在 cutoff 前以成功结束时，用注入时钟写下不可变快照。M9 只读 `snapshot_generated_at` 不晚于 cutoff 的最近完整快照。没有可信来源时间的字段写 NULL 和原因，不用当前值追认历史。不能 UPDATE 或 DELETE。历史回填只在原始来源编号和发布时间能证明时才允许，并标明 backfill，不让它出现在更早的页面。
- 从最新 `origin/main` 开新分支，开新 PR。只改快照迁移、M8 完成后的写入、provider 读取和对应测试。不改 `overlay`/`shadow`、M4、规则 A、阈值、外部数据源或模型。不连生产库，不回填生产，不部署。
- 下一步：先写会失败的例子，再补迁移和写入。

## B-035  已完成  2026-10-21 17:47 北京

- 草稿 PR #46，head `513459f`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39579381063 。`phase1-blocking` 420 passed、21 deselected，用时 53.61 秒，nightly 跳过。没有合并。
- 证据：例子先因没有 `snapshot` 模块而失败。改完之后 `tests/m8/test_b035.py` 6 passed。本地 `make phase1-test` 420 passed、21 deselected，用时 67.05 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.60 秒。
- `complete` 需要 `attribution_candidates`、`attribution_tracks`、`attribution_labels` 都在该交易日、cutoff 前以 `ok` 结束。三阶段都成功且没有事件时，空列表表示已经查过。事件版本只取 `history.at` 不晚于 cutoff 的最后一条。`generated_at` 更晚的异常不进入快照。`source_events_asof` 用作业真实结束时间，不用 cutoff 本身。
- 有事件时不算完整输入。`mechanism`、`deadline_outcome`、`exposure`、`affected`、`direction`、`divergence_tag`、`dimensions`、`next_filing_at` 没有可证明的历史时间，原因写在 `missing.fields`。没有历史时间的行不会被当成当时的生命周期。不回填，不从当前报告反推。
- 读取使用调用方连接上的 `REPEATABLE READ READ ONLY`，读完回滚。不 `SET ROLE`，不加 schema、角色或权限。`role_shadow` 仍不能读这些表。不改 M9、M4、规则 A，不连生产库，不调模型，不部署，不手动跑线上 M8/M9。
- 下一步：等需求方验收。不取新任务。合并后由 A-015 接上这个适配器。

## B-035  进行中  2026-10-21 17:46 北京

- 草稿 PR #46，head `513459f`，分支 `cursor/m8-b035-pit-snapshot-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/46
- 例子先因没有 `snapshot` 模块而失败。改完之后 `tests/m8/test_b035.py` 6 passed。本地 `make phase1-test` 420 passed、21 deselected，用时 67.05 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.60 秒。CI 还在跑。
- `complete` 需要 `attribution_candidates`、`attribution_tracks`、`attribution_labels` 都在该交易日、cutoff 前以 `ok` 结束。三阶段都成功且没有事件时，空列表表示已经查过。事件版本只取 `history.at` 不晚于 cutoff 的最后一条。`generated_at` 更晚的异常不进入快照。
- 有事件时不算完整输入。`mechanism`、`deadline_outcome`、`exposure`、`affected`、`direction`、`divergence_tag`、`dimensions`、`next_filing_at` 没有可证明的历史时间，原因写在 `missing.fields`。没有历史时间的行不会被当成当时的生命周期。
- 读取使用调用方连接上的 `REPEATABLE READ READ ONLY`，读完回滚。不 `SET ROLE`，不加 schema、角色或权限。不改 M9、M4、规则 A，不连生产库，不调模型，不部署。
- 下一步：CI 绿了再写已完成。

## B-035  已收到  2026-10-21 17:40 北京

- 任务：为 M9 提供 PIT 安全的 M8 只读快照。完成与否看 `ingest.job_runs` 的交易日、成功状态和 `ended_at <= cutoff`。返回 `complete`、`source_events_asof`、事件、source IDs 和逐字段缺失原因。晚于 cutoff 的事件不进入快照。历史没有可证实的生成时间时显式 incomplete，不从当前报告反推，不伪造时间，不回填。
- 从最新 `origin/main` 开新分支，开新 PR。只改 `perception.attribution` 和对应测试。不改 A-015 的 `overlay`/`shadow`，不改 M9、M4、规则 A。不新增 schema、角色、权限或数据源。不连生产库，不调模型，不部署，不手动跑线上 M8/M9。
- 下一步：对照 PR #45 head `2de34aa` 的 `m8_provider` 合同和现有 M8 作业记录，先写会失败的例子。

## B-034  已完成  2026-10-21 13:10 北京

- 草稿 PR #44，head `2433af1`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39547698182 。`phase1-blocking` 414 passed、21 deselected，用时 97.14 秒，nightly 跳过。没有合并。
- 证据：三个早报例子先失败（九点十五把前一交易日已经可见的估值漏成「今天没有拿到估值」；一只没有估值时另一只也没出现；缺失句的检查范围写宽了，计划金额里的 `10.00` 被当成填了 0）。改完之后 `tests/m8/test_b034.py` 5 passed。同一天的旧文案没有改。本地 `make phase1-test` 414 passed、21 deselected，用时 66.66 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.89 秒。
- 早报每只股票取 `trade_date` 不晚于报告交易日、`observed_at` 不晚于页面时刻的最新一行。页上保留估值自己的日期。价格仍用报告日收盘价。两个日期不同时写成「估值 YYYY-MM-DD，价格 YYYY-MM-DD」。没有可见行时仍写「今天没有拿到估值」。没有新增过期天数门槛。
- 没有改 M5 算法、参数或库里的估值。没有改 M1、M4、M7、规则 A。没有回填，没有连接生产库，没有调模型，没有部署，没有重算估值。合并后由 A-014 看一次自然九点十五的早报。
- 下一步：等需求方验收。不取新任务。

## B-034  进行中  2026-10-21 13:09 北京

- 草稿 PR #44，head `2433af1`，分支 `cursor/m8-b034-valuation-pit-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/44
- 三个早报例子先失败：九点十五把前一交易日已经可见的估值漏成「今天没有拿到估值」；一只没有估值时另一只也没出现；缺失句的检查范围写宽了，计划金额里的 `10.00` 被当成填了 0。改完之后 `tests/m8/test_b034.py` 5 passed。同一天的旧文案没有改。
- 本地 `make phase1-test` 414 passed、21 deselected，用时 66.66 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.89 秒。CI 还在跑。
- 早报每只股票取 `trade_date` 不晚于报告交易日、`observed_at` 不晚于页面时刻的最新一行。页上保留估值自己的日期。价格仍用报告日收盘价。两个日期不同时写成「估值 YYYY-MM-DD，价格 YYYY-MM-DD」。没有可见行时仍写「今天没有拿到估值」。
- 没有改 M5 算法、参数或库里的估值。没有改 M1、M4、M7、规则 A。没有回填，没有连接生产库，没有调模型，没有部署。
- 下一步：CI 绿了再写已完成。

## B-034  已收到  2026-10-21 13:00 北京

- 任务：早报每只股票取页面截止时刻已经可见的最新估值。`trade_date` 不晚于报告交易日，`observed_at` 不晚于页面时刻。同一 ticker 取交易日最大的一份，同一天再取 `observed_at` 最新的一份。页上写出这份估值的实际日期，不把上一交易日写成当天。价格仍用报告日收盘价；估值日和价格日不同时标出来。没有任何符合条件的估值时，仍写「今天没有拿到估值」。
- 从最新 `origin/main` 开新分支，开新 PR。只改 `perception.attribution.morning` 的估值读取和展示。不改 M5 算法、参数或库里的估值。不连生产库，不调模型，不回填，不部署。
- 下一步：先写会失败的例子，再改早报查询。

## B-033  已完成  2026-10-21 11:22 北京

- 草稿 PR #43，head `69caa6f`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39537938750 。`phase1-blocking` 409 passed，用时 74.98 秒，nightly 跳过。没有合并。
- 证据：七个宽池例子先失败（因子仍是 NULL，失败运行没有标 degraded）。股票池原路径本来就通过。改完之后 `tests/m1/test_b033.py` 8 passed。本地 `make phase1-test` 409 passed、21 deselected，用时 68.40 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.75 秒。
- 用户决策 UD-B-06：宽池日线的拆股因子怎么补。用户原话「m1修复就按照你推荐的做吧」。照做：只改 `Pipeline.wide`，用已有公司行动接口。核实无拆股写 1.0。失败、分页重复或不完整时留 NULL，运行标 degraded。一批失败不抹掉另一批。开高低收和成交量仍是 raw。`post_close` 不更新。股票池 `bars` 不改。
- 报告计数：`adj_factor_split`、`adj_factor_unity`、`adj_factor_null`。代码测试通过不等于生产数据已修好。
- 没有连接生产库，没有回填，没有跑线上 `wide_universe`，没有调模型。没有改其他 M1 模块、M6/M7、阈值、schema、`golden/`、`milestones.txt`。生产核对留到合并后，由 A-014 用一次自然 `wide_universe` 做。
- 下一步：等需求方验收。不取新任务。

## B-033  进行中  2026-10-21 11:21 北京

- 草稿 PR #43，head `69caa6f`，分支 `cursor/m1-b033-wide-split-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/43
- 用户决策 UD-B-06 已写在已收到里。七个宽池例子先失败：因子仍是 NULL，失败运行没有标 degraded。股票池原路径本来就通过。改完之后 `tests/m1/test_b033.py` 8 passed。
- 本地 `make phase1-test` 409 passed、21 deselected，用时 68.40 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.75 秒。CI 还在跑。
- `Pipeline.wide` 按最多 200 个代码一批，调用已有公司行动接口。核实无拆股写 1.0。失败、分页重复或不完整时留 NULL，运行标 degraded。一批失败不抹掉另一批。开高低收和成交量仍是 raw。`post_close` 不更新。股票池 `bars` 不改。
- 报告计数：`adj_factor_split`、`adj_factor_unity`、`adj_factor_null`。
- 没有连接生产库，没有回填，没有跑线上 `wide_universe`，没有调模型。没有改其他 M1 模块、M6/M7、阈值、schema、`golden/`、`milestones.txt`。
- 下一步：CI 绿了再写已完成。

## B-033  已收到  2026-10-21 11:14 北京

- 用户决策 UD-B-06：宽池日线的拆股因子怎么补。用户原话「m1修复就按照你推荐的做吧」。照做：只改 `Pipeline.wide`，用已有 `Alpaca.daily_bars`、`alpaca_splits`、`split_factors` 给宽池原始日线写入核实过的 `adj_factor`。确认窗口内没有拆股时写 1.0；查询失败或不完整时保持 NULL，并让任务结果标成 degraded。不补 `post_close`，不改其他 M1 模块、M6/M7 计算、阈值、schema、权限、规则 A、golden。
- 任务是一次性跨线修复。B-032 已验收合并，PIT 生成时间保护保留，不回填旧异常时间。原 M1/M2 只读边界其余保持。
- 从最新 `origin/main` 开新分支，开新 PR。不连生产库，不回填生产数据，不跑线上 `wide_universe`。不调模型。不改 `docs/`、`golden/`、`milestones.txt`。
- 变更：宽池 `bars_daily` 的 upsert 更新列加上 `adj_factor`。开高低收和成交量仍是 raw。
- 下一步：先写会失败的例子，再改 `Pipeline.wide`。

## B-032  已完成  2026-10-21 10:38 北京

- 草稿 PR #42，head `3e55dbc`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39533772102 。`phase1-blocking` 401 passed，用时 115.98 秒，nightly 跳过。没有合并。
- 证据：五个早报例子先失败（晚生成的仍可见，没有生成时间的旧行仍可见，`--at` 只传了交易日，写入还不接收 `generated_at`）。改完之后通过。本地 `make phase1-test` 401 passed、21 deselected，用时 66.42 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.51 秒。
- `perception.anomalies.generated_at` 可空，迁移不回填。新写入用注入时钟的 `now_utc()`。早报只取交易日对上、生成时间非空且不晚于这次运行的异常。`--at` 重出旧早报时，后补的行不可见。
- M6：当日收盘价在，宽池 `adj_factor` 和 `post_close` 为空，写入者是 `Pipeline.wide` / `Alpaca.daily_bars`（`adjustment=raw`，`source=Alpaca`）。`missing_current_return` 1087 与 `sector_unmapped;missing_current_return` 141 是上游缺口。`missing_post_price` 1089 含那 2 个 close 上的 `insufficient_history`，盘后空价盖住了模型原因，本单不改标签。`sector_unmapped`、`l3_same_as_l2`、`insufficient_history` 是预期降级。`l3_same_as_l2` 的收益和残差仍有效。1,253 个空原因没有清掉。
- 已自行决定：不把空的 `adj_factor` 填成 1.0，不降低 60 天窗口，不改 `ingest`。逐票名单在 A 的私有证据里，不在本仓库，报告不列 1,228 个代码。
- 没有发起真实模型调用，没有连接生产库。没有改 `docs/`、`golden/`、`milestones.txt`。不回填历史异常，不重跑 job 8750。生产迁移留到合并后按 A-014 执行。
- 下一步：等需求方验收。不取新任务。

## B-032  进行中  2026-10-21 10:32 北京

- 草稿 PR #42，head `3e55dbc`，分支 `cursor/m7-b032-pit-visibility-e013`。没有合并。https://github.com/XuQingsong/inves-cog/pull/42
- 五个早报例子先失败：晚生成的仍可见，没有生成时间的旧行仍可见，`--at` 只传了交易日，写入还不接收 `generated_at`。改完之后 `tests/m7/test_b032.py` 通过。全套测试还在跑。
- `perception.anomalies.generated_at` 可空，迁移不回填。新写入用注入时钟的 `now_utc()`。早报只取交易日对上、生成时间非空且不晚于这次运行的异常。`--at` 重出旧早报时，后补的行不可见。
- M6 空原因不在本线改计算。当日收盘价在，宽池 `adj_factor` 和 `post_close` 为空，写入者是 `Pipeline.wide` / `Alpaca.daily_bars`（`adjustment=raw`，`source=Alpaca`）。`missing_current_return` 和 `missing_post_price` 是上游缺口。`sector_unmapped`、`l3_same_as_l2`、`insufficient_history` 是预期降级。`l3_same_as_l2` 的收益和残差仍有效。那 2 个样本不足在 post 上被 `missing_post_price` 盖住，本单不改标签。1,253 个空原因没有清掉。
- 已自行决定：不把空的 `adj_factor` 填成 1.0，不降低 60 天窗口，不改 `ingest`。逐票名单在 A 的私有证据里，不在本仓库，报告不列 1,228 个代码。
- 没有发起真实模型调用，没有连接生产库。没有改 `docs/`、`golden/`、`milestones.txt`。不回填历史异常，不重跑 job 8750。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-032  已收到  2026-10-21 10:20 北京

- 任务分两块。A：`perception.anomalies` 增加实际生成时间，新写入用注入的 `Clock`，历史回放记真实计算时间。早报只取 `trade_date` 对应且 `generated_at` 不晚于页面运行时刻的异常；NULL 或更晚的都不可见。旧行不按交易日回填。B：按 close/post、pool/wide、ticker/source 分层，查清 2026-10-21 自然运行里 `null_reason` 的直接原因。能在本线修的、且不改冻结阈值和接口的，先红后绿修；上游缺口只报告，不越界改。
- 从最新 `origin/main` 开新分支 `cursor/m7-b032-pit-visibility-e013`，开新 PR。不改异常阈值、golden、规则 A、M1 ingestion 契约。不跑生产写任务，不回填历史异常或 marketstate，不重跑 job 8750。不调模型，不连生产库，不改 `docs/`、`golden/`、`milestones.txt`。
- 变更：新增一列生成时间，迁移遵守 M0 schema/权限合同。生产迁移留到 PR 合并后按 A-014 执行。
- 下一步：先写五个失败例子，再补迁移和早报过滤；同时追查 M6 缺失来自哪一行、哪一步。

## B-031  已完成  2026-10-20 00:43 北京

- 草稿 PR #38，head `f110f82`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39286958913 。`phase1-blocking` 354 passed，用时 109.24 秒，nightly 跳过。没有合并。
- 证据：四个例子先失败（十条仍按回答顺序全印，三条不按强弱排，没有强弱的排不进最后，第四条弱的也印了出来）。全页用语这一条本来就会过。五个例子随后都通过。本地 `make phase1-test` 354 passed、21 deselected，用时 66.69 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.68 秒。
- 每次波动最多印 3 条原因，先强，再中，再弱，没有强弱的排最后。同一档按回答里的先后。多于 3 条写「另有 N 条较弱的可能原因」。当时看到了吗仍按全部能解释的原因判断。没有原因时仍写「可能的原因：没找到能解释这次波动的新闻」。
- 已自行决定：晚于波动起点的新闻本来就不会送给模型，引用了也会丢掉，所以例子 4 不能把三条强写成起点之后才发布。这三条用波动当天、钟点不清楚，当时已经知道为假；那条弱早于起点且钟点清楚，当时已经知道为真。印出来的三条强自己不会写成「波动前已经看到这条新闻」，没印出来的那条弱会。
- 没有发起真实模型调用，没有连接真实数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改问法和送去的新闻，没有改「能解释」为否的不印，没有改其他几节。不部署，不加定时任务配置。
- 下一步：等需求方验收。不取新任务。

## B-031  进行中  2026-10-20 00:37 北京

- 草稿 PR #38，head `f110f82`，分支 `cursor/m8-b031-top-reasons-e013`。没有合并。
- 四个例子先失败：十条仍按回答顺序全印，三条不按强弱排，没有强弱的排不进最后，第四条弱的也印了出来。全页用语这一条本来就会过。改完之后 `tests/m8/test_b031.py` 通过。全套测试还在跑。
- 每次波动最多印 3 条原因，先强，再中，再弱，没有强弱的排最后。同一档按回答里的先后。多于 3 条写「另有 N 条较弱的可能原因」。当时看到了吗仍看全部能解释的原因。
- 已自行决定：晚于波动起点的新闻本来就不会送给模型，引用了也会丢掉，所以例子 4 不能把三条强写成起点之后才发布。这三条用波动当天、钟点不清楚，当时已经知道为假；那条弱早于起点且钟点清楚，当时已经知道为真。印出来的三条强自己不会写成「波动前已经看到这条新闻」，没印出来的那条弱会。
- 没有发起真实模型调用，没有连接真实数据库。没有改 `docs/`、`golden/`、`milestones.txt`。不改问法和送去的新闻。不部署，不加定时任务配置。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-031  已收到  2026-10-20 00:30 北京

- 任务：每次波动最多印 3 条原因，先强，再中，再弱，没有强弱的排最后。同一档按模型回答里的先后。多于 3 条时写「另有 N 条较弱的可能原因」。当时看到了吗仍按全部能解释的原因判断。
- 入口是北京 09:15 的 `run_scheduled`，看那一页的文字。从最新 `origin/main`（含 PR #37）开新分支 `cursor/m8-b031-top-reasons-e013`，开新 PR。
- 不改问法和送去的新闻，不改「能解释」为否的不印，不改其他几节。没有原因时仍写「可能的原因：没找到能解释这次波动的新闻」。B-030 不打回。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：先写五个失败例子，再改印出的条数和顺序。

## B-030  已完成  2026-10-20 00:20 北京

- 草稿 PR #37，head `84b516b`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39280934913 。`phase1-blocking` 349 passed，用时 111.67 秒，nightly 跳过。没有合并。
- 证据：八个例子先失败（认不出 `matches`、`answer`、`cards`，能解释为否的仍印出来，送去的方向还是 `down`，周六不写页，计划行印出 `buy_to`）。`{"解释": "没有"}` 这一条本来就会过。九个例子随后都通过。本地 `make phase1-test` 349 passed、21 deselected，用时 63.93 秒；`make phase1-cases` 7 passed、1 xfailed，用时 25.73 秒。
- 波动那一问写明回答的样子，并认已经见过的栏名。送给模型的波动和页上那一行同一套算法。能解释为否的不印，也不算已经看到。页上每条带强、中、弱。北京早上只在纽约那一天是交易日时写页：周六写周五的页，周日、周一和美东假日后的早上不写、不调模型。计划行用中文 `label`，金额用 `value`，空了用 `notional_est`。
- 已自行决定：动作里含有英文字母就当成英文代码，页上不印。调用方已经给了中文涨跌和幅度的，送给模型时仍按原样。缺「能解释」的仍印。百分数一位、半分向偶数靠，沿用 B-029。B-029 把周六跳过是需求方后来指出的错例，这一版按纽约那一天是不是交易日判断。旧例子里动作是英文代码、没有 `label` 的，页上不再印那个代码。
- 没有发起真实模型调用，没有连接真实数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改送哪些新闻、最多 40 条，没有改新闻摘要的问法，没有改估值、计划和持仓的计算。不部署，不加定时任务配置。
- 下一步：等需求方验收。不取新任务。

## B-030  进行中  2026-10-19 23:50 北京

- 草稿 PR #37，head `84b516b`，分支 `cursor/m8-b030-move-reply-e013`。没有合并。
- 八个例子先失败：认不出 `matches`、`answer`、`cards`，能解释为否的仍印出来，送去的方向还是 `down`，周六不写页，计划行印出 `buy_to`。`{"解释": "没有"}` 这一条本来就会过。改完之后 `tests/m8/test_b030.py` 通过。全套测试还在跑。
- 波动那一问写明回答的样子，并认已经见过的栏名。送给模型的波动和页上那一行同一套算法。能解释为否的不印。北京周六写周五的页；周日、周一和美东假日后的早上不写。计划行用中文 `label`，金额用 `value`，空了用 `notional_est`。
- 已自行决定：动作里含有英文字母就当成英文代码，页上不印。调用方已经给了中文涨跌和幅度的，送给模型时仍按原样。缺「能解释」的仍印。百分数一位、半分向偶数靠，沿用 B-029。B-029 把周六跳过是需求方后来指出的错例，这一版按纽约那一天是不是交易日判断。旧例子里动作是英文代码、没有 `label` 的，页上不再印那个代码。
- 没有发起真实模型调用，没有连接真实数据库。没有改 `docs/`、`golden/`、`milestones.txt`。不部署，不加定时任务配置。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-030  已收到  2026-10-19 23:40 北京

- 任务：波动那一问写明回答的样子，并认已经见过的栏名，不再把回答丢掉。送去的波动和页上那一行同一套算法。能解释为否的不印。页上每条带强中弱。北京周二到周六早上写页，周日、周一和美东假日后的那个早上不写。计划行用 `label`，金额用 `value`，空了用 `notional_est`。
- 入口是北京 09:15 的 `run_scheduled`，以及 `morning` 命令判断是不是那一刻。从最新 `origin/main`（含 PR #35）开新分支 `cursor/m8-b030-move-reply-e013`，开新 PR。
- 不改送哪些新闻、最多 40 条，不改新闻摘要的问法，不改估值、计划、持仓的计算。B-029 不打回。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：先写九个失败例子，再改这一问和周六、计划行。

## B-029  已完成  2026-10-19 23:20 北京

- 草稿 PR #35，head `2cffe0b`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39276636354 。`phase1-blocking` 340 passed，用时 107.24 秒，nightly 跳过。没有合并。
- 证据：七个例子先失败（命令模块不存在），再通过。本地 `make phase1-test` 340 passed、21 deselected，用时 66.82 秒；`make phase1-cases` 7 passed、1 xfailed，用时 26.53 秒。
- 命令 `python -m inves_cog.perception.attribution.morning`。是早上那一页的时刻才取波动、新闻、估值、计划和持仓，只取那一刻已经知道的，交给 `run_scheduled`。不传 `news_lookup`。页写到 `INVES_COG_PAGE_DIR`，没配就打印。运行照现有方式记一行。`--at` 用来补跑。
- 某一类没取到，页照写，用「今天没有拿到持仓」「今天没有拿到估值」「今天没有拿到计划」。问模型失败时，那次波动写「可能的原因：这次没问到，下次运行再试」，运行记录留下原因，页上没有报错原文。
- 已自行决定：新闻发布时刻不早于该交易日前 7 个自然日的纽约零点，不晚于这次运行，并且 `first_seen_at` 不晚于这次运行。计划交给页面时用刚收盘的交易日，不用计划表里的下一交易日。持仓和计划可以分开交：`daily_text` 增加可选的 `holdings`，缺省仍从计划行里读，旧调用不变。百分数一位，半分向偶数靠，这样 −0.25% 写成 0.2%；B-028 的例子不是半分，结果不变。北京周六即使钟点对上也不写页，周日不跳。问模型失败先把页写完再把这次运行记成失败。目录不存在就创建。页上原有的「规则 A」保留。
- 没有发起真实模型调用，没有连接真实数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改检测、估值和交易的计算。不改新闻卡和波动卡问法。不部署，不加定时任务配置。
- 下一步：等需求方验收。不取新任务。

## B-029  进行中  2026-10-19 23:17 北京

- 草稿 PR #35，head `2cffe0b`，分支 `cursor/m8-b029-morning-job-e013`。没有合并。
- 七个例子先失败：命令模块不存在。接上之后 `tests/m8/test_b029.py` 通过。全套测试还在跑。
- 命令 `python -m inves_cog.perception.attribution.morning`。是早上那一页的时刻才取波动、新闻、估值、计划和持仓，只取那一刻已经知道的，交给 `run_scheduled`。不传 `news_lookup`。页写到 `INVES_COG_PAGE_DIR`，没配就打印。运行照现有方式记一行。`--at` 用来补跑。
- 某一类没取到，页照写，用「今天没有拿到持仓」「今天没有拿到估值」「今天没有拿到计划」。问模型失败时，那次波动写「可能的原因：这次没问到，下次运行再试」，运行记录留下原因，页上没有报错原文。
- 已自行决定：新闻发布时刻不早于该交易日前 7 个自然日的纽约零点，不晚于这次运行，并且 `first_seen_at` 不晚于这次运行。计划交给页面时用刚收盘的交易日，不用计划表里的下一交易日。持仓和计划可以分开交：`daily_text` 增加可选的 `holdings`，缺省仍从计划行里读，旧调用不变。百分数一位，半分向偶数靠，这样 −0.25% 写成 0.2%；B-028 的例子不是半分，结果不变。北京周六即使钟点对上也不写页，周日不跳。问模型失败先把页写完再把这次运行记成失败。目录不存在就创建。
- 没有发起真实模型调用，没有连接真实数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改检测、估值和交易的计算。不改新闻卡和波动卡问法。不部署，不加定时任务配置。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-029  已收到  2026-10-19 23:00 北京

- 任务：早上 09:15 自己取数据，写出那一页。新命令 `python -m inves_cog.perception.attribution.morning`。是早上那一页的时刻才取波动、新闻、估值、计划和持仓，只取那一刻已经知道的，交给 `run_scheduled`。页写到 `INVES_COG_PAGE_DIR`，没配就打印。运行照现有方式记一行。`--at` 用来补跑。
- 入口是这个命令。从最新 `origin/main`（含 PR #34）开新分支 `cursor/m8-b029-morning-job-e013`，开新 PR。
- 某一类数据没取到，页照写，用已有的「今天没有拿到」。问模型失败，那次波动写「可能的原因：这次没问到，下次运行再试」，运行记录写失败原因，页上不出现报错原文。不传 `news_lookup`。
- 不改检测、估值、交易的计算，不改新闻摘要和波动的问法。不部署，不加定时任务配置。
- 本任务不发起真实模型调用，不连真实数据库，不合并。不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：先写七个失败例子，再做这个命令。

## B-028  已完成  2026-10-19 22:48 北京

- 草稿 PR #34，head `e371941`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39271858685 。`phase1-blocking` 333 passed，用时 109.21 秒，nightly 跳过。没有合并。
- 证据：七个例子先失败，再通过。当时页面是「JNJ down」「9 只一起down」，盘后和基本没动没有写出来，没有新闻时持仓仍写「今天没有重要新闻」。本地 `make phase1-test` 333 passed、21 deselected，用时 65.20 秒；`make phase1-cases` 7 passed、1 xfailed。
- 波动那一行按成员收益的平均写成一位小数的涨或跌。盘后加「盘后」。价格和方向相反时接「明显弱于同类股票」或「明显强于同类股票」。四舍五入后是 0.0% 写「基本没动」。收益全空时按方向写涨跌，不写百分数。当天一条新闻都没收到时，第二、三节写「今天一条新闻都没收到」。
- 已自行决定：空的收益不参与平均，代码仍按成员顺序列出。百分数固定一位，四舍五入远离零。已经给了中文涨跌和幅度的，仍走原来那一行，不加盘后。没收到只看传入条目的发布日是不是这个交易日，补查不算收到。有新闻但不重要的，仍写「今天没有」和「今天没有重要新闻」。没收到时持仓代码按字典序。没有持仓仍写「今天没有拿到持仓」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改检测、估值和交易的计算。不改新闻卡和波动卡问法。
- 下一步：等需求方验收。不取新任务。

## B-028  进行中  2026-10-19 22:45 北京

- 草稿 PR #34，head `e371941`，分支 `cursor/m8-b028-move-line-e013`。没有合并。
- 七个例子先失败：页面是「JNJ down」「9 只一起down」，盘后和基本没动没有写出来，没有新闻时持仓仍写「今天没有重要新闻」。接上之后 `tests/m8/test_b028.py` 通过。全套测试还在跑。
- 波动那一行按成员收益的平均写成一位小数的涨或跌。盘后加「盘后」。价格和方向相反时接「明显弱于同类股票」或「明显强于同类股票」。四舍五入后是 0.0% 写「基本没动」。收益全空时按方向写涨跌，不写百分数。当天一条新闻都没收到时，第二、三节改成「今天一条新闻都没收到」。
- 已自行决定：空的收益不参与平均，代码仍按成员顺序列出。百分数固定一位，四舍五入远离零。已经给了中文涨跌和幅度的，仍走原来那一行，不加盘后。没收到只看传入条目的发布日是不是这个交易日，补查不算收到。有新闻但不重要的，仍写「今天没有」和「今天没有重要新闻」。没收到时持仓代码按字典序。没有持仓仍写「今天没有拿到持仓」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改检测、估值和交易的计算。不改新闻卡和波动卡问法。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-028  已收到  2026-10-19 22:40 北京

- 任务：波动那一行直接用异常检测给的数据。方向是英文 `up`/`down`，时段是 `close`/`post`，涨跌是每只成员的小数收益 `members[].ret`。按有数的平均写成一位小数的涨或跌。盘后加「盘后」。价格涨跌和方向相反时，末尾接「明显弱于同类股票」或「明显强于同类股票」。平均四舍五入后是 0.0% 写「基本没动」。收益全空时按方向写涨跌，不写百分数。当天一条新闻都没收到时，第二、三节改成「今天一条新闻都没收到」。
- 入口是北京 09:15 的 `run_scheduled`。从最新 `origin/main`（含 PR #33）开新分支 `cursor/m8-b028-move-line-e013`，开新 PR。
- 调用方已经给了「幅度」和中文涨跌的，照旧能用。不改波动的检测和方向判断，不改新闻摘要和波动的问法，不改估值和计划，不改 B-027 已定的其他说法。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：先写七个失败例子，再改这一行。


- 草稿 PR #33，head `9ad4aae`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39265554424 。`phase1-blocking` 326 passed，用时 87.75 秒，nightly 跳过。没有合并。
- 证据：六个例子先失败，再通过。当时页面仍有内部编号、「入库」「提前看到」「跌 -5.7%」和全部估值。本地 `make phase1-test` 326 passed、21 deselected，用时 63.09 秒；`make phase1-cases` 7 passed、1 xfailed。前两次 CI 也是 326 passed，只因整套 182 秒和 190 秒超过 180 秒。逐日回归改成先转成数组再拟合，公式没变，第三次 CI 87.75 秒通过。
- 每天那一页按次写波动。解释里至少一条「当时已经知道」为真才写「波动前已经看到这条新闻」；原来算成「提前看到」但解释没用上，写「有相关新闻，但没认出是原因」。估值只印持仓、当天波动和计划单里的股票。计划金额写成美元。
- 已自行决定：来源取编号第二段，`sec_8k` 写成 SEC 8-K。北京时间写成月日和时分。一次波动只有一个幅度时，多只用这个数当平均。事后找到的新闻按返回顺序取前 3 条。估值按代码排序。没有金额就不写美元。计划不是一组时写「今天没有拿到计划」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡和波动卡问法，不改再查一次，不改归类的原词。
- 下一步：等需求方验收。不取新任务。

## B-027  进行中  2026-10-19 21:38 北京

- 草稿 PR，head `891b73a`，分支 `cursor/m8-b027-plain-page-e013`。没有合并。
- 六个例子先失败：页面仍有内部编号、「入库」「提前看到」「跌 -5.7%」和全部估值。接上之后 `tests/m8/test_b027.py` 通过。B-015 到 B-026 里看旧说法的断言已改成新说法。全套测试还在跑。
- 每天那一页按次写波动，估值只印持仓、当天波动和计划单里的股票，计划金额写成美元。解释里没有用上的「提前看到」改成「有相关新闻，但没认出是原因」。
- 已自行决定：来源取编号第二段，`sec_8k` 写成 SEC 8-K。北京时间写成月日和时分。一次波动只有一个幅度时，多只用这个数当平均。事后找到的新闻按返回顺序取前 3 条。估值按代码排序。没有金额就不写美元。计划不是一组时写「今天没有拿到计划」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡和波动卡问法，不改再查一次，不改归类的原词。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-027  已收到  2026-10-19 21:30 北京

- 任务：每天一页改成给人看的话。不要出现「库里」「数据库」这类话。波动按次分组，估值只印持仓、当天波动和计划单里的股票，计划金额写成美元。
- 入口是北京 09:15 的 `run_scheduled`。从最新 `origin/main` 开新分支 `cursor/m8-b027-plain-page-e013`，开新 PR。
- 「提前看到」改成：解释里至少一条「当时已经知道」为真才写「波动前已经看到这条新闻」；原来算成提前看到但解释没用上，写「有相关新闻，但没认出是原因」。
- 不改新闻卡和波动卡问法，不改一档最多 5 条、持仓逐只列的选法，不改再查一次，不改估值和计划的计算。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：先写六个失败例子，再改这一页的说法。

## B-026  已完成  2026-10-19 20:17 北京

- 草稿 PR #32，head `a45deed`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39250133169 。`phase1-blocking` 320 passed，用时 111.43 秒，nightly 跳过。没有合并。
- 证据：四个例子先失败，再通过。当时第二档最多 5 条，同一只展开了多条，没标成高的持仓没有单独一行，第一档写过的持仓在第二档变成「这档没有」。本地 `make phase1-test` 320 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 第二档按传入的持仓逐只列，不设 5 条上限。同一只只展开一条，其余写「这只还有 N 条」。没标成高的集中写「今天没有标成高的：」。第一档已经写过的，第二档仍留一行。第一档仍最多 5 条。没有持仓快照仍写「没有持仓快照」。
- 已自行决定：碰上当天波动的持仓排在前面，其余保持传入顺序。同一只先取碰上波动的新闻，再按编号字典序。第二档不写「含持仓」。「这只还有 N 条」紧跟展开的那一条和公司名。没标成高的代码按字典序用顿号连接。属于持仓的未展开新闻不计入「还有 N 条」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡问法，不改波动卡，不改再查一次，不改归类，不从计划单反推持仓。
- 下一步：等需求方验收。不取新任务。

## B-026  进行中  2026-10-19 20:11 北京

- 草稿 PR #32，head `a45deed`，分支 `cursor/m8-b026-holdings-lines-e013`。没有合并。
- 四个例子先失败：第六只被截掉，同一只展开了多条，没标成高的持仓没有单独一行，第一档写过的持仓在第二档变成「这档没有」。接上之后 `tests/m8/test_b026.py` 通过。B-025 的例 1、例 6 改成第二档仍留这只持仓的一行。全套测试还在跑。
- 第二档按传入的持仓逐只列，不设 5 条上限。同一只只展开一条，其余写「这只还有 N 条」。没标成高的集中写「今天没有标成高的：」。第一档已经写过的，第二档仍留一行。
- 已自行决定：碰上当天波动的持仓排在前面，其余保持传入顺序。同一只先取碰上波动的新闻，再按编号字典序。第二档不写「含持仓」。「这只还有 N 条」紧跟展开的那一条和公司名。没标成高的代码按字典序用顿号连接。属于持仓的未展开新闻不计入「还有 N 条」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡问法，不改波动卡，不改再查一次，不改归类。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-026  已收到  2026-10-19 20:06 北京

- 任务：持仓一只一行，不收成 5 条。第二档「再看：持仓上影响大的」按传入的持仓逐只列。同一只只展开一条，其余写「这只还有 N 条」。没标成高的持仓集中写「今天没有标成高的：」。第一档已经写过的，第二档仍留一行。
- 入口是北京 09:15 的 `run_scheduled`。第一档仍最多 5 条。从最新 `origin/main` 开新分支 `cursor/m8-b026-holdings-lines-e013`，开新 PR。
- 没有持仓快照仍写「没有持仓快照」，不用计划单代替。不改新闻卡问法，不改波动卡，不改再查一次，不改归类，不改估值和计划的计算。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：先写四个失败例子，再按持仓逐只列。

## B-025  已完成  2026-10-19 19:39 北京

- 草稿 PR #31，head `5da0a5c`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39245702828 。`phase1-blocking` 316 passed，用时 113.96 秒，nightly 跳过。没有合并。
- 证据：六个例子先失败，再通过。当时仍按输入顺序把标成「高」的整段展开。本地 `make phase1-test` 316 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 早上那一页先看宏观和影响面广的，最多 5 条；再看持仓上影响大的，最多 5 条。打到持仓写「含持仓」，碰上当天波动再写「碰上不寻常波动」。没展开的写「还有 N 条标了高，这里不展开」。没有持仓快照写「没有持仓快照」。
- 已自行决定：一句行业和只有一句的一组都拼进同一句再找宏观词，英文字母不区分大小写。「高」的家数按代码去重，没有代码再用名称。「高」加「中」超过 8 家仍按名单条数。持仓先用行上的 `positions`，没有再用 `payload.positions`。编号没有时用 `info_id`。第二档不写「含持仓」。B-018 安静的一天和 B-020 只标一家「高」的那条，改成计入「还有」，不再展开。估值和计划仍在。9 家中折成一大片的例子仍然通过。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡问法，不改波动卡，不改再查一次，不改归类，不从计划单反推持仓。
- 下一步：等需求方验收。不取新任务。

## B-025  进行中  2026-10-19 19:35 北京

- 草稿 PR #31，head `5da0a5c`，分支 `cursor/m8-b025-trader-page-e013`。没有合并。
- 六个例子先失败：仍按输入顺序把标成「高」的整段展开。接上之后 `tests/m8/test_b025.py` 通过。全套测试还在跑。
- 早上那一页先看宏观和影响面广的，最多 5 条；再看持仓上影响大的，最多 5 条。没展开的写「还有 N 条标了高，这里不展开」。没有持仓快照就写「没有持仓快照」。
- 已自行决定：一句行业和只有一句的一组都拼进同一句再找宏观词，英文字母不区分大小写。「高」的家数按代码去重。「高」加「中」超过 8 家仍按名单条数。持仓先用行上的 `positions`。编号没有时用 `info_id`。第二档不写「含持仓」。B-020 里只标一家「高」的那条也改成计入「还有」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡问法，不改波动卡，不改再查一次，不改归类。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-025  已收到  2026-10-19 19:30 北京

- 任务：早上那一页先给交易员看宏观和持仓。原来「股价没动但新闻卡标了高」改成两档，再加一行计数。第一档「先看：宏观和影响面广的」，最多 5 条。第二档「再看：持仓上影响大的」，最多 5 条。没展开的写「还有 N 条标了高，这里不展开」。
- 入口是北京 09:15 的 `run_scheduled`。持仓从这次传入的 `plan` 里读，不用计划单代替。从最新 `origin/main` 开新分支 `cursor/m8-b025-trader-page-e013`，开新 PR。
- 只有「中」或「低」、而且高加中不超过 8 家的，不进两档，也不计数。不改新闻卡问法，不改波动卡，不改再查一次，不改归类，不改估值和计划的计算。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：先写六个失败例子，再排这一页。

## B-024  已完成  2026-10-19 18:35 北京

- 草稿 PR #30，head `31b8448`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39238045985 。`phase1-blocking` 310 passed，用时 115.38 秒，nightly 跳过。平台在 CI 绿后把它合并为 `72ab4e3`。
- 证据：一句行业的例子先失败（「说了什么」被丢掉），再通过。行业仍是一组文字的例子本来就通过。本地 `make phase1-test` 310 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 行业写成一句时，这一句留在行业里。「说了什么」、名单内、名单外照常留下，不写原因。本来是一组文字或一组对象的，仍按现在的方式留下。
- 已自行决定：一句行业收成只有这一句的一组。空字符串收成空的一组，不因此丢掉整张卡。既不是文字也不是一组的，仍报「新闻卡行业不是数组」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改问法，不改每天那一页，不改再查一次，不改波动卡。
- 下一步：等需求方验收。不取新任务。

## B-024  进行中  2026-10-19 18:31 北京

- 草稿 PR #30，head `31b8448`，分支 `cursor/m8-b024-industry-text-e013`。没有合并。
- 一句行业的例子先失败：「说了什么」被丢掉。接上之后 `tests/m8/test_b024.py` 通过。行业仍是一组文字的例子本来就通过。全套测试还在跑。
- 行业写成一句时，这一句留在行业里。「说了什么」、名单内、名单外照常留下，不写原因。本来是一组的仍按现在的方式留下。
- 已自行决定：一句行业收成只有这一句的一组。空字符串收成空的一组，不因此丢掉整张卡。既不是文字也不是一组的，仍报「新闻卡行业不是数组」。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改问法，不改每天那一页，不改再查一次，不改波动卡。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-024  已收到  2026-10-19 18:30 北京

- 任务：行业写成一句时，不要丢掉整张新闻卡。这一句留在行业里，「说了什么」、名单内、名单外照常留下，不写原因。行业本来是一组文字或一组对象时，仍按现在的方式留下。
- 入口是 `enrich(..., close_read=True)`。从最新 `origin/main` 开新分支 `cursor/m8-b024-industry-text-e013`，开新 PR。
- 模型没答或答坏了仍写原因。标题初筛不写新闻卡。不改问法，不改每天那一页，不改再查一次，不改波动卡。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。
- 下一步：先写两个失败例子，再让一句行业留下。

## B-023  已完成  2026-10-19 18:26 北京

- 草稿 PR #29，head `5e5c777`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39236931644 。`phase1-blocking` 308 passed，用时 87.03 秒，nightly 跳过。平台在 CI 绿后把它合并为 `f5a1754`。
- 证据：三个例子先失败，再通过。第三套栏名的行业当时是空的，行业对象只剩「利好 需求」，问法里没有「名单内」。B-019、B-022 的例子仍然通过。本地 `make phase1-test` 308 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 问法写明回答用「说了什么」「行业」「名单内」「名单外」，公司用代码、名称、方向、理由、关系、重要程度。行业用文字，影响和理由写在行业名后面。`affected_industries`、`tracked_companies`、`outside_companies`、`impact` 以及行业对象里的「行业」进原来的中文栏。已经有内容的中文栏不用别的名字覆盖。模型没答或答坏了仍写原因。
- 已自行决定：行业对象先认「行业名」，没有再认「行业」，后面用空格接影响和理由。同一栏先用原来的中文栏，再按列出的别名顺序取第一个有内容的。问法写明栏名，并保留方向、关系、重要程度各自允许的写法。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改每天那一页，不改再查一次，不改波动卡问法。
- 下一步：等需求方验收。不取新任务。

## B-023  进行中  2026-10-19 18:21 北京

- 草稿 PR #29，head `5e5c777`，分支 `cursor/m8-b023-card-fields-e013`。没有合并。
- 三个例子先失败：第三套栏名的行业是空的，行业对象只剩「利好 需求」，问法里没有「名单内」。接上之后 `tests/m8/test_b023.py` 通过。B-019、B-022 的例子仍然通过。全套测试还在跑。
- 问法写明回答用「说了什么」「行业」「名单内」「名单外」，公司用代码、名称、方向、理由、关系、重要程度。`affected_industries`、`tracked_companies`、`outside_companies`、`impact` 以及行业对象里的「行业」进原来的中文栏。已经有内容的中文栏不用别的名字覆盖。
- 已自行决定：行业对象先认「行业名」，没有再认「行业」，后面用空格接影响和理由。同一栏先用原来的中文栏，再按列出的别名顺序取第一个有内容的。问法写明栏名，并保留方向、关系、重要程度各自允许的写法。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改每天那一页，不改再查一次，不改波动卡问法。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-023  已收到  2026-10-19 18:20 北京

- 任务：新闻卡问明栏名，并认已经见过的栏。问法写明回答用「说了什么」「行业」「名单内」「名单外」，公司用代码、名称、方向、理由、关系、重要程度。行业用文字，影响和理由写在行业名后面。`affected_industries`、`tracked_companies`、`outside_companies`、`impact` 以及行业对象里的「行业」也进原来的中文栏。
- 入口是 `enrich(..., close_read=True)`。从最新 `origin/main` 开新分支 `cursor/m8-b023-card-fields-e013`，开新 PR。
- 标题初筛不写新闻卡。已经有内容的中文栏不用别的名字覆盖。模型没答或答坏了仍写原因。不改每天那一页，不改再查一次，不改波动卡问法。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。
- 下一步：先写三个失败例子，再改问法和栏名。

## B-022  已完成  2026-10-19 18:07 北京

- 草稿 PR #28，head `f64cb15`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39234618552 。`phase1-blocking` 305 passed，用时 151.20 秒，nightly 跳过。平台在 CI 绿后把它合并为 `b9a2b6f`。
- 证据：新栏名的例子先失败（「说了什么」是空的），再通过。英文栏的例子本来就通过。本地 `make phase1-test` 305 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 入库细读时，`新闻摘要` 进「说了什么」，`受影响美股行业` 进「行业」，`跟踪名单内受影响公司` 进名单内，`名单外明显受影响公司` 进名单外。`影响` 进「方向」，`与新闻关系` 进「关系」。原来的中文栏或英文栏有内容时仍用原来的。模型没答或答坏了仍写原因。
- 已自行决定：同一栏先用原来的中文栏，再用 B-019 的英文栏，最后用这套新名字。空字符串或空数组不算有内容。行业对象用「行业名」，后面用空格接「影响」和「理由」，文字原样留下。公司对象先原样复制，`方向` 和 `direction` 都空才用 `影响`，`关系` 和 `relation` 都空才用 `与新闻关系`。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改每天那一页，不改再查一次，不改波动卡问法。
- 下一步：等需求方验收。不取新任务。

## B-022  进行中  2026-10-19 18:03 北京

- 草稿 PR #28，head `f64cb15`，分支 `cursor/m8-b022-card-aliases-e013`。没有合并。
- 新栏名的例子先失败：「说了什么」是空的。接上之后 `tests/m8/test_b022.py` 通过。英文栏的例子本来就通过。全套测试还在跑。
- 入库细读时，`新闻摘要` 进「说了什么」，`受影响美股行业` 进「行业」，`跟踪名单内受影响公司` 进名单内，`名单外明显受影响公司` 进名单外。`影响` 进「方向」，`与新闻关系` 进「关系」。原来的中文栏或英文栏有内容时仍用原来的。
- 已自行决定：同一栏先用原来的中文栏，再用 B-019 的英文栏，最后用这套新名字。空字符串或空数组不算有内容。行业对象用「行业名」，后面用空格接「影响」和「理由」。公司对象先原样复制，`方向` 和 `direction` 都空才用 `影响`。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改每天那一页，不改再查一次，不改波动卡问法。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-022  已收到  2026-10-19 18:00 北京

- 任务：新闻卡再认一套模型实际用过的栏名。`新闻摘要` 进「说了什么」，`受影响美股行业` 进「行业」，`跟踪名单内受影响公司` 进名单内，`名单外明显受影响公司` 进名单外。公司对象里 `影响` 进「方向」，`与新闻关系` 进「关系」。原来的中文栏或英文栏有内容时仍用原来的。
- 入口是 `enrich(..., close_read=True)`。从最新 `origin/main` 开新分支 `cursor/m8-b022-card-aliases-e013`，开新 PR。
- 标题初筛不写新闻卡。模型没答或答坏了仍写原因。不改每天那一页，不改再查一次，不改波动卡问法。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。
- 下一步：先写两个失败例子，再认这套栏名。

## B-021  已完成  2026-10-19 17:53 北京

- 草稿 PR #27，head `9b2cbb9`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39232794266 。`phase1-blocking` 303 passed，用时 75.89 秒，nightly 跳过。平台在 CI 绿后把它合并为 `61fb74e`。
- 证据：六个例子先失败（`run_scheduled` 还不接收 `news_lookup`），再通过。本地 `make phase1-test` 303 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 北京 09:15，传入查找时，对不上或送给波动卡的开始前新闻少于 5 条，就再查这只股票。查到当时已经公开但库里没有的，归类「没采到」。查过还是没有，归类「查过没有消息」。晚于波动开始的标「波动后才公开」，不写成当时已经知道。不写数据库，不进第 4 段，不另成一页。09:30 和 12:30 不查、不出页面。已经有 5 条且对上了至少一条，不再查。没有传入查找时页面不变。
- 已自行决定：每一只成分股查一次。原来输入里已有的编号不再写上。只有早于或等于波动开始、且不在原输入里的才置「补查到」，归类仍用原来送出的新闻卡，已经是「提前看到」的保持不变。晚于开始的只显示并标「波动后才公开」，不置「补查到」。查找返回不是数组时当成没查到，这次调用仍然算查过。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡栏名，不改波动卡问法，不改一页只出刚收盘那天。不处理「7 天窗口刚好把更早的新闻切掉」。
- 下一步：等需求方验收。不取新任务。

## B-021  进行中  2026-10-19 17:48 北京

- 草稿 PR #27，head `9b2cbb9`，分支 `cursor/m8-b021-lookup-e013`。没有合并。
- 六个例子先失败：`run_scheduled` 还不接收 `news_lookup`。接上之后 `tests/m8/test_b021.py` 通过。全套测试还在跑。
- 北京 09:15，传入查找时，对不上或送给波动卡的开始前新闻少于 5 条，就再查这只股票。查到当时已经公开但库里没有的，归类「没采到」。查过还是没有，归类「查过没有消息」。晚于波动开始的标「波动后才公开」。
- 已自行决定：每一只成分股查一次。原来输入里已有的编号不再写上。只有早于或等于波动开始、且不在原输入里的才置「补查到」，归类仍用原来送出的新闻卡。晚于开始的只显示并标「波动后才公开」。查找返回不是数组时当成没查到。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡栏名，不改波动卡问法，不改一页只出刚收盘那天。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-021  已收到  2026-10-19 17:43 北京

- 任务：对不上或新闻太少时，再查一次这只股票。查找由这次调用传入的 `news_lookup` 注入，不访问网络。查到的、当时已经公开但库里没有的，归类「没采到」。查过还是没有，归类「查过没有消息」。晚于波动开始的可以显示，标「波动后才公开」，不能写成当时已经知道。
- 入口是北京 09:15 的 `run_scheduled`。从最新 `origin/main` 开新分支 `cursor/m8-b021-lookup-e013`，开新 PR。B-020 已合并。
- 已经有 5 条或更多、并且波动卡对上了至少一条，就不再查。09:30 和 12:30 不再查，也不出页面。全市场宽扫不再查。没有传入 `news_lookup` 时页面维持现在的结果。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。不改新闻卡栏名，不改波动卡问法，不改一页只出刚收盘那天。不处理「7 天窗口刚好把更早的新闻切掉」。
- 下一步：先写六个失败例子，再接查找。

## B-020  已完成  2026-10-19 17:28 北京

- 草稿 PR #26，head `3d78807`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39229666071 。`phase1-blocking` 297 passed，用时 117.33 秒，nightly 跳过。没有合并。这次 CI 合入了已经合并的 B-019，所以比分支上多两个例子。
- 证据：前三个例子先失败，再通过。09:30 和 12:30 本来就没有 `daily_pages`。本地 `make phase1-test` 295 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 北京 09:15 只出一页。日期是已经收盘的最近一个美国交易日。第 1 到 3 段只写这一天的跟踪范围内波动。更早的新闻可以解释这一天的波动，但不单独成页，也不进第 4 段。第 4 段只留标成「高」的，以及超过 8 家高或中要折叠的那条。
- 已自行决定：纽约当天已经收盘就用这一天；还没收盘或不是交易日，就往前找上一个交易日。第 4 段先挑有「高」的，或高加中超过 8 家的，再交给原来的文字函数。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡栏名，不改波动卡问法，不做补查。
- 下一步：等需求方验收。不取新任务。

## B-020  进行中  2026-10-19 17:23 北京

- 草稿 PR #26，head `3d78807`，分支 `cursor/m8-b020-one-day-page-e013`。没有合并。
- 前三个例子先失败：更早几天各成一页，只标成「低」的新闻也进了第 4 段。改完后 `tests/m8/test_b020.py` 通过。09:30 和 12:30 本来就没有 `daily_pages`。全套测试还在跑。
- 北京 09:15 只出一页。日期是已经收盘的最近一个美国交易日，用现有的交易日历和收盘时刻。更早的新闻可以解释这一天的波动，但不单独成页，也不进第 4 段。
- 已自行决定：纽约当天已经收盘就用这一天；还没收盘或不是交易日，就往前找上一个交易日。第 4 段先挑有「高」的，或高加中超过 8 家的，再交给原来的文字函数。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改新闻卡栏名，不改波动卡问法，不做补查。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-020  已收到  2026-10-19 17:21 北京

- 任务：一次早上运行只出刚收盘的那一个交易日。更早几天的新闻可以解释这一天的波动，但不单独成页，也不进第 4 段。第 4 段只留名单内标成「高」的，以及超过 8 家高或中要折叠的那条。
- 入口是北京 09:15 的 `run_scheduled`。页的日期用现有的美股收盘判断。09:30 和 12:30 不出页面。从最新 `origin/main` 开新分支 `cursor/m8-b020-one-day-page-e013`，开新 PR。不依赖还没合并的 B-019。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。不改新闻卡栏名，不改波动卡问法，不做补查。
- 下一步：先写四个失败例子，再把早上那次收成一页。

## B-019  已完成  2026-10-19 17:05 北京

- 草稿 PR #25，head `d447e6e`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39226820152 。`phase1-blocking` 293 passed，用时 113.51 秒，nightly 跳过。没有合并。
- 证据：英文栏的例子先失败（「说了什么」是空的），再通过。中文栏和坏回复本来就通过。本地 `make phase1-test` 293 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。上一轮 head `d4bce20` 的测试全部通过，但用时 180.68 秒，超过 180 秒上限。
- 入库细读时，英文栏补进原来的中文栏。中文栏有内容时用中文栏。名单仍只分成名单内和名单外，不删模型答出的公司。`标明` 仍是「模型判断」。名字匹配仍在。模型没答或答坏了仍写原因。
- 已自行决定：按栏判断，中文栏是空字符串、空数组或没有这个栏，才用对应的英文栏。公司对象先原样复制，再补空着的中文栏。股票池文件在一次进程里只读一次，每次候选检查仍拿到一份新的名单。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改波动卡，不改每天那一页，不做补查。
- 下一步：等需求方验收。不取新任务。

## B-019  进行中  2026-10-19 16:52 北京

- 草稿 PR #25，head `d4bce20`，分支 `cursor/m8-b019-news-card-keys-e013`。没有合并。
- 英文栏的例子先失败（「说了什么」是空的），改完后 `tests/m8/test_b019.py` 通过。中文栏和坏回复本来就通过。全套测试还在跑。
- 入库细读时，英文栏补进原来的中文栏。中文栏有内容时用中文栏。名单仍只分成名单内和名单外，不删模型答出的公司。`标明` 仍是「模型判断」。名字匹配仍在。
- 已自行决定：按栏判断，中文栏是空字符串、空数组或没有这个栏，才用对应的英文栏。公司对象先原样复制，再补空着的中文栏。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不改波动卡，不改每天那一页，不做补查。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-019  已收到  2026-10-19 16:50 北京

- 任务：新闻卡要留下模型实际给出的答案。英文栏 `summary`、`industries`、`companies_affected`、`companies_outside_list`，以及公司的 `code`、`name`、`direction`、`reason`、`relation`、`importance`，补进原来的中文栏。中文栏有内容时用中文栏。
- 入口是 `enrich(..., close_read=True)`。从最新 `origin/main` 开新分支 `cursor/m8-b019-news-card-keys-e013`，开新 PR。
- 标题初筛不写新闻卡。波动卡问法不改。模型没答或答坏了仍写原因，名字匹配保留。名单仍只分成名单内和名单外，不删模型答出的公司。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。不做补查，不改每天那一页。
- 下一步：先写两个失败例子，再接英文栏。

## B-018  已完成  2026-10-19 15:26 北京

- 草稿 PR #24，head `6ed8440`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39215554261 。`phase1-blocking` 通过，nightly 跳过。没有合并。
- 证据：八个例子先失败（09:15 入口还不收 `valuation=`），再通过。本地 `make phase1-test` 291 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 北京 09:15 每个交易日一页。同一天的跟踪范围内波动放在一起，各有解释和归类。没有跟踪范围内的波动也出一页。估值和计划从参数传入，不从库里读。能估的写三个数，不估的写原因，计划写代码、动作、数量或比例。没传到就写明没拿到。页上没有 `{}`。
- 只有日期的新闻按钟点不清楚。同一天归类「同一天，发布钟点不清楚」，当时已经知道是 false。更早且已标到的归类「提前看到」，当时已经知道是 true。
- 09:30 和 12:30 不出页面。五日回放、`score_all`、`score_stage` 和冻结的五日文件没改。
- 已自行决定：估值或计划不是行列表时（包括没传、空字典、旧字典）写「没有拿到」。第 4 段先写「说了什么」，再按原来的规则折叠。只有日期的新闻按存下的日期算哪一天。页面日期是跟踪范围内波动的交易日，加上带新闻卡的新闻；宽扫不进第 1 段，也不单独成页。没有可送新闻时仍保留 B-017 的规则报告。用户看到的一页是 `daily_pages`。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不做补查。
- 下一步：等需求方验收。不取新任务。

## B-018  进行中  2026-10-19 15:22 北京

- 草稿 PR #24，head `6ed8440`，分支 `cursor/m8-b018-daily-page-e013`。没有合并。
- 八个例子先失败（09:15 入口还不收 `valuation=`），改完后 `tests/m8/test_b018.py` 通过。全套测试还在跑。
- 北京 09:15 每个交易日一页。同一天的跟踪范围内波动放在一起。估值和计划从参数传入，不从库里读。只有日期的新闻同一天不算「提前看到」。09:30 和 12:30 不出页面。
- 已自行决定：估值或计划不是行列表时写「没有拿到」。第 4 段先写「说了什么」。只有日期的新闻按存下的日期算天。宽扫不进第 1 段。没有可送新闻时仍保留原来的规则报告。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。不做补查。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-018  已收到  2026-10-19 15:11 北京

- 任务：每个交易日一页。同一天的波动放在一起，带上当天的估值和计划。只有日期的新闻不算「提前看到」。从最新 `origin/main` 开新分支 `cursor/m8-b018-daily-page-e013`，开新 PR。
- 入口是北京 09:15 的 `run_scheduled`。每个交易日出一页，没有跟踪范围内的波动也出。09:30 和 12:30 不出页面。`replay_days`、`score_all`、`score_stage` 不改，冻结的五日文件不改。
- `run_scheduled` 和 `execute_stage` 增加 `valuation=`、`plan=`，传到 `attribute_all`。这张单不从库里读估值和计划。
- 只有日期的新闻按钟点不清楚处理。同一天归类「同一天，发布钟点不清楚」。更早的、已经标到的算「提前看到」。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。不做补查。
- 下一步：先写八个失败例子，再改 09:15 那一页。

## B-017  已完成  2026-10-19 13:33 北京

- PR #21，head `c16a146`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39204825060 。`phase1-blocking` 通过，nightly 跳过。没有合并。
- 证据：没有新闻卡的例子先因 `claim_extraction` 失败，一条新闻都没有的例子先因没有当天文字失败，再通过。含 META 的例子仍通过。本地 `make phase1-test` 283 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 跟踪范围内、波动开始前有可送新闻时，`attribute_all` 只调一次 `move_card`，不走 `anomaly_candidates`，也不走 `claim_extraction`。一条可送新闻都没有时不调模型，归类是「查过没有消息」，当天文字仍在。注入的 META 仍在，估值和规则 A 计划的数值没改。
- 已自行决定：没有可送新闻时，仍写出原来的规则报告（这条路径本来也不问模型），并附上当天文字。五日回放，以及直接调用 `score_all` / `score_stage`，仍走规则报告，冻结的五日文件不改。宽扫、只打标签、单独的价格轨道不走波动卡。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。B-016 有新闻卡的那一段留下，不重做。
- 下一步：等需求方验收。不取新任务。

## B-017  进行中  2026-10-19 13:26 北京

- 草稿 PR #21，head `b202f82`。已把 `origin/main` 合进 `cursor/m8-b009-links-e013`（`2024bba`）。没有新开 PR。
- 没有新闻卡的例子先因 `claim_extraction` 失败，一条新闻都没有的例子先因没有当天文字失败。含 META 的例子本来就通过。接上入口后 `tests/m8/test_b017.py` 通过。全套测试还在跑。
- 跟踪范围内、波动开始前有可送新闻时，`attribute_all` 只调 `move_card`，不调 `anomaly_candidates`，也不调 `claim_extraction`。一条可送新闻都没有时不调模型，归类是「查过没有消息」，当天文字仍在。
- 已自行决定：没有可送新闻时，仍写出原来的规则报告（这条路径本来也不问模型），并附上当天文字。五日回放，以及直接调用 `score_all` / `score_stage`，仍走规则报告，冻结的五日文件不改。宽扫、只打标签、单独的价格轨道不走波动卡。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-017  已收到  2026-10-19 13:10 北京

- 任务：跟踪范围内的不寻常波动，从 `attribute_all` 跑下来，没有新闻卡、以及一条可送新闻都没有时，也不许再问 glm。继续在 PR #21 的分支 `cursor/m8-b009-links-e013` 上提交，基线 `3e549a6`，先合入 `origin/main`。不新开 PR。
- B-016 有新闻卡的那一段留下，不重做。B-016 把入口收成「只有新闻卡才走波动卡」不验收。
- 三种都从 `attribute_all` 走：已有新闻卡、有新闻但没有新闻卡、一条可送新闻都没有。前两种只调 `move_card`，不调 `anomaly_candidates`，也不调 `claim_extraction`。第三种不调任何模型，归类写「查过没有消息」，当天文字仍要有。
- 宽扫、只打标签、单独的价格轨道不走波动卡。直接调用 `propose_candidates` 的测试可以留下。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。
- 下一步：先写三个失败例子，再改入口。

## B-016  已完成  2026-10-19 12:40 北京

- PR #21，head `3e549a6`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39200189667 。`phase1-blocking` 通过，nightly 跳过。没有合并。
- 证据：例子先因为 `attribute_all` 不接受 `valuation` 而失败，接上入口之后通过。本地 `make phase1-test` 280 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 跟踪范围内、检索到的新闻已经有新闻卡时，这次运行只调一次 `move_card`，并用 `daily_text` 写出当天的文字，不走 `anomaly_candidates`。波动开始之时或之后的新闻不送进去。注入的 META 仍在，估值和规则 A 计划的数值没改。
- 已自行决定：只有检索结果里已经有新闻卡、且不是宽宇宙时，才走波动卡。没有新闻卡的条目仍走原来的 `anomaly_candidates`，已有评分和生命周期测试保持不变。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`，没有改估值和交易的计算。B-015 的新闻卡留下，不重做。
- 下一步：等需求方验收。不取新任务。

## B-016  已收到  2026-10-19 12:30 北京

- 任务：把波动卡接到真正处理一次跟踪范围内不寻常波动的运行上。继续在 PR #21 的分支 `cursor/m8-b009-links-e013` 上提交，基线 `9726387`，先合入 `origin/main`。不新开 PR。
- B-015 的新闻卡留下，不重做，也不改回「正文没写就留空」。
- 这次运行只调 `move_card`，不走 `anomaly_candidates`。同一次运行用 `daily_text` 写出当天的文字。模型答出的公司不删。估值和规则 A 计划只读，不改数值。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`，不改估值和交易的计算。
- 下一步：先写失败例子，再把入口接上。

## B-015  已完成  2026-10-19 10:27 北京

- PR #21，head `9726387`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39189799997 。`phase1-blocking` 通过。没有合并。
- 证据：八个例子先因没有新闻卡模块而收集失败，再通过。本地 `make phase1-test` 279 passed、21 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 已自行决定：一条新闻把超过 8 家标成高或中、且没有高时，展开中的前 3 家，并写其余家数。新闻卡没答上时，卡上写原因，不把整条抽取判成失败，名字匹配仍然留下。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`、估值、交易、规则 A。Muse / R1 / 东芝必须为空名单的 blocking 测试已删除。
- 下一步：等需求方验收。不取新任务。

## B-015  进行中  2026-10-19 10:15 北京

- 草稿 PR #21，head `f9f3796`。已把 `origin/main` 合进 `cursor/m8-b009-links-e013`（`b205018`）。没有新开 PR。
- 例子先因没有新闻卡模块而收集失败，补上之后 `tests/m8/test_b015.py` 通过。全套测试还在跑。CI 还在跑：https://github.com/XuQingsong/inves-cog/actions/runs/39189078048 。
- 细读的那一次改为 `news_card`。波动卡只调 `move_card`。每天那一页是一段文字。Muse / R1 / 东芝必须为空名单的 blocking 测试已删除。
- 已自行决定：一条新闻把超过 8 家标成高或中、且没有高时，展开中的前 3 家，并写其余家数。新闻卡没答上时，卡上写原因，不把整条抽取判成失败，名字匹配仍然留下。
- 没有发起模型调用，没有连接数据库。没有改 `docs/`、`golden/`、`milestones.txt`、估值、交易、规则 A。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-015  已收到  2026-10-19 10:00 北京

- 任务：新闻卡、波动卡、每天那一页。继续在 PR #21 的分支 `cursor/m8-b009-links-e013` 上提交，先把 `origin/main` 合进来。不新开 PR。
- B-014 不验收。删掉或改掉「Muse / R1 / 东芝必须是空名单」的 blocking 测试。不得删除模型答出的公司。
- 新闻卡只替换已经会细读的那一次。波动卡只在跟踪范围内一次不寻常波动时调一次，不走 `anomaly_candidates`。每天那一页是一段固定顺序的文字，不做网页。
- 本任务不发起真实模型调用，不连数据库，不部署，不合并。不改 `docs/`、`golden/`、`milestones.txt`、估值、交易、规则 A。
- 下一步：先写失败例子，再做卡片。

## B-014  已完成  2026-10-19 01:00 北京

- PR #21，head `fb9cfda`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39147297944 。`phase1-blocking` 通过。没有合并。
- 证据：八个例子先因没有记录器而收集失败，再通过。本地 `make phase1-test` 259 passed、19 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 已自行决定：公司名用 `config/news_entities.yaml` 里这 59 只的正式名称和代码。产品别名不算公司，所以 Muse 那条里的 iPhone 不会写成 AAPL。超过三家时，按正文出现的先后留下前三家。
- 没有改留下方式。没有发起模型调用，没有连接数据库。评分、估值、交易没有改。没有改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：等需求方验收。不取新任务。

## B-014  进行中  2026-10-19 00:57 北京

- 草稿 PR #21，head `fb9cfda`。基线 `8b25fbe`。没有新开 PR。
- 八个例子先因没有记录器而收集失败，补上记录后 `tests/m8/test_b014.py` 9 passed。全套测试还在跑。CI 还在跑：https://github.com/XuQingsong/inves-cog/actions/runs/39147297944 。
- 细读只收正文里写到的跟踪公司，最多三家。没有改留下方式，没有改评分。没有发起模型调用，没有连接数据库。
- 下一步：全套测试和 CI 绿了再写已完成。

## B-014  已收到  2026-10-19 00:50 北京

- 任务：做新闻记录和股价记录。继续在 PR #21 的分支上提交，基线 `8b25fbe`。不新开 PR。
- 新闻记录：编号、入库时间、处理级别。细读时公司只收正文里出现并且在 59 只宇宙里的，最多三家，标明正文写了。正文没有的不补，判断留空。
- 股价记录：只引用波动前已入库的新闻编号。正文写了这家公司、正文没有这家公司、已入库新闻对不上，后两种也算完成。晚于波动的新闻不能标成当时已经知道。
- 本任务不发起模型调用，不连数据库。不改评分、估值、交易。不改 `docs/`、`golden/`、`milestones.txt`。不补「正文没写也可以猜三家公司」。
- 下一步：先写 8 个失败例子，再做记录。

## B-013  已完成  2026-10-19 00:37 北京

- PR #21，head `8b25fbe`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39145362431 。`phase1-blocking` 通过。没有合并。
- 证据：已撤回 `2c9c07f`，工作区与 `820e5e9` 没有文件差异。三个测试的期望已回到当时。本地 `make phase1-test` 250 passed、19 deselected；`make phase1-cases` 7 passed、1 xfailed。
- 已自行决定：UD-B-05，见上一条已收到。没有实现两条新的新闻路径。没有发起模型调用，没有连接数据库。评分没有改。
- 下一步：等需求方验收。不取新任务。

## B-013  进行中  2026-10-19 00:31 北京

- 草稿 PR #21，head `8b25fbe`。已撤回 `2c9c07f`，留下方式与 `820e5e9` 相同。三个测试的期望已改回。
- 全套测试和 CI 还没有结果。不写成已完成。没有实现两条新的新闻路径。没有发起模型调用，没有连接数据库。

## B-013  已收到  2026-10-19 00:30 北京

- 用户决策 UD-B-05：新闻入库后，模型可以判断它会影响正文里没写到的公司。例子是 Muse 登顶应用商店，可以提示 Meta。用户说明记在 B-013。照做：撤掉 B-012 的「正文必须出现公司名或代码才留下」。PR #21 head `2c9c07f` 不收。
- 任务：继续在 PR #21 的分支上提交，不新开 PR。留下方式回到 `820e5e9`。三个被改过期望值的测试改回去。
- 本任务不实现「新闻入库后判断影响谁」和「先看到股价异常再找新闻」。不发起模型调用，不连数据库。不改评分，不改 `docs/`、`golden/`、`milestones.txt`。
- 下一步：撤回 `2c9c07f`，再跑全套测试。

## B-012  已完成  2026-10-19 00:13 北京

- PR #21，head `2c9c07f`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39143773187 。`phase1-blocking` 通过。没有合并。
- 证据：本地 `make phase1-test` 257 passed、19 deselected；`make phase1-cases` 7 passed、1 xfailed。七个点名例子通过。
- 因此改变的现有期望值：`test_three_link_kinds_keep_or_drop_the_expected_ticker` 里未点名的 WDC 和仅有关系的 WDC 不再留下；`test_r1_accelerator_basket_still_needs_a_recording` 的 missing 从空变为候选未连接加速芯片范围；`test_toshiba_reprint_is_not_operating_evidence` 的 affected 从 WDC 变为空。
- 已自行决定：无。评分公式、权重、阈值未改。`test_case_attribution` 继续 pending。没有发起模型调用，没有连接数据库。
- 下一步：等需求方验收。AC-M8-02/06/08 的现场和五日全池仍未关闭。不取新任务。

## B-012  进行中  2026-10-19 00:10 北京

- 草稿 PR #21，head `2c9c07f`。七个例子修之前失败，修之后通过。不新开 PR。
- 现有期望值因此变化的有三条：`test_three_link_kinds_keep_or_drop_the_expected_ticker` 的 WDC 不再因未点名引文或仅有关系留下；`test_r1_accelerator_basket_still_needs_a_recording` 的 missing 从空变为候选未连接加速芯片范围；`test_toshiba_reprint_is_not_operating_evidence` 的 affected 从 WDC 变为空。
- 全套测试和 CI 还没有结果。不写成已完成。没有发起模型调用，没有连接数据库。评分公式、权重、阈值没有改。

## B-012  已收到  2026-10-19 00:00 北京

- 任务：点名规则进入门禁。继续在 PR #21 的分支 `cursor/m8-b009-links-e013` 上提交，基线 `820e5e9`。不新开 PR，不改 PR #17、#18、#19、#22、#23。
- 只改候选进入预期影响范围的规则。市场层和经营层仍只由规则填写。评分公式、权重、阈值不改。不改提示词。
- 本任务不发起模型调用，不连数据库。不改 `docs/`、`golden/`、`milestones.txt`。现有期望值若因这条规则变化，逐条列出测试名和前后值。
- 下一步：先写 7 个失败例子，再修。

## B-011  已完成  2026-10-18 22:14 北京

- PR #22，head `c11250b`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39134912237 。`phase1-blocking` 通过。没有合并。
- 证据：本地 `make phase1-test` 129 passed、12 deselected；`make phase1-replay` 4 passed。v18 的 90 笔没有变化，golden 保持。
- 已自行决定：无。阈值、卖出比例和其他风控未改。没有发起模型调用，没有连接数据库。
- 下一步：等需求方验收。不取新任务。

## B-011  进行中  2026-10-18 22:12 北京

- 草稿 PR #22，分支 `cursor/m4-b011-drawdown-e013`，head `c11250b`。两个等号案例修之前失败，修之后通过。相邻金额保持原运算符。
- 阈值仍是 −8、−4、−12、−6。卖出比例和其他风控没有改。没有改 PR #18、#19、#21。
- 全套测试、90 笔回放和 CI 还没有结果。不写成已完成。没有发起模型调用，没有连接数据库。

## B-011  已收到  2026-10-18 22:08 北京

- 任务：修复回撤恰好 −8% 和 −6% 的边界。用户决定 UD-COORD-07。从 main 新开分支，新草稿 PR，标题 `[M4] B-011 回撤边界`。不改 PR #18、#19、#21，不改 M8 分支。
- 阈值仍是 −8、−4、−12、−6，运算符含义不变。只改比较。不改卖出比例和其他风控。
- 本任务不发起模型调用，不连数据库。不改 `docs/`、`golden/`、`milestones.txt`。v18 的 90 笔若有变化，不改 golden，写阻塞并停。
- 下一步：先写两个等号案例的失败测试，再修。

## B-010  已完成  2026-10-18 21:55 北京

- PR #21，head `820e5e9`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39133341729 。`phase1-blocking` 通过。没有合并。
- 证据：本地 `make phase1-test` 250 passed、19 deselected；`make phase1-cases` 7 passed、1 xfailed。第 1 项现有期望值：无。
- 已自行决定：无。评分公式、权重、阈值未改。`test_case_attribution` 继续 pending。没有发起模型调用，没有连接数据库。
- 下一步：等需求方验收。AC-M8-02/06/08 的现场和五日全池仍未关闭。不取新任务。

## B-010  进行中  2026-10-18 21:50 北京

- head `820e5e9`。上一头 `0294358` 的 CI 失败：https://github.com/XuQingsong/inves-cog/actions/runs/39132601819 。产品测试通过。导入检查把 main 上未格式化的 `docs/phase1/acceptance/M8-B009-probe-2026-10-18.py` 算进本 PR，因为 `base.sha` 停在开 PR 时的 `28cfbad`。没有改 `docs/`。`820e5e9` 改为对合并提交的第一父本做差分。
- 新 CI：https://github.com/XuQingsong/inves-cog/actions/runs/39133341729 。还没有结果。不写成已完成。
- 本地 `make phase1-test`：250 passed，19 deselected。`make phase1-cases`：7 passed，1 xfailed。第 1 项现有期望值：无。没有发起模型调用，没有连接数据库。

## B-010  进行中  2026-10-18 21:40 北京

- 五项和两个次要项已写进 PR #21，head `0294358`。没有新开 PR。PR #18、#19 没有改。
- 第 1 项：v3 路径上没有 `links` 或 `links` 不是数组时，标的进入研究缺口，原因是未给逐环依据。旧录音不重新标成 v3。
- 第 2 项：盲审 id 由对象 id 和种子决定。组别只写在 `blind_map.json`。
- 第 3 项：删除只去掉目标及其同源条目。其他条目保持原样。目标不存在时拒绝生成。
- 第 4 项：六件对象都是 v3 `candidate_payload`。调用次数默认 3，上限是 6 乘以次数。哈希与录音路径相同。
- 第 5 项：已支持的市场关联按候选和标的，来自市场确认或二次命中，并写规则名。未知或不确认留空。
- 次要项：预登记时间按带时区的时刻比较，没有时区就拒绝。报告展示 `hypothesis_width`，不进入评分。
- 评分公式、权重、阈值没有改。第 1 项没有改现有期望值，相关夹具补了合法 `links`。没有发起模型调用，没有连接数据库。全套测试和 CI 还没有结果。不写成已完成。

## B-010  已收到  2026-10-18 21:21 北京

- 任务：修 B-009 复查的五项和两个次要项。继续在 PR #21 的分支 `cursor/m8-b009-links-e013` 上提交，基线 `68ee464`。不新开 PR，不改 PR #18、#19。
- 本任务不发起模型调用，不连数据库。评分公式、权重、阈值不改。不改 `docs/`、`golden/`、`milestones.txt`。现有期望值只允许因为第 1 项而改，优先给夹具补合法 `links`；改了的测试名和前后值写进 PR，没有就写「无」。
- 下一步：每一项先写失败测试再修。B-009 仍是已完成，不重开。

## B-009  已完成  2026-10-18 21:05 北京

- PR #21，head `68ee464`，CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/39129742708 。`phase1-blocking` 通过。没有合并。
- 证据：本地 `make phase1-test` 244 passed、19 deselected；`make phase1-cases` 7 passed、1 xfailed。开工复述在 `handoff/M8/b009-kickoff.md`。
- 已自行决定：无。评分公式、权重、阈值未改。`test_case_attribution` 继续 pending。没有发起模型调用，没有连接数据库。
- 下一步：等需求方验收。AC-M8-02/06/08 的现场和五日全池仍未关闭。不取新任务。

## B-009  进行中  2026-10-18 21:04 北京

- 草稿 PR #21，head `68ee464`。本地 `make phase1-test`：244 passed，19 deselected。`make phase1-cases`：7 passed，1 xfailed。`test_case_attribution` 仍 pending。
- CI 还没有结果。不写成已完成。没有发起模型调用，没有连接数据库。AC-M8-02/06/08 的现场和五日全池仍未关闭。

## B-009  进行中  2026-10-18 21:01 北京

- 草稿 PR #21，head `68ee464`。基线是 `c22aa14`。没有向 `codex/m8-takeover-r01` 推送。PR #18、#19 没有改。
- 四个工作包已写进代码。评分公式、权重、阈值和现有分数期望值没有改。同一空样本载荷的哈希从 v2 `6bfc9571337593c73e87159c15a9eb216a81c83a58c4f2819eef88a67efc7bd1` 变为 v3 `9f078001eca34640868f46ca656540327c431eeb35f4527a45bde589ad7bf121`。
- `test_case_attribution` 仍 pending，等 v3 真实录音。没有发起模型调用，没有连接数据库。全套测试正在跑，CI 还没有结果。不写成已完成。

## B-009  已收到  2026-10-18 20:50 北京

- 任务：M8 剩余开发。逐环依据、评分诊断、诊断实验工具、案例测试框架。基线是 `codex/m8-takeover-r01` 的 `c22aa14`。不向那条分支推送。PR #18、#19 不关闭、不改。
- 本任务不发起模型调用，不连数据库。评分公式、权重、阈值不改。不改 `docs/`、`golden/`、`milestones.txt`。现有评分测试的期望值若必须改，就写阻塞并停。
- 下一步：写开工复述，然后按工作包开发。

## B-008  进行中  2026-10-18 20:47 北京

- 用户决策 UD-B-04：用户要求继续，并准备接收任务。用户原话「继续开始，准备接收任务」。照做：恢复每 10 分钟查看信箱。B 当前是运行。信箱仍到 B-008，没有新编号。
- 已看到 main `c0ae7d0` 上的 UD-COORD-05 和交接承接。承诺的两项在 `82bacdb`，需求方已单独验过。跟踪日期边界、替代解释剩余反例、真实输入和五日全池由协调方在 `codex/m8-takeover-r01` 继续。本线不改那条分支，不新开代码切片，不合并，不发起模型调用。
- B-008 仍是进行中，模块未验收通过。不写成已完成。AC-M8-06 未关闭。`test_case_attribution` 继续 pending。出现新编号后再做那一条。

## B-008  进行中  2026-10-17 15:57 北京

- 草稿 PR #18 head `82bacdb`。没有合并进 main。本地 `make phase1-test`：240 passed，18 deselected。
- UD-B-03 这一轮做完。有保存器时，每一条都没保存成功，任务行记失败并重新抛出；只失败一部分时，后面的异常继续，任务行只计已保存的条数。读回结案时，字典行按列名取，元组行仍按位置取。测试库连接只加入现有临时库网络，不改共享门禁。
- 仍开放：四例现场、五日全池。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。UD-COORD-04 的 19 次模型请求仍由协调方执行，本线没有发起。不把 B-008 写成已完成。

## B-008  进行中  2026-10-17 15:51 北京

- 用户决策 UD-B-03：问题是剩下的代码能不能尽快做完。用户原话「能尽快开发完吗」。照做：这一轮把全保存失败记账和 dict_row 续读做完。测试库连接不改共享门禁；夹具只连现有临时库。不把 B-008 写成已完成，不合并，不发起模型调用。正式五日全池和四例现场仍留给需求方。

## B-008  进行中  2026-10-17 15:46 北京

- 用户决策 UD-B-02：token 快用完，要尽快收口。用户原话「token快用完了，要不尽快收口？」。照做：不再开新的代码切片，不把 B-008 写成已完成，不合并 PR。每 10 分钟的唤醒先停，避免下一次再消耗。
- 草稿 PR #18 head `c1fdba1`。没有合并进 main。本地 `make phase1-test`：238 passed，18 deselected。
- 仍开放：全保存失败记账、dict_row、测试库连接超时、四例现场、五日全池。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。UD-COORD-04 的 19 次模型请求仍由协调方执行，本线没有发起。

## B-008  进行中  2026-10-17 15:45 北京

- 草稿 PR #18 head `c1fdba1`。没有合并进 main。本地 `make phase1-test`：238 passed，18 deselected。
- 已看到答复 `1d836d8`。替代解释排除仍是 15%。缺标记、空值或部分未知不再记成满分；三项都明确为否才是查无。每个候选只用自己的受影响标的和预期篮子。NVDA 为 0、AMD 为 1，无关股票不改变另一条。
- UD-COORD-04 已看到。这一批 19 次模型请求由协调方执行，本线没有发起。全保存失败记账和 dict_row 还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 15:36 北京

- 草稿 PR #18 head `ce2f045`。没有合并进 main。本地 `make phase1-test`：238 passed，18 deselected。
- 已看到答复 `466154b`。09:30 没有新的交易时段时，用刚结束的美股交易日另写一行。北京 10-16 上午和中午都写 10-15，周末写 10-16。异常起点仍是 10-14，这一行的支持留着。不把北京日历当天当成交易日。
- 替代解释的未知语义、全保存失败记账和 dict_row 还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 15:28 北京

- 草稿 PR #18 head `aad70ac`。没有合并进 main。本地 `make phase1-test`：237 passed，18 deselected。
- 已看到答复 `466154b`。这一轮没有新闻时，已经保存的支持、冲突和失效仍写回报告。同日、跨日和周末再读，经营结论、已证实、结案理由、未知项和历史都留下。有新闻再跑也不要求重新证明。没结案的仍是基本面核查中，不写成支持。
- 跟踪阶段自己的交易日还没改。替代解释的未知语义、全保存失败记账和 dict_row 还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 15:14 北京

- 草稿 PR #18 head `459d88c`。没有合并进 main。本地 `make phase1-test`：237 passed，18 deselected。
- 已看到答复 `71fb505`。12:30 没有新的交易时段时，不写默认轨道行，也不把已经记下的支持、失效或冲突盖成待验证。同日中午、跨日和周末再跑都留下原来的 10-14 那一行。
- 跟踪阶段自己的交易日还没改。替代解释的未知语义、全保存失败记账和 dict_row 还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 15:04 北京

- 草稿 PR #18 head `6f4d199`。没有合并进 main。本地 `make phase1-test`：236 passed，18 deselected。
- 已看到答复 `6ad76e5`。12:30 再跑时从已经保存的事件和报告读回结案。条件风险、支持和反证都留下，未知项也留下。没结案的不新结案，也不凭终态写成支持。
- Q-M8-16 第 4、第 5 项还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 14:55 北京

- 草稿 PR #18 head `14f388e`。没有合并进 main。本地 `make phase1-test`：235 passed，18 deselected。
- 已看到答复 `1e73c89`。Q-M8-16 第 3 项：主链计入替代解释排除，权重仍是 15%。没有自身财报、8-K 或评级时这分是 1；有这些自身事件时这分是 0，总分低于 0.5，不进入假设。没有成员时这一项仍缺失，不写成 0。
- 第 4、第 5 项还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 14:43 北京

- 草稿 PR #18 head `4a218b9`。没有合并进 main。本地 `make phase1-test`：234 passed，18 deselected。
- 已看到答复 `a04c0f0`。期限复验第 5 项：12:30 的打标任务不推进生命周期。已经形成的结案结论会留下来：条件风险、截止日仍未知和基本面失效不会退成待验证。没有这些结论的事件仍不结案。
- Q-M8-16 第 3 到第 5 项还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 14:33 北京

- 草稿 PR #18 head `bb2575a`。没有合并进 main。本地 `make phase1-test`：233 passed，18 deselected。
- 已看到答复 `40b3d13`。新反例第 2 项：写明的期限落在非交易日时，这一条记为期限不是交易日。10-18 星期日不再压过 20 个交易日上限，也不会被挪到别的日期。合法交易日和半日市仍可使用。
- 期限复验第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 14:25 北京

- 草稿 PR #18 head `419cbb2`。没有合并进 main。本地 `make phase1-test`：232 passed，18 deselected。
- 已看到答复 `65c66ed`。新反例第 1 项：同一候选里上涨篮子和下跌篮子方向不同时，二次命中按这次对上的篮子取方向。down-basket 的下跌不再套第一只上涨标的。错误篮子仍是未检验。
- 新反例第 2 项还没改。期限复验第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 14:15 北京

- 草稿 PR #18 head `40f6582`。没有合并进 main。本地 `make phase1-test`：231 passed，18 deselected。
- 期限复验第 4 项：期限已到但没有经营记录字段时，走原来的条件风险，结案理由仍是截止日仍未知，未知项写明经营记录缺失。没到期限时，缺这个字段也继续跟踪。空列表仍按原规则结案，不额外标成缺失。
- 期限复验第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 14:04 北京

- 草稿 PR #18 head `036acfc`。没有合并进 main。本地 `make phase1-test`：231 passed，18 deselected。
- 期限复验第 3 项：写明的期限早于事件起点时，这一条记为期限早于事件。10-01 不再当成 10-14 事件的最早期限，也不会立即结案。与起点同一天或更晚的日期仍可使用。
- 期限复验第 4、第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:54 北京

- 草稿 PR #18 head `bfb3f86`。没有合并进 main。本地 `make phase1-test`：230 passed，18 deselected。
- 期限复验第 2 项：财报周期或机制周期不是正整数时，这一条记为周期无效。负数或 0 不再收成起点当天，也不会在次日早晨结案。
- 期限复验第 3 到第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:45 北京

- 草稿 PR #18 head `c3dac17`。没有合并进 main。本地 `make phase1-test`：229 passed，18 deselected。
- 期限复验第 1 项：结案看美股反应日收盘，不看北京日历。10-14 开盘、财报周期 1 个交易日，期限是 10-15。北京 10-15 09:30 继续跟踪。北京 10-16 09:30 才按空记录结成已衰减·无影响，经营影响未证实。
- 期限复验第 2 到第 5 项，以及 Q-M8-16 第 3 到第 5 项，还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:34 北京

- 草稿 PR #18 head `b08cad9`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- Q-M8-16 第 2 项：二次命中只接受本次时点已经可见、并且对上预测指纹的材料。反应用预期残差和对照残差重算，不采用预填的命中。明天才发布、只谈 XOM 的新闻不会把 NVDA 记成确认。已经可见且对得上的后续材料仍可确认。
- 第 3 到第 5 项还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:26 北京

- 草稿 PR #18 head `ceca207`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 已看到 Q-M8-16。第 1 项：截止日取写明的日期，以及起点之后财报周期、机制周期和 20 个交易日里最早的一天。没到这一天就继续跟踪。到了这一天才走原来的经营门槛。空记录仍不写成经营影响已证实。报告留下这个日期。
- 第 2 到第 5 项还没改。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:15 北京

- 草稿 PR #18 head `370575e`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 09:30 的跟踪任务更新三轨并做截止日结案。空记录仍不会写成经营影响已证实。12:30 的打标任务不推进生命周期，报告里的标的代码留给下游。日程没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 13:06 北京

- 草稿 PR #18 head `c52dbc0`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 收盘时段没有起点时，用当日交易所开盘（美东 09:30）。盘后仍用收盘时刻。已经写明起点的对象不改。五日冻结报告的可见标题和状态没有因此改变。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:58 北京

- 草稿 PR #18 head `110f769`。没有合并进 main。本地 `make phase1-test`：228 passed，18 deselected。
- 有连接时，候选、跟踪和截止日本身就是被记录的操作。任务行先写入，阶段在这条操作里执行；阶段失败会把该行写成失败并重新抛出，而不是先跑完再记一个条数。没有连接时仍只执行、不写任务行。日程没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:47 北京

- 草稿 PR #18 head `2a080b2`。没有合并进 main。本地 `make phase1-test`：227 passed，18 deselected。
- 按 Q-M8-15 第 5 项：已有事件从原来的生命周期续上。假设中在四项同时成立时进入市场确认，供给等机制再进入基本面核查。截止日任务才按经营证据规则结案，空记录不会写成经营影响已证实。二次命中和多日跟踪留在同一对象上。影响分解和渠道写入报告。M7 的收盘和盘后对象用交易所收盘时刻作为起点。三个定时任务分别执行候选、跟踪和截止日，没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:39 北京

- 草稿 PR #18 head `f351333`。没有合并进 main。本地 `make phase1-test`：226 passed，18 deselected。
- 按 Q-M8-15 第 4 项：主链回捞改为实体、一跳图谱和批准向量的并集，再取前 40 条。只含 XOM 的新闻不会送给 NVDA。未批准的向量不进入。同一异常的两个候选按各自引用分开打分，缺输入的分项留空。没有新的补搜。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:26 北京

- 草稿 PR #18 head `01a5cdf`。没有合并进 main。本地 `make phase1-test`：225 passed，18 deselected。
- 按 Q-M8-15 第 3 项：候选的 affected 或说法的 claims 不是数组时，这一条记为结构不合格，不再当成合法的空结果。合法的空数组仍然是空。载荷里的候选和说法都写成数组。合法的 affected.basket_id 会留下来。没有改共享传输。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:14 北京

- 草稿 PR #18 head `6d9dd5b`。没有合并进 main。本地 `make phase1-test`：225 passed，18 deselected。
- 按 Q-M8-15 第 2 项：回放只处理当时已经发生的异常。10-16 才开始的对象不会在 10-13 或 10-14 写成已发现，也不会留下历史。已经发生的对象仍回放。新闻仍要到首次见到才进入报告。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 12:06 北京

- 草稿 PR #18 head `4144a2d`。没有合并进 main。本地 `make phase1-test`：225 passed，18 deselected。
- 按 Q-M8-15 第 1 项：同一异常的完整回捞、说法、候选、二次命中、影响分解、市场日、标的代码和报告再次保存改为更新原行。旧回捞留下，下一日跟踪另起一行。状态变了但没有完整审计条目时，拒绝这次变更，不再补一条只有旧状态和新状态的记录。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:57 北京

- 草稿 PR #18 head `8b0a66b`。没有合并进 main。本地 `make phase1-test`：224 passed，18 deselected。
- 五个交易日 2026-10-12 至 2026-10-16 的当时可见报告已冻结。截止点是每个交易日之后的第一个北京 12:30。10-14 的对象在 10-15 12:30 只能看见 CoreWeave，巴克莱和 CPI 仍是后补录。没有录音时状态是待分析。这批标题不是全池，也不是正式五日运行。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:48 北京

- 草稿 PR #18 head `6fddc08`。没有合并进 main。本地 `make phase1-test`：223 passed，18 deselected。
- 四个案例的固定输入可以写成规范载荷。文件字节的 SHA-256 就是计划里的哈希。`--capture` 留给需求方用已批准的客户端落录音。本轮没有调用模型，没有编造成功录音。一条失败不挡住下一条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:35 北京

- 草稿 PR #18 head `e173b23`。没有合并进 main。本地 `make phase1-test`：221 passed，18 deselected。
- 东芝完整解释报告和事件历史记在冻结夹具里。合成走查从已发现走到已验证，五步历史在再次保存后仍整段留下，不会收成一跳。三天跟踪都留下。经营证据标明合成。不是现场结论。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:23 北京

- 草稿 PR #18 head `6a5216d`。没有合并进 main。本地 `make phase1-test`：220 passed，18 deselected。
- 按 Q-M8-14 第 5 项：候选和说法的返回结构写在各自载荷里。机制只有五档。分数、置信度、证据、经营结论和假设标记都标明不由模型决定。整包结构不合格时这一条降级，下一条继续。没有改共享传输、模型或密钥。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:14 北京

- 草稿 PR #18 head `075c6c2`。没有合并进 main。本地 `make phase1-test`：219 passed，18 deselected。
- 按 Q-M8-14 第 4 项：有可见新闻时，一条入口把回捞、说法、候选、规则打分、解释报告、生命周期和保存串起来。模型自填的分数不会留下。调用失败的那条标成待分析，下一条继续。五日回放只使用当时已经见到的材料。三个定时任务有代码入口，日程本身没有部署。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 11:02 北京

- 草稿 PR #18 head `ab54313`。没有合并进 main。本地 `make phase1-test`：217 passed，18 deselected。
- 按 Q-M8-14 第 6 项：广域异常不再写入标的代码，仍可记下回捞和报告。一条广域被拒绝后，后面的异常继续保存。池内的 N1、N2、N6 照常写。六项证据都缺失时，分数留空，不进入假设，也不再除零。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:56 北京

- 草稿 PR #18 head `5c274e6`。没有合并进 main。本地 `make phase1-test`：217 passed，18 deselected。
- 按 Q-M8-14 第 3 项：同一事件第二次保存不再撞主键。生命周期写成新状态，原来的审计历史整段留下，同日再跑不会把历史清空。同日跟踪改这一行；下一日另起一行，前一日那一行还在。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:42 北京

- 草稿 PR #18 head `80009f7`。没有合并进 main。本地 `make phase1-test`：216 passed，18 deselected。
- 按 Q-M8-14 第 2 项：校验候选时不再保留模型自填的分数、置信度、证据、经营结论和假设标记。引用、机制、传导链和受影响标的仍留下。没有规则算出的分数时，不进入中高置信，也不写经营支持。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:32 北京

- 草稿 PR #18 head `db64e96`。没有合并进 main。本地 `make phase1-test`：215 passed，18 deselected。
- 按 Q-M8-13：严格回放和检索窗口在首次取得时间缺失或为空时，不再用发布时间补上。这种材料不进入当时可见，collected_then 和 vectors_then 都为假，模式记为未知。已有首次取得时间且不晚于时点的正例仍是当时可见。明确晚于时点的仍是后补录历史复盘。生产路径不接受案例模式。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:22 北京

- 草稿 PR #18 head `e750146`。没有合并进 main。本地 `make phase1-test`：214 passed，18 deselected。
- 超预期记录最新在前，最多四季。不足四季照存，不取平均。没有季度日期的不排进去。幅度沿用传入的百分数，不从实际值和预期另算。不算经营证据，不改基本面栏。没有传入时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:12 北京

- 草稿 PR #18 head `a2e4a98`。没有合并进 main。本地 `make phase1-test`：213 passed，18 deselected。
- 当年 EPS 分歧度是（最高 − 最低）÷ |当年 EPS|。绝对值小于 0.01 时分歧度留空，等于 0.01 时照公式算。缺最高、最低或当年 EPS，或出现布尔值时留空。不写成未下修或显著下修。不算经营证据，不改基本面栏。没有传入时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 10:02 北京

- 草稿 PR #18 head `8f67174`。没有合并进 main。本地 `make phase1-test`：212 passed，18 deselected。
- 近 7 天和近 30 天的修订广度是（上修家数 − 下修家数）÷ 覆盖家数。家数用传入的窗口计数，不在这里重数事件。覆盖为 0、缺任一数、或出现负数和布尔值时，广度留空。下修达到覆盖的 30% 也不在这里写成显著下修。不算经营证据，不改基本面栏。没有传入时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:52 北京

- 草稿 PR #18 head `3eafdf5`。没有合并进 main。本地 `make phase1-test`：211 passed，18 deselected。
- 一致预期快照按自然日回望 7、30、60、90 天，只取正好那一天的当季、下季、当年、次年。缺那一天、当天没有快照、或同一天数字冲突时，该格是缺失，不用邻近日期填。前值为 0 时变化留空。这里不写未下修或显著下修。不算经营证据，不改基本面栏。没有传入快照时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:42 北京

- 草稿 PR #18 head `0acc18d`。没有合并进 main。本地 `make phase1-test`：210 passed，18 deselected。
- 全量库从首次取得时间起保留 90 天全文，满 90 天仍保留，超过之后全文不再返回。摘要和向量在窗口内外都按原样保留，缺了不从全文补写。没有首次取得时间、时点类型对不上、或时点早于首次取得时，不写这条。过期后仍可检索。不算经营证据，不改基本面栏。没有传入材料时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:32 北京

- 草稿 PR #18 head `509e0335`。没有合并进 main。本地 `make phase1-test`：209 passed，18 deselected。
- 叙事扩散、资金延续、基本面为「开始修订」时，解读记成「基本面开始兑现」。缺资金状态时不写这条。资金是其他状态，或基本面写成局部支持，都不套这条。解读不改估值栏，报告估值仍是「不变 / 待基本面轨道」。不提高研究优先级，不写背离标签，不算经营证据，不改基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:22 北京

- 草稿 PR #18 head `cb30b28`。没有合并进 main。本地 `make phase1-test`：208 passed，18 deselected。
- 叙事衰减且基本面未变时，回吐比例小于或等于 0 记成「价格新均衡」，研究优先级提高。大于 0 且不超过 0.5 仍不命名。这条不发起回捞，不改研究排序，不写背离标签，不改估值，不算经营证据，不改基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:12 北京

- 草稿 PR #18 head `a42f2cd`。没有合并进 main。本地 `make phase1-test`：207 passed，18 deselected。
- 有一致预期时，NTM 另给一条市场侧金额，公式仍是前一日市值乘剩余收益再除以市盈率，只用 TTM 已经计入的成员。TTM 一个都计不上时，NTM 也留空。已计入的成员里只要有一个缺 NTM 市盈率、市盈率为 0、或不是有限数，整条 NTM 留空，不把其余成员加总。负的 NTM 市盈率照公式算。这条不改 TTM 金额，不写相容或部分相容，不算经营证据，不改基本面栏。没有传入成员时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 09:01 北京

- 草稿 PR #18 head `776de94`。没有合并进 main。本地 `make phase1-test`：206 passed，18 deselected。
- 资金轨道的 5 日和 20 日回吐比例沿用 r = 1 − 累计剩余 ÷ 首日剩余，两个窗口分开记。缺窗口、累计或首日不是有限数、或首日剩余为 0 时，该窗口是缺失，不写成 0。算出来等于 0.5、大于 1，也不在这里写成已消化、反转或其他资金状态。不改估值，不算经营证据，不改基本面栏。没有传入窗口时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:52 北京

- 草稿 PR #18 head `384d179`。没有合并进 main。本地 `make phase1-test`：205 passed，18 deselected。
- 覆盖自检记下每天的异常总数、找到候选的数量和原因未明的数量。原因未明比例是未明数除以总数。总数为 0、缺任一计数、计数不是非负整数、找到候选或未明多于总数时，比例是缺失。报警要至少三天，而且每一天的比例都严格高于前一天。只有两天、中间持平或回落、或其中一天比例缺失，都不报警。只给出报警标记，不写健康页。这条不算经营证据，不改基本面栏。没有传入覆盖天数时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:41 北京

- 草稿 PR #18 head `bb1c6f5`。没有合并进 main。本地 `make phase1-test`：204 passed，18 deselected。
- 共识度只写市场层。独立来源根按非社交材料去重计数，空名字不算，社交来源不计数，社交标成未接通。搜索倍数只在给出的数字都相同才记下，没有或互相不一致就留空，不合成一个高低档。卖方点评只认二三级点评；一级和四级点评不算卖方，缺等级是缺失。不写置信度。这条不算经营证据，不改基本面栏。没有传入共识材料时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:31 北京

- 草稿 PR #18 head `a0f832f`。没有合并进 main。本地 `make phase1-test`：203 passed，18 deselected。
- 研究资源按四档排序：持仓风险、近期候选、可改变驱动因子的关键环节、重大未知异常。持仓而且标明风险才进第一档，只持仓或只标风险都不进。候选要另外标明近期才进第二档；规格没有写近期是多少个交易日，所以不把没标明的候选当成近期。同一档保持传入顺序。对不上四档的排在最后，原因留空。这条不替换五档核验队列，不算经营证据，不改基本面栏。没有传入研究名单时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:22 北京

- 草稿 PR #18 head `8f06c82`。没有合并进 main。本地 `make phase1-test`：202 passed，18 deselected。
- 一手数据突变直接进入关注队列，不需要新闻。监控实体的榜单名次跳升严格多于 20 名，或搜索热度严格大于自身历史的 3 倍，或官网发布新产品，三条有一条即可。恰好 20 名或恰好 3 倍不算。没有监控实体的榜单和搜索不算。缺比较值、并且另外两条也没有写成否时，是缺失。这条不算经营证据，不改基本面栏。没有传入一手信号时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:12 北京

- 草稿 PR #18 head `67831a1`。没有合并进 main。本地 `make phase1-test`：201 passed，18 deselected。
- 新边的状态只写成候选，提议更高也不提升。价格共振或证据全是价格时，不能把关系升到已确立；原来的较低状态留下，缺状态是缺失。市场共振或市场叙事要改成经营传导，必须经营证据规则给出支持。反证、条件风险、只有价格、或缺时间或缺方向，连接类型不变。即使经营证据支持了传导类型，也不改基本面栏，也不把经营影响标成已证实。没有提议这三件事时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 08:02 北京

- 草稿 PR #18 head `9bc8208`。没有合并进 main。本地 `make phase1-test`：200 passed，18 deselected。
- 传闻被一级否认或矛盾之后，内容退出经营依据。只认传闻或四级材料；一级文件被否认不走这条。二级否认不算证伪。价格冲击原样留下，0 也算有记录，缺记录是缺失而不是删掉。来源根或信息编号留下，空字符串不算传播记录。这条不改基本面栏。没有传入这条时不写。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:51 北京

- 草稿 PR #18 head `6bcbe26`。没有合并进 main。本地 `make phase1-test`：199 passed，18 deselected。
- 丢弃抽检每周最多 20 条。只有标明已丢弃、并且有信息编号的材料才进入人工复核。没丢弃、没标明、或没有编号，都不占名额。同一编号只占一条，按传入顺序取满 20 条后停止。规格写的是随机抽样，但没有给抽样种子，所以这一刀不打乱顺序。后来标明重要的才计入漏检，没写这一栏是缺失，不是不漏。这些材料不算经营证据，不改基本面栏。没有传入丢弃名单时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:42 北京

- 草稿 PR #18 head `30540a9`。没有合并进 main。本地 `make phase1-test`：198 passed，18 deselected。
- 探索名额每天最多 3 条。只有同时标明低热度、并且标明涉及新机制、又有信息编号的材料才进入研究。缺任一标记、热度不低、机制不是新的、或没有编号，都不占名额。同一编号只占一条，按传入顺序取满 3 条后停止。这些材料进入研究，不算经营证据，不改基本面栏。没有传入探索名单时不写这条。每周 20 条丢弃抽检仍未做。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:33 北京

- 草稿 PR #18 head `a87d205`。没有合并进 main。本地 `make phase1-test`：197 passed，18 deselected。
- 四项市场指纹只用来排除对不上的解释，不指出唯一原因。暴露梯度沿用已有的秩相关，大于 0 才算暴露更直接的反应更强，成员少于 3 或秩相关算不出是缺失。无暴露对照沿用篮子特异性，预期篮子绝对残差均值大于对照才算对照表现不同，缺篮子是缺失。时序沿用时间对齐，早于或落在时段内算相容，晚于时段不算。反证响应沿用官方否认后的绝对值减弱，没有否认、不是官方否认、或缺剩余收益时这一项是缺失。某一项为假就列入不相容，缺失不算不相容。四项都通过也不写市场关联状态，不改基本面栏，不算经营影响。没有传入指纹时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:22 北京

- 草稿 PR #18 head `c00ab17`。没有合并进 main。本地 `make phase1-test`：196 passed，18 deselected。
- 三轨组合只认两行已经写明的对照。叙事衰减、回吐严格大于 0.5、基本面未变，读成冲击已消化。叙事衰减、资金延续、基本面冲突，读成价格和基本面背离。恰好 0.5 不算已消化。缺叙事、缺基本面、衰减而未变却缺回吐、或衰减而冲突却缺资金状态时，不写结论。扩散加延续加开始修订不写成兑现，也不改估值。这两行不提高研究优先级，不挑选背离标签，不改基本面栏。没有传入三轨时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:12 北京

- 草稿 PR #18 head `cee688d`。没有合并进 main。本地 `make phase1-test`：195 passed，18 deselected。
- 官方否认之后，后一次剩余收益的绝对值更小，才记反应减弱。一级否认或矛盾才算官方否认。二级否认、一级确认、缺任一侧剩余收益，这条不写结论。绝对值相等或更大，不算减弱。符号反过来但绝对值更小，仍算减弱。这条不改二次命中结论，不算经营证据，也不改基本面栏。没有传入否认时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 07:02 北京

- 草稿 PR #18 head `b092942`。没有合并进 main。本地 `make phase1-test`：194 passed，18 deselected。
- 鉴伪清单有八项：原始出处、完整表述、发布时间、首次取得时间、是否旧闻重发、传播关系、独立来源数、反方材料。缺项是未知。空字符串不算完整表述。来源根按去重计数，空名字不算。转载标记为假也算有数据。清单填满也不改真实性，不算经营证据，不改基本面栏。没有传入清单时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:52 北京

- 草稿 PR #18 head `0fc5472`。没有合并进 main。本地 `make phase1-test`：193 passed，18 deselected。
- 晚于异常起点的报道可以解释之后的传播，不能解释已经发生的下跌。同一时刻或更早的报道，这条两边都不下结论。缺发布时间或缺起点是缺失。这不改时间对齐的 1.0、0.7 和 0，也不改基本面栏，也不证明经营影响。没有传入时间时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:42 北京

- 草稿 PR #18 head `3c53a64`。没有合并进 main。本地 `make phase1-test`：192 passed，18 deselected。
- 链条上市场确认、消息真实性和盈利传导分开。市场确认不把未核实改成核实。核实或修订也不自动写成盈利传导。发现异常的那次价格不能再当作传导。证伪和部分核实仍缺消息真实性。三条都齐时仍不证明经营影响，也不改基本面栏。没有传入链条时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:32 北京

- 草稿 PR #18 head `d2c1281`。没有合并进 main。本地 `make phase1-test`：191 passed，18 deselected。
- 传闻拆成两件事。有来源根或信息编号时，发表本身进叙事。内容要有另一个来源根的一二级定量说法，并且变量相同、不是价格、热度、二次命中、共识或资金流，也不是反证，才算经营证据。同一来源根、三级来源、变量对不上，或传闻自己没写变量，都不算。一级说法本身不走这条。这条不改真实性，不改基本面栏，也不证明经营影响。没有传入传闻时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:22 北京

- 草稿 PR #18 head `9e98ddc`。没有合并进 main。本地 `make phase1-test`：190 passed，18 deselected。
- 核验队列按五档排序：持仓的经营证伪或风险越限、直接量化的经营变化、异常中的新解释、可能改变产业关系的新机制，其余是普通重复背景。同一档保持原来的先后。真实性不改变档位。一级来源即使传播为 0 也必须核验，四级来源传播再高也不因此核验。价格上的数量不算直接量化。这条队列不替换检索排序，不调用模型，也不改基本面栏。没有传入队列时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:12 北京

- 草稿 PR #18 head `b1cbc23`。没有合并进 main。本地 `make phase1-test`：189 passed，18 deselected。
- 弱信号在 30 个交易日内凑齐至少 3 个来源根和 2 个阶段，并且窗口内没有直接反证时，只提高研究优先级，并记一条补证任务。生命周期停在已发现，不进入假设中。缺比较日或缺阶段时是缺失。这一条不升级真实性，不改基本面栏，也不进覆盖层。没有传入线索时不写这条。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 06:04 北京

- 草稿 PR #18 head `a27dc2e`。没有合并进 main。本地 `make phase1-test`：188 passed，18 deselected。
- 情绪放大只作描述。来源根数达到扩散（至少 3，并且至少是昨日的 1.5 倍）、搜索热度严格大于自身历史的 3 倍，或榜单名次跳升严格多于 20 名，并且基本面还没有局部支持、支持或冲突时，记为真。缺比较日或没有热度输入时是缺失。这一条不改基本面栏，不证明经营影响，也不把不相容写成情绪。没有传入热度时不写结论。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:53 北京

- 草稿 PR #18 head `8e539f9`。没有合并进 main。本地 `make phase1-test`：187 passed，18 deselected。
- 市场确认的独立证据不是价格。两个不同来源根、带监控实体的搜索热度突增，或一二三级点评，满足一条即可。同一来源根只算一次。四级点评和没有监控实体的热度标记不算。这一条单独成立也不能进入市场确认，另外三项仍要同时满足。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:42 北京

- 草稿 PR #18 head `7b80d3b`。没有合并进 main。本地 `make phase1-test`：186 passed，18 deselected。
- 一条当时可见的一二级定量说法把基本面写成局部支持。四级来源、没有数量、价格、热度、二次命中、共识，以及截止后才见到的材料，仍是待验证。局部支持不是支持，也不证明经营影响。估值倍数仍不写基本面栏。截止日已经写出的支持、冲突或失效保持不变。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:32 北京

- 草稿 PR #18 head `805deeb`。没有合并进 main。本地 `make phase1-test`：185 passed，18 deselected。
- 隐含幅度按渠道各写一条。缺金额的渠道是无法检验。单条渠道用同一套 1.5 和 5 的界限，不相容仍写不相容，不写成情绪。没有传入隐含幅度时不写渠道行。这不改变基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:21 北京

- 草稿 PR #18 head `632f8c2`。没有合并进 main。本地 `make phase1-test`：184 passed，18 deselected。
- 没有向量、或向量不是批准的模型和维度时，检索降到规则，报告写「向量检索降到规则检索」。没有传入向量材料时不写这句。这句不改变经营结论，也不改变市场分和基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:12 北京

- 草稿 PR #18 head `945a4c6`。没有合并进 main。本地 `make phase1-test`：183 passed，18 deselected。
- 由价格异常回捞来的后续信息，首次见到时间必须早于那次响应。同一时刻或更晚见到的不算，缺首次见到时间也不算。不是从价格异常回捞来的材料，仍只看发布时间和来源根。这不改经营结论。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 05:02 北京

- 草稿 PR #18 head `3ca9d66`。没有合并进 main。本地 `make phase1-test`：182 passed，18 deselected。新的检查在原有二次命中测试里。
- 二次命中按预期方向取号。上涨时剩余收益至少 +1 且对照篮子绝对值小于 1 才是命中，反方向至少 1 是反证。下跌把符号反过来。对照篮子自己也到 1 时不算命中。东芝合成走查的后续剩余收益改成与下跌方向一致的负数，结论仍是确认。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:52 北京

- 草稿 PR #18 head `85152d5`。没有合并进 main。本地 `make phase1-test`：182 passed，18 deselected。
- 解释报告把市场归因置信度和基本面成立度分开。市场分按最高候选：0.70 起为高，0.50 起为中，再低是低。供给、需求、竞争、客户融资达到 0.5 时，基本面先写待验证。估值倍数和不够 0.5 的候选不写基本面成立度。市场分高不能抄进基本面栏。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:41 北京

- 草稿 PR #18 head `df013dd`。没有合并进 main。本地 `make phase1-test`：181 passed，18 deselected。
- 状态至少「观察到」但没有美元暴露的边，登记一条补暴露任务，原因是缺美元暴露。候选边不登记，估值倍数不登记。这条任务不把结论改成不相容，也不写金额 0。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:32 北京

- 草稿 PR #18 head `95ffffe`。没有合并进 main。本地 `make phase1-test`：180 passed，18 deselected。
- 隐含幅度证据分只认三档：相容 1.0、部分相容 0.6、不相容 0.2。无法检验是缺失，按剩余权重重配，不记成 0。情绪这两个字不进分数。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:22 北京

- 草稿 PR #18 head `29e521e`。没有合并进 main。本地 `make phase1-test`：179 passed，18 deselected。
- 市场归因至少为中的候选才登记指纹。字段是关联实体、预期篮子和方向、对照篮子。结论留在市场层。低于中、或不打分的默认候选不登记。后续信息要晚于起点并且实体相交才对得上这枚指纹。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:14 北京

- 草稿 PR #18 head `e874546`。没有合并进 main。本地 `make phase1-test`：178 passed，18 deselected。
- 渠道由机制决定。供给走供给/价格，需求和竞争走直接收入，客户融资同时走订单/积压和融资/对手方，估值倍数只有估值倍数。信源取引用里最高的等级。美元暴露只加总状态至少「观察到」的关系。分部收入用分部利润率，不退回公司利润率。缺利润率或订单缺兑现年数时结论是无法检验，不把缺项写成 0。不相容不写成情绪。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 04:03 北京

- 草稿 PR #18 head `5dbdbcf`。没有合并进 main。本地 `make phase1-test`：177 passed，18 deselected。
- 市场侧金额只加总 EPS 为正的成员：前一日市值乘剩余收益再除以 TTM PE。EPS≤0、PE 不可用、或只有总涨跌没有剩余收益的成员不计入。一个都计不上时结论是无法检验，不把金额写成 0。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:51 北京

- 草稿 PR #18 head `a34efe2`。没有合并进 main。本地 `make phase1-test`：176 passed，18 deselected。
- 篮子特异性是预期篮子绝对残差均值减去对照篮子，再除以 3，限制在 0 到 1。没有对照篮子是缺失。叙事证据按同时提到事件和受影响名字的独立来源根计数，同一来源根只算一次，5 个封顶。替代解释排除只减掉自身财报反应、8-K 指引或评级变化的成员，价格本身不减。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:41 北京

- 草稿 PR #18 head `1436f12`。没有合并进 main。本地 `make phase1-test`：175 passed，18 deselected。
- 暴露梯度用状态至少「观察到」的关系：直接 3、间接 2、概念关联 1，再和按预期方向取号的残差做 Spearman，负相关记 0。成员少于 3、残差缺失、候选或已退出的关系，以及暴露全部相同，都是缺失而不是 0。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:31 北京

- 草稿 PR #18 head `17dcffe`。没有合并进 main。本地 `make phase1-test`：174 passed，18 deselected。
- 标的代码只写在池内。广域不写。没有达到 0.5 的候选时，异常成员写成 N6。达到 0.5 的估值倍数写成 N2，同一名字不再写成 N1。供给要同时是叙事冲击且基本面未变才写成 N1，否则留空。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:22 北京

- 草稿 PR #18 head `dd9672d`。没有合并进 main。本地 `make phase1-test`：173 passed，18 deselected。新的检查在原有说法测试里。
- 说法抽取只接受前 40 条。已经有说法字段的材料不再送去抽取，空说法也算已经抽过。多出来的一条不会调用模型。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:11 北京

- 草稿 PR #18 head `9a26521`。没有合并进 main。本地 `make phase1-test`：173 passed，18 deselected。
- 短名单已满 5 条时，报告不写「补证未执行」。预算用完时，这句话写入报告的补证栏和未知项，不改变经营结论，也不改变生命周期。这一步仍不发起搜索。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 03:01 北京

- 草稿 PR #18 head `78e6b0b`。没有合并进 main。本地 `make phase1-test`：172 passed，18 deselected。
- 短名单已经有 5 条时不补搜。不足 5 条且预算用完时，调用次数是 0，报告写「补证未执行」。补搜结果的首次见到时间是当前时刻，时间对齐仍只用发布时间；当前时刻之前的回放看不见它。这一步只做计划，不发起搜索。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:52 北京

- 草稿 PR #18 head `38c798f`。没有合并进 main。本地 `make phase1-test`：171 passed，18 deselected。
- 短名单先按可见窗口过滤，再用检索分取前 40 条，不沿用原来的 rank。对不上检索实体、也没有批准向量的材料不占名额。窗口外和当时还看不见的材料进不了说法抽取。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:42 北京

- 草稿 PR #18 head `ad48446`。没有合并进 main。本地 `make phase1-test`：170 passed，18 deselected。
- 规则命中和批准向量的前 50 条取并集，再按来源根留一条。第 51 条向量、未批准的模型，都不能靠相似度进来。同一来源根的转载并进那一条，路径仍记下规则和向量。向量查询只拼篮子名、方向和成员名。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:32 北京

- 草稿 PR #18 head `234b149`。没有合并进 main。本地 `make phase1-test`：169 passed，18 deselected。
- 检索实体只含异常成员、这些成员所属篮子的其他成员、从这组名字出发的一跳邻居，以及用代码挂到这组名字上的监控实体。邻居任何状态都算，包括驳回。邻居的下一跳、同伴所在的其他篮子、监控实体带出的其他代码，都不进入检索。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:22 北京

- 草稿 PR #18 head `37dd333`。没有合并进 main。本地 `make phase1-test`：168 passed，18 deselected。
- 供给或需求的约束清单有四档结论。缺来源、四级来源，或没有写明冲击是有限还是实质时，结论是「约束不清但有上下界」。一二三级来源写明冲突时，标签是「关键约束冲突」。这两档都不把经营影响标成已证实，也不关闭案例。东芝合成走查的经营结论仍来自合成 8-K，约束清单自己仍是不清。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:17 北京

- 草稿 PR #18 head `be94cb9`。没有合并进 main。本地 `make phase1-test`：167 passed，18 deselected。
- 解释报告带影响范围和跟踪清单。暴露只跟关系走。候选关系、已退出的关系降成概念关联。没有关系的价格成员是纯共振。估值倍数停在概念关联。供给或需求的清单上，「有数据」不是证据。东芝合成走查已验证之后，WDC 仍是纯共振，类型候选只有事件冲击。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 02:03 北京

- 草稿 PR #18 head `bd4da67`。没有合并进 main。本地 `make phase1-test`：166 passed，18 deselected。新的案例测试单独通过。
- 捕获命令同时打印候选路径和说法抽取路径。两条路径不同，不调用模型，也不写文件。缺候选文件时状态是待分析，缺说法文件时状态是抽取失败。截止后没有可用材料时不打印说法路径。没有编造成功录音。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:54 北京

- 已读 main `7768fc9`。Q-M8-12 的 13 项复核已关闭，没有重做，也没有重做 17 项经营门槛。草稿 PR #18 head `fd99d88`。没有合并进 main。本地 `make phase1-test`：165 passed，18 deselected。
- 解释报告的类型候选只跟已打分的机制走。分数达到 0.5 的估值倍数写成叙事冲击。经营影响已证实的供给、需求、竞争或客户融资写成事件冲击。没有达到 0.5 的分数写成原因未明。案例名字本身不会写成叙事冲击。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:44 北京

- 草稿 PR #18 head `82d485f`。没有合并进 main。本地 `make phase1-test`：164 passed，18 deselected。新的案例测试单独通过。
- 四个历史案例的录音路径可以打印。命令不调用模型，也不写文件：`PYTHONPATH=src python -m inves_cog.perception.attribution.capture_plan --fixture tests/fixtures/phase1 --root recordings`。缺文件时调用失败，状态是待分析。没有编造成功录音。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:37 北京

- 已读 main `158f056` 的 Q-M8-12。草稿 PR #18 head `b0f9ddf`。没有合并进 main。本地 `make phase1-test`：164 passed，17 deselected。
- Muse 按被引用材料的日期区间和开盘比较：09-18 早于 09-21 开盘，同一天是未知。不靠 `before_open`。R1 的前 3 名必须引用发布材料，并让受影响标的连到成员。OpenAI 的前 4 名按候选计，第 5 名不能补。结构清单空也不把 `closes_case` 设为真。
- blob：`historical.py` `0e87a6c1d117f8f7ccc0f637e18b8bffa7a34772`，`manual.py` `7d32147a2b123dd4dbe2fd14f089ed70e7ce5c85`。`cases.py` 未改。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:23 北京

- 草稿 PR #18 head `52d36b0`。没有合并进 main。本地 `make phase1-test`：161 passed，17 deselected。新的案例测试单独通过。
- 2026-10-02 的 HDD 对象成员是 STX 和 WDC，没有 MU。截止日只能看见东芝扩产这条四级转载。机制不是供给时结构清单不通过。机制写成供给后，只表示标题对上了日经转载，不能当成经营证据。TDK 时间上可以做二次命中，夹具没有价格响应，结论保持未检验。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:12 北京

- 草稿 PR #18 head `5d43332`。没有合并进 main。本地 `make phase1-test`：161 passed，16 deselected。新的案例测试单独通过。
- 2026-09-21 的池内对象已经分别含有 CPU 篮子和 META。Axios 仍停在 09-18，角色是背景。没有录音时调用失败。引用登顶材料之后，剩下的缺口是「不能证明早于开盘」，案例不关闭。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 01:04 北京

- 草稿 PR #18 head `744bc39`。没有合并进 main。本地 `make phase1-test`：161 passed，15 deselected。新的案例测试单独通过。
- 2025-01-27 的 M7 异常对象里，方向向下、成员含 NVDA 的篮子名含「加速」。后补录发布页在这个截止日可用，更晚的 Reuters 和 Axios 进不了候选。没有录音时调用失败。临时引用能消掉加速芯片篮子这条结构缺口，这只表示结构清单空了。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:54 北京

- 草稿 PR #18 head `79e49ef`。没有合并进 main。本地 `make phase1-test`：161 passed，14 deselected。
- TDK 标题的发布时间晚于 2026-10-02 开盘，时间上可以做二次命中。夹具没有价格响应，结论保持未检验。它的首次见到时间在 2026-10-14，发布当天的严格路径看不见。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:41 北京

- 草稿 PR #18 head `d427085`。没有合并进 main。本地 `make phase1-test`：160 passed，14 deselected。
- 现场候选录音的入口是 `candidate_capture`。文件名是载荷的 SHA-256，缺文件就失败。仓库里没有编造的成功录音。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:33 北京

- 草稿 PR #18 head `55302e7`。没有合并进 main。本地 `make phase1-test`：159 passed，14 deselected。导出文件没有进入本 PR。
- 冻结了导出 `cd02bdd` 的七条标题。规则上 CoreWeave、巴克莱和 CPI 可以补上 OpenAI 的三类，东芝标题是日经转载。这是夹具，不是现场录音。北京 10-15 09:15 只能看见 CoreWeave，看不见巴克莱和 CPI。
- 不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:22 北京

- 草稿 PR #18 head `478e93c`。没有合并进 main。本地 `make phase1-test`：158 passed，14 deselected。
- 后补录历史案例的候选只引用截止前可用的材料。不在这批材料里的引用会被丢掉。没有录音时调用失败，不编造成功。
- 案例仍未通过：发布材料还缺加速芯片篮子，Reuters 只占一类背景，Axios 不能证明早于开盘，东芝仍缺日经扩产原文。不关闭 AC-M8-06。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:13 北京

- 已读 main `c5b7e96` 的 M8 v8（Q-M8-11）。草稿 PR #18 head `1f0011a`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：157 passed，14 deselected。
- 三条人工补证可以进入「后补录历史案例」：发布页走发布路径，Reuters 转述只作背景且不是 FT 原文，Axios 停在 09-18、不能证明 72 小时主窗口，角色标成背景。这不表示案例已通过，也不关闭 AC-M8-06。
- 生产路径不接受案例模式。`first_seen_at` 晚于回放时点的材料仍然不可见。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-17 00:02 北京

- 草稿 PR #18 head `4539b31`。没有合并进 main。本地 `make phase1-test`：156 passed，14 deselected。
- 三条 2026-10-16 人工补证接到对应案例日之后仍是后补录。发布页没有榜单快照，Reuters 转述不是已冻结的 FT 原文，Axios 停在 09-18。标题方向对得上也不关闭第 7.1 节。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:55 北京

- 草稿 PR #18 head `9b66ae4`。没有合并进 main。本地 `make phase1-test`：155 passed，14 deselected。`make phase1-cases`：3 passed，166 deselected。
- M7 四个案例日的异常对象在没有当时可见新闻时各有状态：池内是「已发现·原因未明」，广域是「已记录」。不调用模型。这不是第 7.1 节通过。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:41 北京

- 已读 main `a5991c9`。UD-COORD-02 已把 PR #11 和 PR #16 合并进 main。草稿 PR #18 head `15479f3`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：154 passed，13 deselected。
- M7 已实现的测试留在套件里，没有退回 pending。三条人工补证仍不关闭第 7.1 节缺口。`test_case_attribution` 继续 pending。不开始下一条，也不开始 M9/M10。

## B-008  进行中  2026-10-16 23:37 北京

- 草稿 PR #18 head `b2ea6cd`。已合入 main `2247520`。没有合并进 main。本地 `make phase1-test`：138 passed，11 deselected。
- 经营证据门槛在 `38e8471` 已关闭。本步是来源夹具：2026-10-16 人工读取的三条公开页冻结为后补录摘录，当时未采集，也没有向量。
- 官方页只有发布日期 2025-01-20，没有榜单快照。Reuters 转述印着 10-08 05:12 PM 和 10-09 02:49 AM，页面没有时区；9 月年化收入接近 500 亿美元，来源根是 Reuters，FT 原文仍未冻结。这两天都早于 10-14，只作背景，不做二次命中。Axios 日期是 09-18，不能改成 09-19，09-19 至 09-21 开盘前的榜单仍缺。
- `test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:22 北京

- 草稿 PR #18 head `38e8471`。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。
- 估值倍数类联动停在市场层，进入基本面核查会拒绝。供给、需求、竞争、客户融资仍可进入。东芝走查以供给进入核查。
- 经营证据的四项反例仍在 `f559023`，等需求方独立复核。`test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:12 北京

- 已读 main `31e8ceb` 对 `a028e59` 的四项反例。草稿 PR #18 head `f559023`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。
- 覆盖人数 NaN、修订人数无穷大、修订人数超过覆盖人数、EPS 变化 NaN，都保持条件风险。恰好 30% 和 3% 仍通过。空证据的条件风险不能靠普通赋值改成支持；截止日使用时会再核验。合法结构化证据仍能走到已验证。等需求方按这个 SHA 独立复核。
- `test_case_attribution` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 23:04 北京

- 草稿 PR #18 head `7dbbca3`。没有合并进 main。本地 `make phase1-test`：137 passed，11 deselected。`make phase1-cases`：1 passed，147 deselected。
- 空新闻路径已从 pending 删除。四个案例在标明 synthetic、新闻为空时状态都是「已发现·原因未明」，不调用模型。这不是真实源判定。
- `test_case_attribution` 继续 pending。真实冻结新闻仍缺 10-08 FT 年化营收、09-19 至 09-21 开盘前的 Muse 榜单、R1 或登顶。不开始下一条。

## B-008  进行中  2026-10-16 22:55 北京

- 已读 main `5ce0e6e` 上的经营证据预检和 M8 v7。草稿 PR #18 head `a028e59`，已合入这份 main。没有合并进 main。本地 `make phase1-test`：137 passed，10 deselected。
- 经营已验证不再接受单独的 filing、股价、资金流、社交热度、市场共识度或二次命中。公司一级材料要有可定位引用，并且是 8-K 指引变更或电话会定量表述。EPS 修订要至少 30% 分析师同向、当年共识变化至少 3%、方向一致。产业数据要两个独立来源根。缺字段、未来材料、已证伪材料不通过。约束项仍未知时，另一条合格证据可以支持，未知项保留。截止日不能直接传入「支持」。
- 东芝走查用的是标明 synthetic 的 8-K 指引变更，不是真实公告。`test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。不开始下一条。

## B-008  进行中  2026-10-16 22:45 北京

- 草稿 PR #18 head `ed694dc`。没有合并进 main。本地 `make phase1-test`：136 passed，10 deselected。
- 感知表写入走调用方传入的连接，不打开数据库地址。广域异常只写回捞和报告，状态改成已记录。已评分但没有引用的候选会拒绝。一次性测试库里 `role_perception` 写入十张归因表成功，空引用被约束拦住，事务已回滚。`role_ingest` 插入被拒绝。没有 GRANT ingest，没有写共用库。真实补证入库仍停在 `Repository.put_info`。
- `test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。三处缺口仍缺冻结夹具。不开始下一条。

## B-008  进行中  2026-10-16 22:34 北京

- 草稿 PR #18 head `f2ddf45`。没有合并进 main。本地 `make phase1-test`：134 passed，10 deselected。
- 回放打标：`published_at` 不晚于回放时点、但 `first_seen_at` 更晚，标成「后补录历史复盘」，当时未采集，也不把向量算成当时已有。东芝 10-02 发布、10-14 才见到，在 10-02 当天是后补录；到北京 10-15 09:15 已可见，但没有向量时间戳时 `vectors_then` 为假。CPI 的 `first_seen_at` 在 10-15 14:35+08，09:15 的回放仍是后补录。
- `test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。三处缺口仍缺冻结夹具。下一步：感知表写入只在一次性测试库验证。真实补证入库仍停在 `Repository.put_info`。不开始下一条。

## B-008  进行中  2026-10-16 22:24 北京

- 草稿 PR #18 head `bb5fc2f`。没有合并进 main。本地 `make phase1-test`：133 passed，10 deselected。
- 已看到用户批准的导出分支 `data/m8-export` `cd02bdd`。核对后本机临时副本已删除。导出文件没有进入本 PR，也没有进入 main。
- 缺口在 `handoff/M8/source-gaps.md`。能对上标题的有东芝扩产、TDK 磁头、CoreWeave 债券收益率、巴克莱下调 Dell / HPE / NetApp、当天 CPI 同比 3.7% 对预期 3.6%。对不上的有 10-08 FT 约 500 亿美元年化营收、09-19 至 09-21 开盘前的 Muse 榜单、DeepSeek R1 或登顶。2026-09 至 10 月新闻最早 `first_seen_at` 在 2026-10-14，更早的异常日只能标成后补录历史复盘。巴克莱三条和 CPI 的 `first_seen_at` 在 2026-10-15 14:35+08，北京 10-15 09:15 的回放还看不见。
- 合成标题只检查案例方向。10-09 仍不能当作 10-14 之后的二次命中。`test_case_attribution` 和 `test_case_no_news_unexplained` 继续 pending。下一步：等冻结夹具补上这三处缺口后再开案例测试。不开始下一条。

## B-008  进行中  2026-10-16 22:14 北京

- 草稿 PR #18 head `d42b06f`。没有合并进 main。本地 `make phase1-test`：132 passed，10 deselected。迁移在一次性测试库里建表成功。
- 新增 `migrations/phase1_m8_0001_attribution.sql`：回捞、说法、候选、联动事件、三轨、二次命中、冲击分解、系统性标签、标的代码、解释报告。没有 GRANT ingest，没有写共用库。
- 东芝中期走查是合成夹具，不是冻结新闻。候选引用日经扩产，机制为供给。2026-10-06 的 TDK 只做二次命中。生命周期从已发现走到已验证·有影响。报告写明终结原因，并保留未完成的约束项。标的代码为空，因为这条不是估值倍数连带、叙事冲击未变或原因未明。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。不假定 `data/m8-export` 已存在。下一步：把另外三个案例的候选排序接到同一份报告契约上，仍用合成或录音，等冻结新闻再开案例测试。不开始下一条。

## B-008  进行中  2026-10-16 22:09 北京

- 已读 `ops/answers/B-008.md`。草稿 PR #18 head `eaa3dae`，已合入 `origin/main` `c8fee63`。没有合并进 main。本地 `make phase1-test`：130 passed，10 deselected。
- 二次命中要求 `published_at` 晚于异常起点。2026-10-08 和 2026-10-09 对 2026-10-14 的 OpenAI 异常只作背景。负例已写进 `test_second_hit`。M8 v6 第 7.1 节仍写 10-09 做二次命中；`docs/` 和 golden 未改，冲突记在 `handoff/M8/kickoff.md` 第 12 节。
- 缺 EPS 共识或覆盖家数不是「未下修」。缺价格、基本面或联动状态时不生成情绪标签。条件风险报告写「截止日仍未知」、未知项，并且 `operating_impact_proven` 为假。
- 说法抽取和候选生成用录音。广域异常不调用模型。补证真实入库仍停：只打算走 M1 已有的 `Repository.put_info`，没有新增 ingest 写权限，也没有写共用库。`data/m8-export` 尚未按已到仓库处理。
- main 补上的两条 v6 pending 登记，对应测试在本分支已经转绿，合并时没有放回 pending。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。下一步：解释报告把东芝案例走到截止日所需的夹具，以及感知表迁移只在一次性测试库验证。不开始下一条。

## B-008  进行中  2026-10-16 21:59 北京

- 规则切片已推到草稿 PR #18，head `dc78efe`。没有合并。本地 `make phase1-test`：128 passed，10 deselected。
- 新转绿：`test_retrieval_recovers_low_rank_item`、`test_five_dims_rules`、`test_tracks_and_deadline`、`test_divergence_labels`、`test_systemic_event_tag_requires_level12`、`test_unexplained_recheck_5d`、`test_anomaly_contract`。低排序榜单按实体重合进入前 40，并被候选引用。截止日结果按复述第 6 节落入生命周期。只有四级信源时系统性标签为「无」。
- 仍在 pending：`test_case_attribution`、`test_case_no_news_unexplained`。等冻结新闻和录音，不编造现场调用，不连接共用库。
- 下一步：说法抽取、候选生成和解释报告。不开始下一条。不等这条 head 的 CI 才写下一阶段。

## B-008  进行中  2026-10-16 21:44 北京

- 规则切片已推到草稿 PR #18，head `7eb7614`。没有合并。本地 `make phase1-test`：121 passed，10 deselected。
- 已转绿：`test_implied_magnitude_rules`、`test_evidence_scores`、`test_time_alignment_late_news`、`test_candidate_validation`、`test_retrieval_background_window`、`test_embedding_model_isolation`、`test_market_confirmation_four_conditions`、`test_lifecycle_transitions`、`test_second_hit`、`test_search_budget`、`test_verified_not_from_market_evidence`。golden 的隐含幅度和证据分全部命中。阈值在 `config/params/p-2026.10/m8.yaml`。
- 仍在 pending：`test_anomaly_contract`、`test_retrieval_recovers_low_rank_item`、`test_five_dims_rules`、`test_tracks_and_deadline`、`test_divergence_labels`、`test_systemic_event_tag_requires_level12`、`test_unexplained_recheck_5d`、`test_case_attribution`、`test_case_no_news_unexplained`。
- 下一步：继续这些测试和实现。不开始下一条。不等这条 head 的 CI 才写下一阶段。

## B-008  进行中  2026-10-16 21:34 北京

- 草稿 PR #18：https://github.com/XuQingsong/inves-cog/pull/18 ，分支 `phase1/m8-attribution-tracking`，head `bdb5ad8`。复述在 `handoff/M8/kickoff.md`。没有合并。没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- 没有必须停的问题。复述第 6 节按规格执行：截止日结果落入生命周期的方式、`search_daily_budget = 200`、向量只用 `text-embedding-async-v1` / 1536、M7 对象先用已验收夹具。要改写 `ops/answers/B-008.md`。
- D-28：三处都还在，但不改变 M8 要读的已入库关系和篮子 id。`draft_ticker` 的健康标签、多 L2 覆盖、STX/SKHY 硬编码列为 backlog，本模块不改 M6。
- 下一步：先提交失败的 blocking 测试和冻结夹具，再实现。不开始下一条任务。

## B-008  已收到  2026-10-16 21:30 北京

- 任务：M8 建连归因与三轨跟踪。先写开工复述和草稿 PR，分支 `phase1/m8-attribution-tracking`。没有「必须停」就直接开发。
- 依据：`origin/main` `2165c29`；`ops/control.md` 中 B 为「运行」。M8 用 v6。不连共用库，不改 `docs/`、golden、milestones，不合并。M7 尚未进 main，按已验收契约和夹具开发，不把未合并的 M7 实现混进本分支。
- 下一步：读 T08、M8 v6、M7 输出契约和 M6 图谱接口，写 `handoff/M8/kickoff.md`。

## B-007  已完成  2026-10-16 18:08 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `3102373`。没有合并。已合入 `origin/main` `e2c223c`，`MANIFEST.sha256` 和 `CHANGELOG.md` 自动合并，两边都保留。没有改阈值，没有改 M6，没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38885054082 （PR，phase1-blocking，122 passed，12 deselected，33.46s）。同头 push：https://github.com/XuQingsong/inves-cog/actions/runs/38885047902 。本地 `make phase1-test` 同样 122 passed、12 deselected。M7 blocking 12 个，含一致性测试 `test_file_and_database_views_match`。`test_case_detection` 通过。`test_anomaly_live_smoke` 仍等待 R5。
- 差异原因：`marketstate.baskets` 只从 2026-07-01 起。数据库模式用这段短窗口算收益 z，和文件模式 120 日 z 不是同一个数，关注级抢在 `A_linked` 前面；`数据中心电力与散热` 变成 `A_watch`，合并后把数据中心电力从 L3 抬到 L2。另外 `universe` 写死为 `pool`，BAC、LQDA、MMED、PGR、U 被算进池内。现在两种模式都用同一套日线重算篮子。广域只取不在 `config/universe.yaml` 和篮子成员里的 `marketstate.daily`。行业和风格 ETF 只参与轮动。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）四个数不变：非温和查全率 0.9459459459459459（70/74），样本外 0.9512195121951219（39/41），对照日篮子异常 0，平均每天对象 2.327445652173913（2208 个交易日，5139 条）。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。
- 已自行决定：无。
- 下一步：无。不合并。不开始下一条。

## B-007  进行中  2026-10-16 18:06 北京

- 实现已推到 PR #11，head `3102373`（先合入 `origin/main` `e2c223c`，`MANIFEST.sha256` 和 `CHANGELOG.md` 自动合并，两边都保留）。没有改阈值，没有改 M6，没有改 `docs/`、golden、milestones，没有连接或写入共用库。
- 差异原因：`marketstate.baskets` 只从 2026-07-01 起。数据库模式用这段短窗口算收益 z，和文件模式 120 日 z 不是同一个数，关注级抢在 `A_linked` 前面；`数据中心电力与散热` 变成 `A_watch`，合并后把数据中心电力从 L3 抬到 L2。另外 `universe` 写死为 `pool`，BAC、LQDA、MMED、PGR、U 被算进池内。
- 现在两种模式都用同一套日线重算篮子。广域只取不在 `config/universe.yaml` 和篮子成员里的 `marketstate.daily`。行业和风格 ETF 只参与轮动，不当作广域个股。2026-10-14 文件模式仍是 2 条池内（含 `A_linked`，数据中心电力仍是 L3）；补上当日广域日线后，这 5 只是 `universe = wide` 的 L4，池内两条不变。
- 一致性测试：`test_file_and_database_views_match`。本地 `make phase1-test`：122 passed，12 deselected。M7 blocking 12 个，`test_case_detection` 通过。
- AC-M7-07（`--source file`）四个数不变：非温和查全率 0.9459459459459459（70/74），样本外 0.9512195121951219（39/41），对照日篮子异常 0，平均每天对象 2.327445652173913（2208 日，5139 条）。
- 下一步：等这条 head 的 CI。绿了再写已完成，并删除本机 `/tmp/m7-export`。不要重做实现。

## B-007  已收到  2026-10-16 17:40 北京

- 任务：M7 再修。数据库模式和文件模式不一致，违反 Q-M7-8。在 PR #11 上按 `config/universe.yaml` 和篮子成员划分池内 / 广域，查明篮子层差异并消除，加一致性测试，合入最新 main，重跑文件模式 AC-M7-07。
- 依据：`origin/main` `d339bff`；`ops/control.md` 中 B 为「运行」。不改阈值，不改 M6，不连库，不改 `docs/`、golden、milestones，不合并。
- 下一步：读 `data/m7-export` 的 `stored-marketstate/`，对照 2026-10-14 的两种快照。

## B-006  已完成  2026-10-16 17:12 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `b529480`。没有合并。已合入 `origin/main` `3f5d476`，冲突只在 `MANIFEST.sha256` 和 `CHANGELOG.md`，两边都保留。没有改 `docs/`、golden、milestones，没有改 M6，没有连接或写入共用库。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38878632674 （PR，phase1-blocking，109 passed，9 deselected，32.69s）。同头 push：https://github.com/XuQingsong/inves-cog/actions/runs/38878624666 。本地 `make phase1-test` 同样 109 passed、9 deselected。M7 blocking 11 个（含别名测试），`test_case_detection` 通过。`test_anomaly_live_smoke` 仍等待 R5。
- Q-M7-15：路径 B 不再用 4 个百分点分支，`m7.yaml` 已去掉 `path_b_gap`。其余阈值没改。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 2.327（2208 个交易日，5139 条）。四项都过线。
- 别名表：`NAND/DRAM` → `memory`。写在复跑代码和报告 `summary.basket_aliases`。`sector:XLF` 没有改判成 KRE。2026-07-27、07-29 仍未命中，因为当天 2 条和 5 条异常里没有 `basket_id = memory`。2023-03-10、03-13 的 `sector:XLF` 仍未命中。
- AC-M7-03 已按新结果重出，在 `handoff/M7/ac-m7-03.json`。自测在 `handoff/M7/self-test.md`。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。
- 已自行决定：无。
- 下一步：无。不合并。不开始下一条。

## B-006  进行中  2026-10-16 17:10 北京

- 实现已推到 PR #11，head `b529480`（先合入 `origin/main` `3f5d476`，冲突只在 `MANIFEST.sha256` 和 `CHANGELOG.md`，两边都保留）。路径 B 不再用 4 个百分点分支，`m7.yaml` 已去掉 `path_b_gap`。别名表只有 `NAND/DRAM` → `memory`，写在复跑代码和 `handoff/M7/ac-m7-07.json` 的 `summary.basket_aliases`。`sector:XLF` 没有改判。
- 本地 `make phase1-test`：109 passed，9 deselected。M7 blocking 11 个，`test_case_detection` 通过。
- AC-M7-07（`--source file`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 2.327（2208 个交易日，5139 条）。四项都过线。2026-07-27 和 07-29 仍未命中 `basket:NAND/DRAM`：当天 2 条和 5 条异常里没有 `basket_id = memory`。XLF 两天仍未命中。
- 下一步：等这条 head 的 CI。绿了再写已完成，并删除本机 `/tmp/m7-export`。不要重做实现。

## B-006  已收到  2026-10-16 17:00 北京

- 任务：M7 验收修复。在 PR #11 的分支上删除路径 B 的 4 个百分点分支（Q-M7-15，`m7.yaml` 去掉 `path_b_gap`），复跑程序加验证集篮子别名表（至少 `NAND/DRAM` → `memory`，Q-M7-16），合入最新 main，重跑 blocking、`test_case_detection`、`--source file` 的 AC-M7-07 和最近 5 天清单。
- 依据：`origin/main` `3f5d476`；`ops/control.md` 中 B 为「运行」。B-005 验收不通过是因为每天 3.33 个对象。不改别的阈值，不改 M6，不连库，不改 `docs/`、golden、milestones，不合并。
- 下一步：先改 `test_path_b_relative`，让 4 个百分点不再命中，确认测试失败后再改实现。

## B-005  已完成  2026-10-16 14:48 北京

- PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ea089ff`。标题改为「[M7] 提交验收」，已取消草稿。没有合并。没有改 `docs/`、golden、milestones，没有改 M6，没有连接或写入共用库。迁移文件 `migrations/phase1_m7_0001_anomalies.sql` 只在一次性测试库里应用过，共用库留给 A 线在合并后执行。
- CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38863086547 （phase1-blocking，75 passed，9 deselected，31.51s）。本地 `make phase1-test` 同样 75 passed、9 deselected。M7 的 10 个 blocking 测试通过，`test_case_detection` 通过。`test_anomaly_live_smoke` 仍留在 `pending.txt`，等待 R5。
- AC-M7-07（`--source file`，`handoff/M7/ac-m7-07.json`）：非温和查全率 0.9459（70/74），样本外 0.9512（39/41），对照日篮子异常 0，平均每天对象 3.328（2208 个交易日，7349 条）。前三项过线。3.328 高于每天 2.5 的上限。多出来的主要是路径 B 的 4 个百分点分支，约每天 1.3 条只因个股和主 L3 留一收益差达到 4 个百分点、自身涨跌达到 3%。阈值没有下调。
- AC-M7-03：最近 5 个交易日 2026-10-08、10-09、10-12、10-13、10-14 的收盘和盘后清单在 `handoff/M7/ac-m7-03.json`。AC-M7-05：盘后价只从 2026-10-07 起，序列只有 6 个交易日，自身 120 日 z 为空，没有合适的盘后例子，留给 A 线在合并后补。自测逐条写在 `handoff/M7/self-test.md`。
- 已删除：本机 `/tmp/m7-export` 已删除。整份导出没有进入 PR 分支。四个案例窗口留在 `tests/fixtures/phase1/m7/`。
- 已自行决定：无新决定。HDD、CPU、2026-10-14 的收益 z 落在关注级，又和 `|resid_z|≥3` 或路径 B 成员合并，严重级别按规则成为 `alert`，入口仍保留 `A_watch`。这是按冻结阈值改期望，不是改阈值。
- 下一步：无。不合并。不开始下一条。

## B-005  进行中  2026-10-16 13:48 北京

- 测试先红：`8f0f7ed` 提交了失败的 blocking 测试和四个案例窗口夹具。检测代码还没写。

## B-005  已收到  2026-10-16 13:40 北京

- 任务：在 PR #11 上开发 M7。先红后绿。不连库，不执行迁移，不改 M6、`docs/`、golden、milestones，不合并。
- 依据：`origin/main` `344deab`；`ops/control.md` 中 B 为「运行」。M7 v8 已冻结。K01 只计 `close`+`pool` 合并后对象；K02 迁移只授予 `job_runs` 的 INSERT/UPDATE；K03 轮动按答复 A，主题轮动是 `alert`。
- 下一步：读 `data/m7-export` 的 README，先提交失败测试和四个案例夹具。

## B-004  已完成  2026-10-16 13:16 北京

- 草稿 PR #11：https://github.com/XuQingsong/inves-cog/pull/11 ，分支 `phase1/m7-anomaly-detection`，head `ac7c252`。复述在 `handoff/M7/kickoff.md`。没有写实现，没有改 `docs/`、golden、milestones，没有改 M6，没有合并。
- 必须停，等答复后再写代码：
  1. AC-M7-07 每天的异常对象，我倾向只计 `close` 且 `universe = pool`、合并之后的对象。把盘后和广域算进去会超过每天 2.5 个。
  2. `role_perception` 对 `ingest.job_runs` 只有 SELECT。我倾向只给这张表补 INSERT，任务名 `anomaly_detect` 和 `premarket_review`。
  3. 轮动单独命中时的 `severity`。我倾向风格价差 `|z| ≥ 3` 为 `alert`，只有行业极差 ≥ 4 为 `watch`。
- 数据申请（不含凭证，不含新闻；导出放 PR 分支 `handoff/M7/export/`，合并前删除）：
  1. `ingest.bars_daily`：篮子成员加 SPY、QQQ、IWM、RSP、11 只行业 ETF、SMH、IGV、KRE、MTUM、VLUE；列 `ticker, trade_date, open, high, low, close, volume, post_close, adj_factor, source`；2017-01-03 至 2026-10-14。
  2. `ingest.macro_observations`：`VIX_CBOE`、`VIX3M_CBOE`、`VIXCLS`、`DGS2`、`DTWEXBGS`、`DCOILWTICO`；列 `series_id, observation_date, value, units, realtime_start`；同一日期。
  3. `graph.baskets` 全表，成员保留生效区间。
  4. `ingest.issuer_profiles` 的 `ticker, sic`，范围是日线里出现的代码。
  5. `ingest.short_interest`：池内代码，`publish_date` 2018-01-02 至 2026-10-14；缺的不要填 0。
  6. `graph.cluster_suggestions` 有行才导。
- 已自行决定：见复述第 6 节。没有连接工厂或阈值之外的新决定。
- 下一步：停下。不开始实现。

## B-004  已收到  2026-10-16 13:10 北京

- 任务：M7 开工复述。只写 `handoff/M7/kickoff.md`，开草稿 PR，分支 `phase1/m7-anomaly-detection`。提交后停下，不写实现。
- 依据：`origin/main` `4c92710`；`ops/control.md` 中 B 为「运行」。用户已于 2026-10-16 批准开工（G1）。B-003 已通过，PR #8 已合并（`38510bc`）。
- 下一步：读 T07、M7 v7、验证报告、golden 77 个事件，以及 M6 的输出表和 Q-M6-15、Q-M6-18。复述三条路径、数据接口、数据申请和 AC-M7-07 复跑方式。

## B-003  已完成  2026-10-16 12:26 北京

- 已把最新 `origin/main` `b0f5eb1`（含 M3 合并 `9bbf151`）合进 PR #8。head `c144899`。没有合并 PR。
- 冲突只动了三个文件。`pyproject.toml` 依赖取并集，保留 `scipy>=1.14,<2`，其余与 main 相同。`uv lock` 已按这份依赖重算，`uv.lock` 没有变化。`tests/fixtures/phase1/MANIFEST.sha256` 两边条目都保留，Harness `validate_frozen` 通过（162 条，无缺、无多余、无哈希不符）。`tests/harness/CHANGELOG.md` 只追加，M6 `draft.json` 与 M3 `timeline.json` 两行都在。
- blocking：本地 `make phase1-test` 65 passed，7 deselected，1 warning，19.43s，退出码 0。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38850453859 （PR，65 passed / 7 deselected / 22.15s）。push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38850448970 。
- 已自行决定：无。没有改 `docs/`、golden、milestones 里原有内容；main 带进来的文档和 M3 代码原样保留。
- 下一步：无。不开始 M7。

## B-003  已收到  2026-10-16 12:21 北京

- 任务：把最新 `origin/main` 再合进 PR #8。不合并 PR，不改别的文件。
- 依据：`ops/control.md` 中 B 为「运行」。B-003 写明 B-002 第 1–5 项已通过，第 6 项取消。
- 下一步：解决 `pyproject.toml`、`tests/fixtures/phase1/MANIFEST.sha256`、`tests/harness/CHANGELOG.md`，跑 blocking。

## B-002  已完成  2026-10-16 12:21 北京

- 需求方在 B-003 中确认第 1–5 项通过。第 6 项按 Q-M6-20 取消：B 线不写共用库，三天重算改由 A 线在 PR #8 合并后执行。
- 交付仍是 PR #8，head `d5d0587`，CI https://github.com/XuQingsong/inves-cog/actions/runs/38848165567
- 已自行决定：无。

## B-002  阻塞  2026-10-16 11:59 北京

- PR #8，head `d5d0587`。CI 绿：https://github.com/XuQingsong/inves-cog/actions/runs/38848165567 （push 同头：https://github.com/XuQingsong/inves-cog/actions/runs/38848160877）。本地 `make phase1-test`：53 passed，6 deselected，1 warning，19.53s，退出码 0。
- 新增测试：`test_l3_same_as_l2_drops_theme_factor`（相同成员 → `m+s`、`l3_same_as_l2`、`beta_t` 为空；不同 → `m+s+t`）、`test_sic_review_additions`、`test_draft_all_does_not_share_one_connection`（复现原来 3 个线程叠在一条连接上，修完后深度为 1；有连接工厂时每个线程一条新连接）。
- 冲突：`src/inves_cog/llm/transport.py` 按任务名分开保留。`segment_mapping_draft` 仍是 `max_tokens=4096`、`reasoning_effort=low`；`graph_seed_draft` 和 `exposure_draft` 仍是 `8192` 和 `low`。模型名没改。分支已合入 `origin/main` `0035c26`。
- 第 6 项：阻塞：等待数据库连接信息。要重算 2026-10-12、13、14 并写入共用库的 `marketstate`。这台环境到不了 Mac 上的 `127.0.0.1:25432`，现有 `inves_cog_review` 又只能读。需要一份能写 `marketstate`、不写 `ingest` / `fundamentals` / `trading` 的连接，放在未跟踪的 `.env`，不提交。
- 已自行决定：无。没有连接工厂时 `draft_all` 改为串行；命令行传入工厂后才并行，每个线程自己的连接。
- 变更：无新表、无新数据源。因子口径和 SIC 映射按已经写进文档的 Q-M6-18、Q-M6-19。
- 下一步：1–5 已在 PR #8，不合并。等连接到位后只做第 6 项，不重做前面的修复。

## B-002  已收到  2026-10-16 11:40 北京

- 任务：M6 合并前修复（PR #8，分支 `phase1/m6-graph-baskets-marketstate`）。不合并 PR。
- 依据：`origin/main` `0f6371f`；`ops/control.md` 中 B 为「运行」。验收报告有条件通过。
- 下一步：合入 main 并解决 `transport.py`；Q-M6-18 先红后绿；补 `sic_to_etf.yaml`；`draft_all` 每线程一条连接；跑 blocking。第 6 项重算共用库需要可写的 `marketstate` 连接，当前只有一份到不了的只读说明。

## B-001  已完成  2026-10-16 11:08 北京

- `make phase1-test`：在 `origin/main` `273be4a` 上退出码 0。**39 passed**，5 deselected，1 warning，**10.66s**。Python 3.11.17。用的是脚本自带的一次性 docker compose 库，没有连生产库。M6 还在 PR #8，不在这条 main 上，所以这 39 个是 M0–M2 的 blocking，不是 M6 的 11 个。
- 复述：B 线做感知和解释，顺序是 M6 验收后的修复、M7、M8。M7 在每个交易日收盘后发现个股、篮子、行业、大盘的异常，对应目标 A1。M8 给每个异常找候选原因、证据和置信度，对应目标 A2、A3。代码只写 `inves_cog.perception`（含 `graph`）和 `inves_cog.marketstate`；`ingest` 只读，例外只有 M6 文档已经授权的采集。不改 A 线的 `trading`、`valuation_v1`，不改 `docs/`、`golden/`、`milestones.txt`，不合并 PR（用户批准后由需求方合并）。必须停的情况：跨模块表结构或接口、golden、规则 A 或交易行为、新数据源或付费、key 或权限、不可逆删改数据，以及仓库里的定时服务和共用库迁移。一次只做信箱里还没「已完成」的最小编号；`ops/control.md` 里 B 为「暂停」就停。
- PR #8 印象（只读，head `acf4856`，分支 `phase1/m6-graph-baskets-marketstate`，没有改）：价格层在 `inves_cog.marketstate`，按留一篮子、含截距、信号日之前 120 日的 SVD 回归算剩余涨跌，轮动和 v5 警戒分开；图谱在 `inves_cog.perception.graph`，原文切片、无引用就丢、审核日志和已确认视图是分开的。schema 在 `migrations/phase1_m6_0001_graph_marketstate.sql`，授权的采集收在 `ingest/market_structure.py`。main 上这两个包仍只有空 `__init__.py`。风险大的地方：`draft_all` 默认 3 个线程共用一条数据库连接；同一 ticker 有多条 L2 时 `active_baskets` 后写覆盖先写；`draft_ticker` 把所有异常收成 degraded，和「没有年报」分不开；STX 单一业务和 SKHY 四季 TTM 写死在图谱服务里；`handoff/M6/` 里多份证据是单行 JSON，diff 不好看。
- 疑问：这台机器没有生产库 URL 和 API key。本次测试不需要，所以没有停。下次要读共用库或跑 live，需要用户把值给我，我放进未跟踪的 `.env`，不提交。文档和 M6 v6 没有要停下来的疑问。
- 用户决策 UD-B-01：用户说每次做完任务后开启定时任务，监控 `ops/inbox/B/` 里还没完成的任务，有就直接开始开发。打算照做，但只作为这个 agent 的唤醒：每 10 分钟看一次信箱（与 A 线 UD-A-01 同一间隔），仍按 README 第 3 节一次只做一条；B 为「暂停」就什么也不做。不在仓库里加定时服务，不改调度代码。复用同一个定时器，不在每次完成时再挂一个。
- 已自行决定：无。
- 下一步：没有下一条信箱任务。不碰 PR #8，等需求方发 B-002。

## B-001  已收到  2026-10-16 11:02 北京

- 任务：入门（搭环境、读文档、复述）。不写业务代码，不开 PR。
- 依据：当时的 `origin/main` `d4afbaa`；`ops/control.md` 中 B 为「运行」。
- 下一步：读任务书 §4、M6 v6、M7 验证报告、M2 验收报告；跑 `make phase1-test`；读 PR #8。
