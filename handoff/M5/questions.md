# M5 必须停问题

K01：成长类 V1 影子分的“Δg 同构曲线”缺四个横轴节点。请给出分别对应95/70/40/10分的Δg（百分点）。依据：规格§8.8、FR-M5-08。仅暂停该字段，其余按 A-007 继续。答复位置：ops/answers/A-007.md。

已答复：main 37ee8fb7b3f82534271cea4abc97c3f747a13ea5，ops/answers/A-007.md。四节点-10/0/+10/+25→95/70/40/10，分段线性与端点钳位；缺失保留NULL并写原因，不改用p。已先补失败断言，再填配置。K01关闭。

K02（跨模块主线登记，2026-10-16，已回报信箱）：继承main2165c29后，全仓pytest收集退出4，FR-M0-05提示M8新增的test_embedding_model_isolation、test_retrieval_background_window不在pending。M5只删了本模块14行，未改B的登记。请需求方或B在main登记未实现测试；A不改M8行或放宽门禁。合并前全仓127passed，不能将该旧结果冒称新main门禁通过。继续整理不受影响的M5证据，保持草稿，等待此主线修复后复跑。

K02已由需求方在main8d748ef34d11b547a5925f6cb715e44ee9b48a66补齐两条M8 pending登记；不改门禁或测试标准。A仅合入该主线提交，再复跑准确最终SHA，不改B模块行。
