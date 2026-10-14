# M1/M2 接入与独立数据库状态（2026-10-14）

独立 PostgreSQL 18.6 + pgvector 0.8.6，数据库 inves_cog，端口 15432，本项目独立目录与账号。未连接其他项目数据库；凭据仅在忽略的本地配置中。没有安装开机自启服务。

阿里百炼 Token Plan 的 deepseek-v4.1-flash、glm-5.3 均真实 HTTP 200；不需要另一个对话模型 key。Alpaca SIP/News、SEC_USER_AGENT、FRED、Alpha Vantage 已接通；R7 导出已收到并离线导入。

嵌入已按三项要求实测，详见 v3-embedding-check.json：当前 DASHSCOPE_API_KEY 就是 Token Plan key；Token Plan GET models 为 200、未列 text-embedding-v3，POST embeddings 为 404；同一个 key 在北京与国际 compatible-mode 的 GET models 和 POST embeddings 均 401 invalid_api_key。因此需一个开通规定 text-embedding-v3 的百炼普通 API key；这是 AC-M1-08 非阻塞项，不挡 M1 提交。未把本地未配置地址的探针失败说成网络 401。

CompanyIR 实测 403；Yahoo 在旧客户端与隔离的最新版客户端均实测 getcrumb 403、quoteSummary 429，不能归类为缺 key。未换源或模型。M1 五日回补已达标，真实定时证据今晚产生；M2 真实覆盖和分部证据仍在补齐，各模块自测报告逐条列明。
