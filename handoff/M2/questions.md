# M2 v2 开发中新问题（等待答复）

基线 main：4e217a0。已先提交失败测试：633d141a0e450c058b843c2d517b0821a50a19a9；17 个测试全部存在，15 个 blocking 首次全部失败；尚未提交实现。replay 保留“等待 R7（Muse 导出）”，live 保留“等待 R4/R5/R7”。

## K13：M0 干净环境断言排斥任何后续迁移

`tests/harness/test_m0_ci.py:13` 写死 `record['migrations']` 只能为 M0 一项，而 `scripts/phase1.py` 正确执行并记录全部迁移。加入 M2 必需迁移后，干净环境 CI 会必然失败。

详细证据、建议与授权边界见 [M1 questions.md](https://github.com/XuQingsong/inves-cog/blob/phase1/m1-market-info-ingest/handoff/M1/questions.md) K14：建议对完整迁移清单作动态一致性断言，并保留 M0 必需项与其他环境断言。请求需求方 main 修正基线，或给 M1 明确例外；M2 随后合入修正，不独立改 M0、不自建共享客户端或共享表。

按任务书 §4.1 第③步，此问题发布后暂停实现，等待答复。中期 checkpoint 尚未达到，不把合成数据或未取得的 oracle 声称为真实结果。
