# M8 82bacdb：作业记账与行映射独立验收

准确 head `82bacdbb1e0fad8980a973fd0c90d5ab9cbc7f18`；chain blob `e95e694010d3b14cba5426e5afd13d345db3d83a`，Store blob `275842b01efc06d1f7f6930d0170b2c0ee071457`。

**20组真实PG16检查全部通过**，准确冻结迁移、role_perception、tuple_row/dict_row各10组。实际Store.save→新Store.prior恢复条件风险、结案原因、unknowns、history、fundamental/proven；同状态再存可读，两模式无KeyError；无审计的状态变更拒绝，有完整审计允许，不存在事件返回None。

实际run_scheduled→execute_stage→Store.save，用非法日期导致真实SQL失败：全部成功job_runs=ok/processed_count2；一失败一成功则后一条继续，job_runs=ok/processed_count1，返回rows保留失败；全失败抛RuntimeError，job_runs=failed/processed_count0/error_summary非空。返回count2是总行数，不能当成功数；部分失败详情在rows，未增加部分失败必须写error_summary的新门槛。

**连接范围限定**：上述失败恢复采用autocommit=True，与已有ingest入口模式一致；普通事务连接控制中，首个SQL失败令事务中止，记账更新也失败并回滚。源码尚无完整M8生产连接装配，故本次关闭tuple/dict入口和autocommit下失败记账窄项，不声称任意事务模式、真实部署或正式调度通过。协调方后续装配必须明确该约束并实测。

ce2日期函数AST未变，两个起点前写入反例复用、不重做、不关闭。无模型、共享业务写、凭证读取或部署，未改开发源/任务/README/Harness；一次性容器已删除并精确查询包含停止容器的列表为空。

本机review/m8-82bacdb-job-row/保留verify.py、results.json、source/blob差异、迁移哈希及清理证明。准确CI39015396118已独立读取为success；未重跑无变化旧慢失败。

UD-COORD-05要求B在已承诺两项交付后停止并短交接，本次支持两项收口；其余日期、真实输入链、四例/引用、五日全池及M0–M8整体验收由协调方承接，不把交接等同模块通过。不启动M9/M10、合并或部署。
