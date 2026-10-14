# M1 配置与独立数据库检查（2026-10-14）

这是一份接入状态报告，不是模块验收报告。M1/M2 尚未完成，不将最小接入探针当成连续五个交易日或全标的验收证据。

## 独立数据库

- 实例仅用于本项目；独立数据目录 `.harness/local-postgres/data`、独立端口 `127.0.0.1:15432`；数据库名 `inves_cog`。
- 本机 Postgres.app 的 PostgreSQL 18.6、pgvector 0.8.6。CI 的锁定 PostgreSQL 16/pgvector 0.8.7 配置保持原样。
- 已执行 M0、M1 两个迁移共三个 SQL 文件，`ingest` 有 15 张表；应用账号 `inves_cog_ingest` 只获得 `role_ingest`。
- 已验证应用账号真实登录和读取 `ingest.source_health`；其他项目的数据库没有连接或修改。
- 管理入口：`python scripts/local_database.py start|status|stop`。启动入口可重复执行当前仓库迁移；本次没有设置系统开机自启。
- 连接凭据已写入本地 `.env`；管理员凭据和原配置备份位于忽略目录，目录 0700、凭据文件和 `.env` 0600。没有密钥、口令或数据库文件进入 Git。

## 已取得的真实接入证据

| 来源 | 探针与结果 | 证明范围 |
|---|---|---|
| Alpaca SIP | HTTP 200，AAPL 两根历史日线 | 已提供账号能取到指定 SIP 历史数据；不是 73 只完整覆盖 |
| Alpaca News | HTTP 200，1 条新闻 | 新闻接口接通；不是 90 天回补完成 |
| SEC | HTTP 200，AAPL submissions 1,001 条；三个索引 Accepted 核对 | 已按需求方 K17 答复用索引 Accepted，三个实源样例断言通过 |
| Alpha Vantage | HTTP 200，日历 4,588 行 | 未来财报日历接口接通；没有将其当成历史发布时间 |
| FRED | 修正后 HTTP 200，DEXUSEU 5 个日期的历史观察 | 汇率 key 可用；2026-01-01 的 `.` 为来源无报价，不能归因于缺 key |
| 简单 LLM | Token Plan HTTP 200，deepseek-v4.1-flash，返回含 entities 的 JSON | 使用需求方给的 key 和地址；共享客户端已接通 |
| 复杂 LLM | Token Plan HTTP 200，glm-5.3，返回 graph_node_ids、reason | 困难任务实际路由到批准模型；没有使用其他模型 |
| 嵌入 | 同一 Token Plan 地址请求 text-embedding-v3/1024 返回 HTTP 404：Model not exist | 此端点目前不能提供规定嵌入；需要可提供此模型的 DashScope 接入信息，不自行换模型 |

两个 LLM 的服务商/接入方式已由用户明确确认，不再要求更换 LLM key。模型选择始终由固定 registry 决定；普通任务超时 120 秒、最多 3 次，困难任务 900 秒、1 次。模型探针只含合成连接文本，不上传研究数据。单元测试只回放冻结录音，没有用真实 key 或联网。

FRED 的首次失败为 HTTP 400：注入 Clock 的 UTC 日期为 2026-10-14，而接口报告当天为 2026-10-13。实现现在用 series 元数据返回的 `realtime_end` 与注入日期取较早者，同时取完全部 vintage 分页，不猜固定时差；已先提交失败断言再修正，并用真源重新核对成功。

SEC 的三个真源 JSON 字面值与索引 Accepted 不同（夏令时相差 8 小时、冬令时 10 小时）。用户已确认索引 Accepted 为权威：索引的美东时间转 UTC，JSON 字符串原样留证据；索引缺失时原始申报仍保留，并记录 URL、错误类别、HTTP 状态和待重试缺口，不生成未经核实的财报反应日。没有写死 8/10 小时的修正，也没有改 golden。修复前的红灯已保留在提交历史，修复后完整离线门禁恢复为 24 项通过。

## 仍缺的接入配置

1. 可提供 `text-embedding-v3` 1024 维的 DashScope API key 和匹配的地区/业务空间地址（`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`）。当前填入的 key 与 Token Plan LLM key 相同，现有端点实测返回 404；不把“key 字段非空”当成嵌入可用。
2. Google CSE 的 `GOOGLE_CSE_API_KEY`、`GOOGLE_CSE_CX`，供后续 M8 使用。
3. Tavily/Exa 字段已填，尚未发送探针；它们不属于本次 M1/M2 开发范围，不声明已验证。

## 开发状态

- M0：已验收和合并。
- M1：核心行情/信息契约、共享 SEC/LLM、迁移、配置和持久化基础已有实现；最新完整离线门禁 24 项通过。SEC 真源时间冲突已按用户答复修复。运行入口、定时任务、完整采集链与连续五日证据仍未完成。
- M2：17 个测试已登记并先提交，30 份 Muse 输入和 90 份独立 oracle 已冻结；主体提取器、分部、共识导入/派生、档案和中期 checkpoint 尚未完成。收到汇率方案答复不等于这些实现已经交付。
- PR #3/#4 仍为草稿，不改标题为提交验收；不改 docs 或 milestones。
