# inves-cog 项目记忆（需求方/协调者用）

## 系统
美股市场感知 + 纸面交易系统，两个模块严格分开、互相提供依据：
- 模块一（感知）：基本面、新闻、情绪、资金、价格结构、异动、归因、复盘。
- 模块二（估值与纸面交易）：规则 A 打分、估值、仓位、风控、纸面执行与计划。
页面层（`src/inves_cog/web/`）只格式化上游结果，不重算交易规则；缺数据必须明示，不能显示成“无风险/空仓”。

## 协作
- 线：A（Codex，交易/估值/运维部署）、B（Cursor，感知/页面）、C（设计，Figma 额度已用完）。规则见 `ops/README.md`；任务 `ops/inbox/<线>/`，验收与关单 `ops/answers/`，状态在 `agent-status` 分支 `ops/status/`。
- 一条线同时只挂一个任务；需求方验收后在 answers 末尾写“已关单”。
- 合并：需求方验收通过（代码复核 + 准确 head CI 通过）后直接合并，不再等用户说“合并”（用户 2026-10-26 授权），事后报告。
- 部署：合并后在 `ops/answers/A-014.md` 追加“续十四补充N：部署 …（运维）”交给 A，A 回报后需求方线上走查。
- 本机 `gh` 已登录，可直接推送/合并/查 CI（`export PATH=/opt/homebrew/bin:$PATH`）。

## 环境
- 服务器 `claude-ubuntu`（43.166.2.31），代码 `/home/claudeuser/inves-cog`，数据 `/home/claudeuser/inves-cog-data`，网站 http://43.166.2.31:8080/
- 生产 venv 没有 pytest，不要往里装。完整测试：服务器 `/home/claudeuser/b062-preview` 下用 docker 镜像 `inves-cog-harness-b062` 跑 `make phase1-test`；汇总行全过即可，最后的 EXIT 2 是清理 docker 网络失败，已知问题。CI 必过检查：`phase1-blocking`。
- 页面走查必须用生产数据渲染分支代码：服务器 `/tmp/b074chk` 检出分支后运行 `/tmp/b074_start.sh`（127.0.0.1:8092，读生产只读库），本机 `ssh -f -N -L 8092:127.0.0.1:8092 claude-ubuntu`，用 `~/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium --headless=new --virtual-time-budget=10000 --screenshot=...` 截图。SWE-2 自报的截图多次是旧页面，需自己核对。
- 页面截图工具：`/tmp/b062render/`（render.py + shoot.sh），原型 `docs/phase1/design/prototype/index.html`（定稿规格）。

## 规则 A 卖出规则适用范围（页面不得画不适用的线）
观察波段仓：只有波段止盈/止损。进攻层：灾难止损、翻倍分批止盈、破位减仓、基本面清仓。标准层：破位减仓、警戒减仓、基本面清仓。防守层：破位减仓、基本面清仓。各核心层有波段股数时加波段部分止盈。止盈提示不算风险。

## 页面禁用
下单按钮、目标价/合理价、“实时”、内部编号（M9、N1、dev50、参数名、None）。

## 用户决定（2026-10-31）
- A 线停用：所有开发与部署都交给 SWE-2（sidekick），需求方复核合并后由 SWE-2 部署、留证据于服务器 `ops/swe2-*.txt`。
- 板块异常门槛维持平时波动的 3 倍。
- 一期第 2 批：B-072 财报卡片已上线；B-073 页面改版已上线（`fb3927d`）；B-074 页面第二轮已上线（个股页 `ca4d57f`、首页 `4ef67ce`）；下一单 B-075 三面原因判断。

## 当前状态（2026-10-26）
- B-062 投资者页面改版：PR #79 已合并（`8c10f8f`），785 项测试通过；已交 A 部署（A-014 补充三十三）。待 A 回报后线上走查，通过即关单。
- A-022 新闻分级：已上线，等首个美东交易日的分级与费用回报后关单。
- 待讨论：GOOGL 同时出现“计划加仓”和“再 1 天破位减仓”的矛盾信号；空头数据结算日晚于页面日期；资金流数据源；主动推送。
- 完整历史：`~/.local/share/devin/cli/summaries/history_378d2be3d17248a8.md`

## 部署与核对规则（2026-11-01 事故后）
- 部署禁止 `supervisorctl update`；只 `reread` 后 `add`/`restart` 指定程序；证据须列出部署前后全部程序清单（当前 22 个）。2026-11-01 因重生成配置漏掉 pages/review/live_perception，网站停机约 7 小时。
- 页面截图前先在同一台机器 curl 确认 200；截完必须打开图片确认内容（SWE-2 多次交回报错页/空页）。晴雨表截图用 `/barometer?static`。
- 二期状态：数据采集（flows）、历史回补、回测框架、晴雨表计算与页面（/barometer，首页市场结论）均已上线（main 682e0b6）。下一步：v19 对照回测与影子运行；OCC 恢复后补跑 `job=occ`。
