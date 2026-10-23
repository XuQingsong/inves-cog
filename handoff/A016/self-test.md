# A016 纸面计划时序及输入完整度

目标：计划在同日 M9 之后运行；评分没完成时等待，截止仍缺则明确不出计划；逐项展示实际输入缺口，保留规则 A。

## 验证

先失败提交 e312d529bd2007014437d08df2e48a908cd76ae1：4 项真实失败，见 red.log；实现后相关 M4/全部ops检查 86 passed、3 deselected（合入 B046 后；其相邻回归另19 passed），见 green.xml。注入时钟、离线固定输入，无模型或来源请求。

| 清单 | 结果与证据 |
|---|---|
| E1 | test_e1_et_window_and_restart：冬夏均 ET08:35 开始、09:05 不发布；旧北京时间窗口不触发。更新原 test_plan_json_contract 的过期时段断言。 |
| E2 | test_e2_only_real_success_before_now_is_ready / test_e2_e4_wait_then_plan_once_across_restart / test_e2_deadline_failure_no_plan_or_duplicate：上一交易日评分须 ok/degraded、真实 ended_at 不晚于当前时间；等待期间无 job/计划，期限写 failed/skipped_upstream。test_e2_outer_worker_does_not_hide_deadline 核外层 worker 不吞掉最终轮询。 |
| E3 | test_e3_e6_actual_plan_unchanged_except_completeness：真实引擎生成非空订单，覆盖层缺失仍出计划；覆盖层存在记录版本及 M8 缺口。test_e3_late_overlay_not_consumed：不使用窗口开始后才生成的覆盖层。 |
| E4 | 持久 job 行查询加会话 advisory lock；同日有任何已尝试记录不重复，JobRunner 先写 running，再写最终状态。重启用相同持久记录亦不重复。 |
| E5 | test_e5_seven_sources_no_empty_insider_proof：按 FR-M4-16 的 sources 列表结构报告七源；缺 VIX 按非恐慌，未知上市/事件采集覆盖与无可证明时间明确 unknown/NULL。沿用 test_plan_unpublished_low_coverage 验证95%原门槛。 |
| E6 | 同一非空输入用未改 prepare/真实引擎生成基线，与 daily_plan 除 input_completeness 外逐项完全相同；无规则 A 修改。 |
| E7 | test_e7_add_only_m9_program_separate_migration：supervisor 原 program 集合仅新增 m9。实际唯一授权迁移已执行、五表初始空、独立投递目录已准备，见 m9-deployment.json。生产 worker 因两个现有角色 NOLOGIN/无 scoped URL 尚未启动，已向需求方明确请求最小登录决定。 |
| E8 | 相关86项通过，B046相邻回归另19项通过，ruff通过；make phase1-test 实际因本机无 Docker 在启动前退出，未冒称全量成功。准确提交 CI 待 PR 运行后补链接；无 M7/M8/M5 源码或合同文件修改。 |

## 部署和限制

生产只执行 phase1_m9_0001_overlay_shadow.sql，SHA256 2b5b1306953b1eaa28463cb507498849cb8db1198dd77d00ba9c66cf6701af94。管理员仅用于本次批准的DDL；role_overlay/role_shadow 都是已有 NOLOGIN 角色，未借用管理员业务运行或擅自更改登录权限。INVES_COG_OVERLAY_DIR 已指向独立生产目录，未与历史导出/迁移目录重叠。M9尚未启动，不能宣称自然发布通过。

代码提交验收与生产安装分开：本PR未合并前不安装M4时序代码。M9已合并代码的迁移可独立推进，登录条件解决后继续仅新增M9进程。M4运行时若窗口已过且评分已就绪，明确报错过窗口，不伪称上游缺失。输入完整度中无原始可见时间的字段不以读取时间冒充；内部人无行不证明采集完整。

初次准确head全量CI的5处旧时段断言失败及修正依据见ci-history.md；没有删除、跳过测试或改门禁。

合入需求方已验收 main384244a（B046 merge6fa657c），调度脚本唯一冲突同时保留M7期限分支和A016的M4自主管理评分门槛；未手改继承的B源码/合同。B046相邻19项实际通过。
