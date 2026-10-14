# M1/M2 接入和独立数据库状态（2026-10-14）

两个模块的业务实现、运行入口和离线验证已完成；完整真实验收尚未完成，详见 self-test.md。

独立 PostgreSQL 18.6 + pgvector 0.8.6，数据库 inves_cog，端口 15432；本项目独立目录和账号，ingest 17 张表、fundamentals 8 张表。没有连接其他项目数据库。凭据在忽略的 .env/本地目录中，未提交；CI 原定 PostgreSQL/pgvector 配置未改。本次未设置开机自启。

两个对话模型均使用用户指定的阿里百炼 Token Plan，deepseek-v4.1-flash 和 glm-5.3 已分别真实返回 HTTP 200；无需再提供对话 LLM key。FRED、Alpaca SIP/News、SEC、Alpha Vantage 已接通。真实采集得到 73 个行情代码、1,302 个广域诊断入选、60,509 条新闻累计及六系列 73,384 个 FRED 历史版本；统计和限制见 database-summary.json、self-test.md。M2 的 EUR/TWD/KRW 历史汇率已实测；无汇率时抛具体 FXGap，不能以 NULL 隐藏缺口。

仍未接通的是嵌入：Token Plan 对 text-embedding-v3/1024 返回 404；已有 DASHSCOPE_API_KEY 在 https://dashscope.aliyuncs.com/compatible-mode/v1 返回 401 invalid_api_key。缺的是拥有规定嵌入权限的 key 及其匹配地区/业务空间端点，不是缺两个 LLM 的 key。未采用其他模型。

CompanyIR 网站请求返回 403，健康记录明确为未接通；没有绕过限制或切换数据源。Google CSE 配置缺口属于后续 M8；Tavily/Exa 字段已填，未将它们列为 M1/M2 验收通过证据。

M1 blocking 24 项、M2 blocking 25 项，临时联合 blocking 39 项均通过；Muse 90 组/2,255 字段 legacy 差异 0。M2 干净环境 CI 仍需 M1 的已授权 M0 迁移清单修复进入 main 后重跑。连续五日、59 只真实财报与54只分部原文抽查仍未形成，两个 PR 保持草稿，不改 milestones。
