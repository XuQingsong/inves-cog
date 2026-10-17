来源：需求方已核实的 [A008 K01 盘点](https://github.com/XuQingsong/inves-cog/blob/main/docs/phase1/acceptance/M5-input-coverage-gaps-2026-10-17.md)。这是准确 3ac5f9b 的修复前基线，非本轮已修复结论。源存在性将继续检查主项目本机存量；原始行不提交。

# M5 44只不估逐项覆盖缺口（准确3ac5f9b）

本表来自本机只读快照及已存SEC/公告资料，只列缺项、来源存在性和修复归属，不输出原始金融行。

当前可估15/59；不估44/59。独立稀释加权股本缺41只；金融ROTE/TBV缺2只；困境规则有意不估1只。

| 股票 | 已发布类型 | 当前公式必需缺项（全部） | 来源/修复分组 |
|---|---|---|---|
| AVGO | 周期 | diluted_shares, cyclical_subindustry_PE_parameters | local_SEC_current_period_diluted_tag_exists |
| MRVL | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| MU | 周期 | diluted_shares | local_SEC_diluted_tag_does_not_cover_current_period |
| SKHY | 周期 | normal_net_margin, normal_revenue, diluted_shares | foreign_original_labels_exist_period_unit_extraction_needed |
| INTC | 困境 | 困境类按规则不估 | intentional_distress_no_value |
| NOK | 稳定 | fcf_ttm, diluted_shares | foreign_original_labels_exist_period_unit_extraction_needed |
| LITE | 未盈利成长 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| ORCL | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| CRM | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| ADBE | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| GOOGL | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| AMZN | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| NFLX | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| AAPL | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| TSLA | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| COST | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| WMT | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| HD | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| UNH | 金融 | rote_5y_avg, tbv_per_share | financial_tangible_equity_contract_missing |
| JNJ | 稳定 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| JPM | 金融 | rote_5y_avg, tbv_per_share | financial_tangible_equity_contract_missing |
| XOM | 周期 | diluted_shares | local_SEC_diluted_tag_does_not_cover_current_period |
| CVX | 周期 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| CAT | 周期 | diluted_shares | local_SEC_current_period_diluted_tag_exists |
| GE | 周期 | diluted_shares, cyclical_subindustry_PE_parameters | local_SEC_current_period_diluted_tag_exists |
| WDC | 周期 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| STX | 周期 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| SNDK | 周期 | normal_net_margin, normal_revenue, diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| AMAT | 周期 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| LRCX | 周期 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| KLAC | 周期 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| ASML | 周期 | normal_net_margin, diluted_shares | foreign_original_labels_exist_period_unit_extraction_needed |
| QCOM | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| ARM | 稳定 | fcf_ttm, diluted_shares | foreign_original_labels_exist_period_unit_extraction_needed |
| TSM | 稳定 | diluted_shares | foreign_original_labels_exist_period_unit_extraction_needed |
| CIEN | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| COHR | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| ETN | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| GEV | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| CEG | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| DELL | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| CRWD | 未盈利成长 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| FTNT | 稳定 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |
| ZS | 未盈利成长 | diluted_shares | full_original_not_in_review_local_archive_not_proven_unobtainable |

## 来源统计（不冒充已提取完成）

{"local_SEC_current_period_diluted_tag_exists": 17, "local_SEC_diluted_tag_does_not_cover_current_period": 2, "foreign_original_labels_exist_period_unit_extraction_needed": 5, "intentional_distress_no_value": 1, "full_original_not_in_review_local_archive_not_proven_unobtainable": 17, "financial_tangible_equity_contract_missing": 2}

41只名单：AVGO, MRVL, MU, SKHY, NOK, LITE, ORCL, CRM, ADBE, GOOGL, AMZN, NFLX, AAPL, TSLA, COST, WMT, HD, JNJ, XOM, CVX, CAT, GE, WDC, STX, SNDK, AMAT, LRCX, KLAC, ASML, QCOM, ARM, TSM, CIEN, COHR, ETN, GEV, CEG, DELL, CRWD, FTNT, ZS

M2当前shares优先取期末普通股，作为规则A市值与打分输入；M5要求稀释加权股本，两者语义不同。新增估值专用字段及独立来源，不替换shares；保持旧state输出和规则A/M3/M4逐字段/订单对照不变。

现有固定接口未单独暴露diluted_shares，不能靠将ordinary字段改名来提高覆盖。原始标签/公告行的期长、单位、拆股、多类别与当时可见性需单独验收。

NOK/ARM除股本还缺FCF；SKHY/SNDK/ASML缺常态利润率（SKHY/SNDK还缺三年营收）；AVGO/GE缺已确认周期PE参数。原reason只报第一个缺项，会低估后续工作。

ROTE/TBV、历史不足与未定义PE参数的修复分组和验收建议见后续完整报告。原始金融包仍仅本机，无上传或变更。

