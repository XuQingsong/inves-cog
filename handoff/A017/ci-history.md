# A017 准确提交 CI

- head337df84f92bb0806667828977042a9cfff2ce463，[CI39971495151/job120475066604](https://github.com/XuQingsong/inves-cog/actions/runs/39971495151/job/120475066604)：1failed/586passed/21deselected/179.99秒；8项A017测试全部通过（含真实一次性数据库市场页与原JSON完全相等/无交易字段）。唯一失败test_import_firewall：ruff format要求三个新增Python文件格式化。
- 此前本地只跑ruff check，漏了format --check；现对本单三个新文件执行formatter，并本地check与format --check均通过。不改格式门禁、不改B代码/测试、未跳过功能用例。新准确head CI另行实回。
