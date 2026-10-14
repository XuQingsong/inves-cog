# M1 第二轮进度

基线main 3e9df18，M1 v6；PR #3保持草稿。已先提交失败测试，再提交源隔离、RSS、异常记录和短正文归并实现。

|任务卡顺序|状态|证据|
|---|---|---|
|1 嵌入|仅使用用户指定的现有key；普通模型GET /models实测401，不再索要其他key；尚未达成真实嵌入|embedding-key-check.json，未输出key|
|2 官网|5站实际采集成功；坏1站时其余4站继续，逐URL健康|public-sources.json|
|3 Trends|关键词隔离正反测试通过，超时不把整个源标未接通|原test_trends_unavailable_marked|
|4 Fed/EIA RSS|实际20/12/16条入库，三个源均level1|public-sources.json|
|5 异常原因|实体/字段/嵌入失败均记类型与消息|原test_llm_extraction_failure_degrades|
|6 短正文根|原错误结论已撤回；<300字符加入标题，生产修正前保存回滚备份|source-root-repair.json|
|7 LLM用量|开发中|待迁移和共享客户端自动记录|
|8 新闻分级|开发中|待最近7交易日实测和冻结重要新闻|
|9 代码规范门禁|开发中|待Ruff改动文件检查及豁免清单|
|10 按时调度|等待2026-10-15北京08:20–08:45；08:50一次核对只收证据，不转正式|正式job_runs，不能提前算通过|

M2六项实现遵照任务卡等待M1验收合并后开始；已仅同步main需求。旧版证据将按§4.6保留在Git历史，最终每条AC只留一份。
