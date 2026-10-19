# M8 82bacdb：替代解释独立复验

准确head `82bacdbb1e0fad8980a973fd0c90d5ab9cbc7f18`，对照Q16 `a97361cf` 的缺失语义/候选独立范围。62断言55通过7不符；7项是同一个影响范围扩张问题的不同表现。

已通过三标记True/False/None全部27组合、缺键与部分未知：任一true可确定自身事件，全部false才查无，其余NULL；15%权重/NULL重配不变。只列NVDA/AMD且不带篮子的候选，实际完整chain各得替代分0/1、总分.46/.76，无关股票不会改变。明确列两只股票的候选允许.5。

尚未闭环：合法affected行同时含必填ticker及可选basket_id时，_alternative_members先加ticker又扩入同篮全部异常成员。NVDA自身事件true、AMD三标记false，同属semis：

| 合法候选 | 原Q16应有替代分/总分 | 实际 |
|---|---|---|
| 只列NVDA，附semis定位 | 0 / .46 | .5 / .61 |
| 只列AMD，附semis定位 | 1 / .76 | .5 / .61 |

通过实际parser→propose→validate→components→evidence_score复现；basket_members、baskets别名及member.basket_id三入口相同，若同篮同行未知还会把已知0变NULL。候选甲因此从低变中、乙从高变中，不只是显示；未运行交易，不宣称发生订单变化。

现有propose._affected_rows要求ticker非空，basket_id是附加定位；不能因定位字段暗中扩大单独列名标的的作用域。这沿用原Q16“只影响NVDA/AMD各自0/1”要求，不新增仅篮子行功能/阈值/公式。

本机review/m8-82bacdb-alternatives/保留62断言、原输入输出、准确Git blob及规范diff；无模型/环境/凭证/数据库/部署或开发源码修改。未知处理窄项关闭，合法带篮子范围不关闭；依UD-COORD-05由协调方承接最小修复，不再退B消耗额度。M8整体及四例/全池五日未通过。
