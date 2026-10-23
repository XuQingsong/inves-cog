# 准确提交 CI 实回

- head 87f006048f4a2d642acf69a256aac860732b30c1：[CI39951689859](https://github.com/XuQingsong/inves-cog/actions/runs/39951689859)，5 failed、543 passed、21 deselected（134.99秒）。独立已读 job120407414888 完整日志。
- 五项失败均在 tests/ops/test_runtime_scheduling.py：旧固定北京窗口两项参数、原外层paper评分门禁、原premarket/paper重叠断言、旧固定北京窗口断言。按A016授权的ET08:35–09:05和M4 CLI拥有评分等待/截止处理更新；保留原测试名及M7/M5断言，不改门禁或跳过测试。
- 更新后的准确提交CI另行记录，旧失败不覆盖为成功。

- 需求方集成验证 [CI39962796598/job120444795980](https://github.com/XuQingsong/inves-cog/actions/runs/39962796598/job/120444795980)：568 passed、21 deselected，但 `FR-M0-12: blocking took 181.607s > 180s`，make退出1。业务断言没有失败，不能写成集成成功；未放宽180秒门槛或修改B测试。
- 按A016最新反馈合入 main dbea515（继承B047及需求方文档），不改继承的B源码/合同。新增的准确提交仅这次集成及失败事实记录，下一次准确head完整CI用于决定是否可验收；若仍超时，报告既有总套件性能边界，不无限重试或改B范围。
