# A017 公网只读页面入口

独立入口 `inves_cog.web.public` 包装已合并的 B048 API，不改业务页读取/计算。`scripts/serve_pages.py` 读取私有 env，仅接受 WEB 专用连接；uvicorn 单 worker、0.0.0.0:8080，不信任转发头、不记录访问 URL/异常正文。只追加其 configuration 返回的 pages program，不重写已有 supervisor 配置。

先失败提交 d70a496：6 项失败见 red.log。实现后本地 7 passed、1 deselected，ruff通过；green.xml 的 deselected 是需一次性数据库的市场页逐字段透传测试，待清洁 CI，不能当本地已通过。

| 要求 | 证据 |
|---|---|
| 非 GET 405 | test_a017_only_get_no_docs_or_other_paths；含HEAD/OPTIONS，Allow=GET |
| 文档及非页面路径404 | 同上，/docs、/redoc、/openapi.json与非页面路径；底层文档路由亦移除 |
| 每IP60次/分钟 | test_a017_per_ip_60_per_minute_ignores_forwarded_headers、test_a017_rate_limit_is_separate_for_socket_ips；注入单调时钟、实际socket IP，不信任X-Forwarded-For；到期恢复，活跃客户端容量有界 |
| 错误脱敏 | test_a017_error_hides_exception_and_connection_string；包含假连接串的异常只返回通用503，不输出栈/账号/SQL |
| 首页路径 | test_a017_exact_home_alias_and_upstream_payload；/api/pages/?date=…与原/home等价 |
| 市场页保持原数据 | test_a017_public_market_is_original_payload_without_trading_fields；复用B048一次性真实形态数据库夹具，逐字段比对包装前后JSON，递归禁止交易字段；待CI |
| 只新增pages程序 | test_a017_service_only_web_single_worker_and_no_secret、test_a017_uvicorn_single_worker_direct_ip_and_no_access_logging；现有安装器/业务API未改 |

## 运维依赖

requirements-pages.txt 固定 uvicorn0.38.0/click8.1.8/h11 0.16.0 的wheel哈希（h11与业务锁版本一致），仅Linux/Python3.11页面运行环境使用，不升级业务uv.lock。固定包已从公开PyPI下载，Python3.11经uv离线解析三包、哈希安装到临时target并实际运行 `python -m uvicorn --version` 成功。uvicorn参数依据官方 https://uvicorn.dev/settings/ 与 https://uvicorn.dev/deployment/。

尝试将uvicorn放入全项目ops extra的锁定受既有curl-cffi索引超时阻塞，先停止原重试，再系统TLS/10秒无重试核实仍timeout；没有声称成功或无限重试。故用独立带哈希的页面运维依赖，不修改主锁/其他依赖。临时打包工具Python3.9不支持click8.3，固定支持的8.1.8；最终使用目标Python3.11离线解析与验证，不把3.9失败当生产成功。

## 尚未启动与必须由用户完成的条件

服务器最近只读预检：role_web/role_overlay/role_shadow均NOLOGIN、三个scoped URL缺失；8080无监听，uvicorn未安装。没有启页面/M9或借其他业务账号/管理员运行。需要用户直接允许三个既有角色LOGIN、独立随机密码仅存服务器私有env；不新增角色或扩大表权限。用户还须在服务器防火墙/云安全组放行TCP8080（由root/云控制台执行，A不操作）。

合并后才安装入口与运行依赖；仅新增pages进程。用role_web实际身份检查default_transaction_read_only和输入SELECT权限。先loopback验证，再外部GET http://43.166.2.31:8080/api/pages/?date=…，只报告状态码、是否含计数、RSS；页面明文/持仓/DSN不入Git或聊天。未完成身份/公网验证前不能称上线成功。M9迁移/目录复用已有证据，不重复。
