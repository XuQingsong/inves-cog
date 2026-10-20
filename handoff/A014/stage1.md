# A014 第一段：早上页面轮询登记

本段只交付代码登记，尚未安装服务、连接服务器、调用模型、补跑或迁移数据库。部署目标仍为43.166.2.31；Mac不是部署目标。

- 基于main cf17d7359e2db33b589b2e84c56da1776f1857ea，分支phase1/a014-deploy-server。先失败测试6f94a6b（10失败、10原有通过，red.xml），后实现；不改perception、估值、计划、docs、golden、milestones或表结构。
- scripts/schedule_morning_page.py每30秒轮询，通过注入Clock及原job_slot认定分钟，并使用相同美东交易日规则。夏令时北京09:15、冬令时10:15；非该分钟不读私有环境、不调用命令、不写页。不加--at、不补错过的运行。
- 新程序morning_page登记到原Supervisor配置，autostart/autorestart=true；原scheduler/daily_modules/financials/watchdog/embedding和Darwin专属awake均保留。配置environment仍只有PYTHONUNBUFFERED，未写任何私有环境值或正文。
- 在.harness/service/按北京日期/分钟先原子创建attempt文件，然后调用原早上命令。退出0或1都保留记录；同分钟轮询、重启或多进程竞争都不再次调用。自行决定：先持久化占位以保证最多一次；进程在占位后意外退出也不在同一分钟重试，符合“不重复尝试”的限制。文件只记状态、日期/分钟、退出码或错误类型。
- 调用前复用read_environment读取仓库私有.env并传入子进程环境，进程变量仍按原规则优先。INVES_COG_PAGE_DIR若没设置，默认仓库旁的daily-pages；若指向仓库内（包括解析后的链接）则拒绝，不调用早上命令。子进程stdout/stderr不进入服务日志；wrapper只记录脱敏状态和错误类型。
- 对应验收1：同一测试覆盖Linux和Darwin，既有命令/awake保留、新程序自启和自动拉起、environment无秘密。验收2：到点前/后、冬令时旧时刻、周末均无调用。验收3：夏令时首次、同分钟和重启去重、次日再调用。验收4：冬令时只有10:15调用。验收5：退出1也不重试。另核对环境只传子进程、页目录在仓库外、私密值不写attempt/输出。
- 最终本机tests/ops及导入/时钟/模型门禁 **32 passed**，stage1-tests.xml；Ruff通过。按任务执行make phase1-test，本机无Docker，入口明确退出；不安装Docker、不跳过门禁。原GitHub CI会在干净Docker里执行同一个make phase1-test，结果以PR准确head为准，链接写PR/status。
- 第一段交PR后停在“进行中”。只有需求方合并且下次唤醒确认origin/main包含本次代码后，才进入43.166.2.31安装/私有库迁移检查/一次10月19日页面补跑/加密交付第二段；本次未登录或变更任何机器的服务。
