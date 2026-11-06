# CSV 台账导出

用户确认：全部台账、截至 T 的现状、(T,U] 的已入账变化，资金与货物分别 CSV，多表 ZIP 下载。默认按实际入账时间；首版不做其他筛选。使用现有资金与货物模型，不新增数据库表、队列或快照存储。

实现细节：所有启用且已登录用户可读，与现有台账权限一致；Cookie HTTP 下载，不新增 MCP 工具。日常工作新增“导出台账”，复用现有 Naive UI 页面样式。GET /api/exports?mode=all|snapshot|changes，snapshot 使用 as_of，changes 使用 start/end，必须带时区，现状含截止点、变化不含起点而含终点。不支持未来截止点；可留空截止取本次快照时间。

ZIP 含两个 UTF-8 BOM CSV 和说明.txt（生成时间、边界、行数、口径）。金额元、数量整数；状态中文；业务编号与名称并列；货物每个单据 SKU 一行。原资金单与冲销单均保留；停用账户与 SKU 不过滤。历史数量/金额配当前目录名称，零余额/零库存保留。现状资金含 public/private/external，库存仅 internal 仓库。

- [x] 后端：基础设施读取、应用导出编排、HTTP 适配；复用 read_snapshot 和正式流水计算。
- [x] 前端：三个选项、上海时间输入、下载与错误提示。
- [x] 测试：真实 fgas_test HTTP 验证认证、CSV 格式、状态、时间边界及现状+变化一致；运行前端构建。
- [x] 独立只读审阅、记录验证。未经请求不发布，不自动浏览器交互。

验证：显式 DATABASE_URL 指向本机 55438 的 fgas_test，FGAS_TEST_DATABASE=1，以 /tmp/fgas-agent-review-venv/bin/python 运行 pytest backend/tests/test_exports.py backend/tests/test_funds.py backend/tests/test_stock_transfers.py -q：26 passed in 13.98s。npm run build、py_compile、bash -n tools/run_tests.sh、git diff --check 通过。新增导出用例已加入现有 run_tests.sh，无新增工作流。

独立只读审阅未发现重要问题，确认资金原单/冲销、货物正式流水、(T,U]边界和 Cookie 权限符合范围。未调用真实外部服务、未做浏览器交互、未发布。
