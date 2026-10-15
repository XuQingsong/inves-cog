# M2 独立收尾自测

基线：main be2137e；分支 phase1/m2-closeout。按用户要求从 M3 PR #7 拆出，不包含打分代码或迁移，不修改 docs、golden、milestones。

## 范围和提交顺序

先提交 bff60bc：D-17、D-21、继任 CIK 和真实采集耗时的回归测试；在未实现的 main 上实际 4 failed，见 red-tests.xml。之后单独提交实现。原失败提交 77bcacb、6f5e4b2、b39f6bd、31dc1b8 的断言保留，未用 skip 或放宽容差。

| 收尾项 | 结果和唯一最终证据 |
|---|---|
| D-17 | verification.py + extreme_cases.py；原件金额、期间和可见日期逐项匹配才标 extreme_value_verified，错误金额、错误期间继续隔离，legacy 不变。config/fundamental_verifications.json 保存原件 SHA 和 context；extreme-values.json 证明 LITE 恢复可打分。SKHY 已核验季度不等于完整 TTM，其他缺报门禁仍生效。 |
| D-21 | earnings_history.py + tests/m1/history_cases.py；2,392 份 2015 年以来 8-K Item 2.02 全部核对官方索引 Accepted，未核验 0，见 earnings-history.json；坏索引不生成事件，25 份夹具不受旧的最新 20 份限制。 |
| successor CIK | 按截止日最新可见 filing_date、accession 选择，不受数据库返回顺序影响。XOM 旧 34088 → 新 2115436；前身导入 1,580 行，54 份财报事件，官方重组证据见 xom-predecessor.json。 |
| M2 live | m2-live-final.xml：实际 1 passed，0 skipped，1,309.747 秒，处理 59 只；状态 degraded 如实保留来源缺口，不宣称所有来源全绿。已仅删除 test_fundamentals_live_smoke 的 M2 pending 行。 |

真实冒烟输出来自拆分前完整提交 1be5aff12af0434acf49d363d484744e33bf7a92 的实跑；本次原样移动，不伪称重新实跑。live-provenance.json 对本 PR 提取器、服务、客户端集成文件逐一校验字节一致及 SHA。为让真实采集在时限内完成，日常只刷新最新可见 vintage，完整 PIT 重建保留 --rebuild-history；每次仍获取 SEC companyfacts，分部映射独立任务运行，未映射状态不隐瞒。只有 segment_mapping_draft 请求限定输出和思考档，不改其他 LLM 任务。

## 检查

- 4 项原失败回归：4 passed，regression.xml。
- 全仓 blocking：39 passed、5 deselected，9.42 秒，blocking.xml。
- 离线测试不访问网络或系统时钟，LLM 使用测试替身或录音；既有 M0 正反门禁通过。
- 金额 NULL 规则、模型白名单和权限不变；没有扩大数据库权限或连接其他项目数据库。
- 新增非阻塞待办：ASML、TSM 的 stale_fundamentals 尚需纳入 6-K 季度业绩，登记 handoff/M2/backlog.md，期限 M5 提交验收前。

M2 收尾需需求方验收后合并；M3 随后再合入 main，不以当前分支替代上游正式验收。
