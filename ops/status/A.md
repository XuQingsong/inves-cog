# A 线回报

> A 线任务状态；历史明细见各 PR 自测。此文件仅保留协作所需进度与证据链接。

## A-007  进行中  2026-10-16 18:34 北京
- 修复 [PR #16](https://github.com/XuQingsong/inves-cog/pull/16) 待审，head **1c72798fc47c07a2b60e4c071a93d0c836c885ad**；[准确 head 的 CI38887300522](https://github.com/XuQingsong/inves-cog/actions/runs/38887300522) 成功。全仓离线118 passed、v18 90/90，正金额订单对照一致。证据 handoff/ops/A-007/repairs.md；计划证据仅核验统计，不公开账户、持仓和金额明细。
- XOM fixed补1→47个知识日期，14个早期标准营收窗口缺口逐期列因；当前数值与legacy不变，公开SEC来源及摘要在xom-history.json。变更仅任务授权M2来源合并、M4说明及XOM历史修复；无迁移、服务或权限变更。
- M5草稿 [PR #17](https://github.com/XuQingsong/inves-cog/pull/17)，head **1fd65ffe02ac96c45b1866f742deff852363a76d**，handoff/M5/kickoff.md已交；先红后绿继续开发。
- **必须停 K01（仅成长类V1影子分）**：规格§8.8未给95/70/40/10分对应的四个Δg横坐标（百分点），请在ops/answers/A-007.md明确；其余功能继续。详见handoff/M5/questions.md。
- M5拟新增独立三表迁移和m5.yaml，继承既有权限边界，未部署。只读M2 fixed、M4计划/持仓，不读M3；无新数据源或依赖。公开报告不含私有账户数据。
- 下一步：M5失败测试/夹具→实现→逐条AC自测；完成后停止取新任务。无需等待修复PR合并。A-006时间证据由需求方核对，不再手动执行。
- 已自行决定：公开证据保留统计和公开财务输入；旧状态中内部运行元数据删去，历史验证结果保留于下方和对应PR。不改变已完成编号。状态写前尝试pull --rebase，只更新A.md，保留B.md。

## A-007  已收到  2026-10-16 17:49 北京
- 接收main e2c223c78919e4e08222ce7014eb4587560b00a6的A-007：先D-33/D-34独立修复PR，再M5开工及开发。M5完成后本线停下，不取新任务，等待整体检验。
- 中途答复渠道ops/answers/A-007.md；未合并代码不部署、不运行生产迁移、不自动合并PR。

## A-006  已完成  2026-10-16 17:25 北京
- D-32 PR #14、M2正式调度 PR #15由需求方合并；按ops/answers/A-006.md完成授权部署验证。准时运行由需求方明早核对，不再手动执行A-006任务。
- M4 [PR #12](https://github.com/XuQingsong/inves-cog/pull/12)，head459d91ed407e945227e726a84cd3291898afc977，[CI38878686128](https://github.com/XuQingsong/inves-cog/actions/runs/38878686128)绿，114离线通过，v18 90/90。handoff/M4/self-test.md。后由需求方有条件验收并合并d339bfffe4d1db9a0d3d3cc31c2780db5a4bca24，milestones由需求方登记。
- [main47c6e59的CI38878899115](https://github.com/XuQingsong/inves-cog/actions/runs/38878899115)绿。内部部署明细留本地，不再复制到公开状态。

## A-005  已完成  2026-10-16 14:31 北京
- [PR #13](https://github.com/XuQingsong/inves-cog/pull/13)，head8d3aa5a762f564ecfd6263a0dee6c9d9f0bc9241，[CI38861471796](https://github.com/XuQingsong/inves-cog/actions/runs/38861471796)绿；89blocking，调度合同先11failed后11passed。
- 价格结构历史补算、分钟缺窗真实复核、调度注册交付；handoff/ops/A-005/self-test.md。部署与入口修复由A-006承接，已完成。

## A-004  已完成  2026-10-16 13:35 北京
- M4开工复述PR #12，head e55361d5ec8ad5a7c827dd7a81102afd11427af9，[CI38856417633](https://github.com/XuQingsong/inves-cog/actions/runs/38856417633)绿；仅kickoff，源码参照32条，三项必须停问题后经需求方答复。
- 已合并代码的授权服务切换完成；A-003遗留时间证据交需求方。handoff/M4/kickoff.md。

## A-003  已完成  2026-10-16 13:20 北京
- 修复[PR #10](https://github.com/XuQingsong/inves-cog/pull/10)，head481e0248944f5791cabdc111d681afed619e51bc，[CI38852874067](https://github.com/XuQingsong/inves-cog/actions/runs/38852874067)绿；64blocking+2replay，规则A600行16200字段零差异。
- D-27 UNH成本口径、D-26 SEC异常隔离/游标、D-22健康复核及用量统计完成；handoff/M1/a003-self-test.md。需求方合并61a97e139d80c1b43b4a5a72b30c7f2fa678483a。真实时间证据已按A-004授权例外交需求方，A不重复运行。

## A-002  已完成  2026-10-16 11:35 北京
- [PR #7](https://github.com/XuQingsong/inves-cog/pull/7)，head2c93b5af2630e0d49ad3703a0239c63cff091735，[CI38845929760](https://github.com/XuQingsong/inves-cog/actions/runs/38845929760)绿。M3源码注释21项映射完整；代码AST不变，600行16200字段回放零差异。handoff/M3/a002-comment-only.json、self-test.md。

## A-001  已完成  2026-10-16 11:13 北京
- PR #7合入当时最新main，head73a25d03505513c1ce28c703d5abb9cf067a77b2，[CI38844008192](https://github.com/XuQingsong/inves-cog/actions/runs/38844008192)绿。仅A线，B线PR保持不动；未自动合并。
- 用户决策UD-A-01：从GitHub信箱取任务，复用一个本线程自动化每10分钟检查；有任务按协议接收/执行/回报，无任务或暂停则安静结束。已先登记再启用，未重复创建。
