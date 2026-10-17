# A009 自测与独立复验入口

范围仅 ARM 估值专用现金流、TSM 上市 ADS 单位链及 A009 K01 的既有 TTM 降级；继续 PR #17。代码文件的准确内容指纹在 `code-manifest.json`，最终完整 SHA 和对应 CI 在 agent-status 的 A-009 最终回报及本机 manifest。方法 v1.3 → v1.4，仅升级输入合同/存量发布审计，不改权重、估值参数或规则 A。

| 任务要求 | 实现与证据 |
|---|---|
| ARM 正例及缺期、不对齐、未来、币种、PPE 范围负例，先红后绿 | `tests/m2/valuation_cashflow_cases.py`；先提交失败测试，再提交实现，测试名不变。还拒绝对齐流量失败时回用旧年度 FCF。 |
| 同起止/币种/申报的 OCF−纯 PPE，年度+当期YTD−上年同期YTD | `source-audit.json` 列三对真实期间、系数、accession、单位和 USD identity；完整原值/符号/算式仅在本机 `independent-source-formula-checks.json`。目标严格等于财报状态期末；不匹配即记录具体缺期，不用 investing 代理。 |
| 最小 M2 可选 JSON 且旧值/来源/健康不动 | 只为 ARM fixed 追加 `valuation_fcf_ttm` 及同名来源，extract/外国季报组合后更新此可选字段，M5 独立读取。没有迁移或持久化接口变更。59 家旧完整提取输出、3,556 旧状态原字段均逐项相等。 |
| TSM 实际 EPS/股本/价格/PE 单位核实 | 既存 2026-04-16 的20-F（0001628280-26-025362）F-8分别列每股/每等价ADS；该文内每ADS=5普通股。仅接受文档覆盖的2023–2025年度实际EPS，保留原FRED美元换汇链；EPS×5、稀释股数÷5、NYSE美元/ADS价格不变。来源/目标单位、系数、PIT、原来源、重复换算审计均保留。 |
| 历史 PE 当时可见，不能猜 ADS 历史起点 | 该20-F无Accepted精确时刻，证据保守从2026-04-17才可用，不倒灌此前；未证实旧期间排除。历史不足5年继续原L2中位倍数回退，不新增参数。 |
| 预测已ADS/普通股正例，缺单位、未来、重复转换/拆股负例 | `tests/m5/listed_unit_cases.py`。既存Yahoo预测仅美元，无每证券单位，真实NTM仍unknown；按正式K01拒用其EPS NTM及预期增长，实际链齐全时回到FR-M5-05原TTM路径并降低置信度。未知实际EPS/股数/价格链仍不估。没有把未知预测认作已ADS。 |
| 预测降级不继承污染旧值，不顺便刷新 PE | 单位有效性变化进入trigger审计；预测audit由absent→unknown也更新原因，但不改变历史倍数。合成正反例检查已知→未知→恢复；未知预测撤回即清理旧已发布值，不受25%待复核挡住；实际TTM五日三档稳定。 |
| 真实来源独立重算及覆盖 | 10个ARM/TSM逐日源/公式独立检查；五日59行：49/49/49/50/50可估、零异常失败。A008原47/47/47/48/48的类型和三档均不变。`coverage-after.json`含全部剩余字段及具体原因。 |
| 稳定与交易隔离 | 236组相邻日比较、171组无重算可估稳定对照；ARM/TSM五日三档各自恒定。11,494条实际规则A评分一致；五日完整合成计划字节相同，订单13/5/2/0/5。`rule-a-trading-proof.json`列前后hash；不是实际账户/持仓。 |
| 受影响测试和CI | M2/M5受影响28 passed、1 live deselected，离线、无skip，见 `affected.xml`；改动文件Ruff格式/检查通过。最终准确head CI另逐次核对，不把本地成功或旧CI当最终CI。未变的权限/其他公式证据复用A008。 |

复验入口：本机 `/private/tmp/inves-m5-a009/manifest.json`。完整留存重建、源/算式、稳定审计和可复现脚本均在同目录，含逐文件SHA256；使用既存只读角色/本机连接，无采集、外部API、模型调用或写库。公开材料只有代码、合成回归、来源元数据、计数与hash，原始金融包没有上传。

可复现离线测试（项目根目录，已有Python 3.11开发环境）：

```sh
PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 INVES_COG_LIVE=0 python -m pytest tests/m2/test_fundamentals.py tests/m5/test_valuation.py -m 'phase1_blocking or phase1_replay' -q
```

本机完整复验脚本为 `replay-script.py`、`source-audit-script.py`、`trading-proof-script.py`，需要既存原件与项目只读连接；不在外部环境重采资料。原系统取得时间缺失的留存资料仍标unknown/后补录，不把离线重建称为历史实时抓取。

剩余9只沿用A008的源/历史/研究合同限制；真实TSM预测单位尚未知，但已按K01明确降级。没有声称全59家可估、M5整体已验收、真实持仓/调度已部署；不改docs/golden/milestones，不合并PR或部署，自动接单仍暂停。交协调方独立复验。
