# 首次实际M8来源消费：部分完成

只证明已生成的2026-10-15快照可以交给M9消费；**A5五日尚未完成**。

源代码04631bbf5e8c3aaadbf978427754188dcb101a72，M9消费代码39291661d7c48d56e40bebceddf9bf963978b620（后续提交仅继承集成及补充证据）。本机私有导出时间2026-10-22 16:24:59.641219 UTC，原生 `read_replay_snapshot` 读取现有role_perception的本项目只读事务。用户已在原对话明确批准跨端私有快照导出及M9离线验证，UD-A-33已先推送状态。

消费直接调用M9生产 `generate_overlay` 与 `validate_payload`，不手抄模型事件、不修改provider的缺项或complete。它没有运行生产M9 scoped-shadow CLI/服务，不能替代生产账号/目录接线验收。模型调用0、数据库写0、实时投递未触碰；本机输出仅为私有0600的replay_overlay_*封装。仓库内JSON只有计数、代码SHA和文件哈希，没有事件正文、密钥、页面或持仓。

| 日期 | 真实M8快照 | 实际M9结果 |
|---|---|---|
| 10-15 | id=1，complete，2事件；实际生成15:58:21.254641 UTC，历史source_asof=10-16 04:30 UTC | 1标的，off=1，on=0，unknown=0 |
| 10-16 | 无 | unavailable，overlay=null |
| 10-19 | 无；M8未执行到该日 | unavailable，不能拿M7异常0冒充M8空日已完成 |
| 10-20 | 无 | unavailable，overlay=null |
| 10-21 | 无 | unavailable，overlay=null |

原M8一次执行从15:41:06.173412至16:25:36.230231 UTC，因A包装2670秒期限停止，逻辑17/HTTP19，单位已退出/MainPID=0。16次任务返回，第17被期限中断；用量回执16 ok、2 failed（既定重试）、1 failed_usage_missing。中断请求费用未知，不能记作零。实际候选分析响应7–9分钟，A整批45分钟期限估计不足；不是服务器IO或B043 loader再次失败。原生MemoryStore/Recording未逐次持久化，因此没有宣称可无损恢复10-16，亦未重启付费批次。

恢复需要先明确保留首日、剩余日期的跨日状态及持久断点的原生路径，再核准确新增调用上限。已在[原PR45直接请求需求方核定](https://github.com/XuQingsong/inves-cog/pull/45#issuecomment-6345811944)；A不代改M8或自行扩费。五日实际来源齐备后再完成A5，其余A1–A4、代码回归与CI独立推进。
