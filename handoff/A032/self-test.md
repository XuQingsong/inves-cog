# A-032 自验与部署交接

守护代码 `33fe469198562f39097f7e44e7c96a279bacb4a2` 的完整 [phase1-blocking CI 实际成功](https://github.com/XuQingsong/inves-cog/actions/runs/42281630905/job/128111816423)。后续预览和材料提交仍需自己的准确 head CI，不借用此结果。

当前为草稿开发交付，未验收、未迁移、未安装、未发真实邮件。FINRA 来源已按 UD-A-59 获批；历史晴雨表事后修订接口已获UD-A-60授权并实现，其余实现已继续完成。不会覆盖原读数或把迟到数据伪称历史当时可见。

|自验|实际结果与证据|
|---|---|
|T1 清单|59项，逐项见 deadlines.md。代码调度及只读到位汇总见 evidence/catalog.json、probe.json。部分历史 flows 来源只有估计发布时间且无连续日常生产者，缺少实际到位分布，明确未全部满足验证要求。|
|T2 事故回放|evidence/performance-33fe4691.json 为当前库按11/03–06日期分类，四日查询均无错误，检出7/6/7/8项；11/05跨资产（含10Y/MOVE/HYG/IEF）与空头成交量仍缺。已补齐的 VIX/OCC 不能用现库伪造原缺失，另用运维修复记录重建，见 incident-reconstruction.json、公开奖录哈希。VIX原读数16.61与补后28.18的缓存不一致检查通过。SOXX已确认3:1拆股，按任务§1正确豁免；无公司行动的对照触发suspect，T2要求必报异常与事实冲突，需需求方纠正预期。没有原始补前数据库快照，不能证明完整历史可见性或全部检出均非误报。|
|T3 补数|tests/dataguard/test_recovery.py、test_runtime.py、test_receipts.py：串行锁、存活旧job不重启、递增间隔、重试耗尽、资源告警/未知暂停、实际复核、下游失败不称修复。UD-A-60修订入口已实现，另存新ops表、实际修订时间和输入哈希；原读数不变。生产自动补数尚未启用。|
|T4 邮件|真实本地Unix假SMTP经STARTTLS、认证、MIME发送通过；数据库队列测试由CI真实Postgres验证合并/去重/结论。应用队列与稳定Message-ID抑制重复；SMTP确认丢失情况下不能承诺网络端绝对一次。未配置明确显示，失败递增重试。无真实外发。|
|T5 页面|服务器只读分支预览，Mac浏览器截图；截图前HTTP200，截图后人工打开核验。data-status.png、home.png；账户信息服务器侧隐藏。预览并非生产安装。|
|T6 性能|准确代码33fe469198562f39097f7e44e7c96a279bacb4a2，59项0.904秒、进程峰值66.5MB，全部记录查询EXPLAIN无Seq Scan/无计划错误，非管理员只读登录。证据performance-33fe4691.json；包含四次有界回放峰值，不冒称连续24小时常驻观察。|
|T7 安全|SMTP只从服务器600权限环境文件读取；日志仅错误类型/状态码/过滤行数，不输出响应、连接串、密码或私有页面。假证书/假口令仅测试临时生成。|
|T8 部署|见下方；尚未执行。|

本地专项实际86 passed（守护纯策略、真实假SMTP、服务配置回归），仓库check_style通过。完整数据库迁移/队列测试由准确提交CI验证，CI状态另附；不能用本地无Docker测试替代。先失败测试历史保留。没有修改B线perception逻辑、旧ingest采集业务逻辑、docs/golden/milestones或交易规则。

## 合并后部署步骤（未执行）

1. 核对需求方验收与合并，确认生产main包含准确交付提交，先核对未提交文件和当前全部Supervisor程序，保存前后清单，不重跑A030迁移或补算。
2. 只安装 migrations/phase2_ops_0001_data_guard.sql：新ops缺口/审计/通知/运行状态/晴雨表修订表与最小既有角色ACL；不新建业务角色、不以管理员运行业务。
3. scripts/install_data_guard.py --prepare-env --write-config 只追加data_guard，拒绝未合并来源，保留其他程序字节；禁止supervisorctl update。随后reread、add data_guard，只restart pages。独立核对所有原程序及PID状态。
4. 默认detect_only=true、INVES_DATAGUARD_BACKFILL=0，首24小时硬门槛。由需求方核对误报后明确决定改为1，程序每轮重读，不自行开启。
5. 服务器owner-only文件 /home/claudeuser/inves-cog-data/dataguard.env 配置 INVES_SMTP_HOST=smtp.gmail.com、INVES_SMTP_PORT=587、INVES_SMTP_USER、INVES_SMTP_PASSWORD、INVES_SMTP_FROM、INVES_ALERT_TO。账号启用两步验证和应用专用密码；此文件不进Git、不回显、不记入证据，真实发送前再完成安全配置。
6. 启动后独立核验首轮实际缺口入库、页面时间与邮件配置状态，跟踪首日只检测及日报真实结果；不把进程存活当业务成功。未配置邮件时检测仍可用，主动邮件尚不可用。

## 尚未收口的边界

- UD-A-60已落实：dataguard.restatement复用原计算器，仅在独立只读视图中按观察日期对齐每日来源；源时间字段不改。每周/月度仍沿用实际发布日期，不臆造发布时间。
- 需求方须解决SOXX T2预期与已证实公司行动的冲突。
- 部分来源实际日常发布时间分布不足，T1不能标为全通过；首次只检测可暴露误报，不能以此替代既定验收。
- 生产安装、真实补数、真实邮件、24小时观察均未执行，不计入开发验证完成。

## UD-A-60 历史修订补充（2026-11-07）

用户已直接答复“允许”。失败优先提交3fd9571d后实现：新增ops.barometer_revisions，按日期与输入哈希去重，实际revised_at与输入来源行哈希保存；仅role_ingest SELECT/INSERT、role_web SELECT，无业务角色UPDATE/DELETE。补数下游调用该入口，不写flows.barometer_daily；原图表保留原值，另列事后修订恐慌/贪婪与北京时间。缺输入修订不当成修复成功，守护复核最新修订并检查VIX缓存差异。

计算视图仅允许五类原计算器SELECT查询，最多550日/每查询50000行；观察日期不得晚于目标日，采集/发布不得晚于实际修订时间，CFTC发布日期不得晚于目标日。不导入目标日之后的市场观察；修订明确非PIT，不向历史交易读取路径供数。bars原表无采集时间列，证据只能证明本次修订读取到的当前数据，不能证明历史可见性。每周/月度晚到数据不能假定原发布日期，仍可能保留缺失；未放宽成功标准。

新增test_restatement.py实际运行原计算器的非空多来源夹具，VIX28.18、每日PC0.7进入目标日；离线守护54项通过。扩展本地服务回归合计90 passed；另3项新闻窗口数据库测试因本机无Docker报环境错误，不冒称通过，连同新表权限/去重/原值保留/迟到数据时间测试交准确head CI真实Postgres核验。当前生产未迁移，新修订区尚无真实运行数据；原页面截图和性能证据保留原代码head，不冒称已覆盖新增表查询，新增查询在CI核验。
