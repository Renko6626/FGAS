# Agent 查询与帮助精简实施计划

**目标：** 修复库存分页，准确声明有限取值参数，减少 AI 获取帮助和查询时的无用内容。

**既定路线：** 保留 FastAPI、MCP v2 四入口、low/high、现有业务服务与 PostgreSQL；不增加依赖、数据库字段、恢复机制或客户端运行时。用户已授权修复上轮审阅问题。

**接口决策（用户已确认）：** help 默认返回说明、精确输入 Schema 与示例，新增 `include_output_schema=true` 获取输出 Schema。另一方案为自定义参数表，需额外维护格式，未采用。

**参考：** 本机 DeepSeek Harness `dsh-mcp-client` / `dsh-tools` 0.1.5-rc.3 的 README 与实现。native 使用工具说明和输入 Schema，PTC 使用生成 SDK；帮助结果进入调用历史。保持标准 Schema、减少默认帮助内容，兼顾两种呈现。

## 工作项

- [x] 在 `backend/tests/test_agent_access.py` 扩展已有 MCP 用例覆盖库存跨页回归，沿用 HTTP 创建目录与现有 MCP 客户端，检查第一页、第二页、大页及汇总。
- [x] `agent_queries.get_inventory` 传递 page/limit，用数据库 total 判断 has_more，取消二次分页。
- [x] `agent_schemas` 分别声明资金与货物状态枚举；`agent_catalog` 的 help resource/action 使用现有契约表生成枚举。已有 kind、basis、level、topic 等枚举继续保留。错误参数返回字段与合法值。
- [x] 复用货物流水分页服务；货物列表避免加载随后丢弃的关联详情。联系人备注和当前保管人沿用已有资料补充只读返回。
- [x] 用户确认帮助接口后调整 `agent_catalog` / `mcp`，保留精确输入校验与 Patch 语义；压缩 overview/guide 的重复内容，更新相关文档与现有帮助测试。
- [x] 集中运行相关 Agent/货物测试；完整改动结束运行项目后端检查。仅使用 fgas_test，不做浏览器交互、不修改客户端长期配置；外部模型体验按用户后续明确授权单独执行。
- [x] 比较相同 JSON 序列化口径的帮助体积，审阅实际差异与验证证据。

## 验收重点

库存超过20条仍能完整翻页且 totals 不因页码变化；无效状态不能伪装为空结果；枚举在帮助 Schema 中可见；low 不增加执行权限；指南保留资金与货物生效区别、结算、私账方向、分页和不自动重发写入等必要规则。

## 进度

审阅基线：Agent 现有18项测试通过；库存27条时第一页20条且 has_more=false，第二页为空，limit=100仍20条，已在 fgas_test 复现并回滚临时数据。


集中验证：显式指定 fgas_test 执行 `./tools/run_tests.sh`，64 passed（22.77s）；Agent专项20 passed。一次独立只读审阅无重要问题。工作区未提交、未部署。

用户追加真实 Agent 工具体验，允许本轮调用模型。已通过 dsh_subagent 原生 MCP 启动一个只提供 FGAS 四工具的临时 native preset，任务为完整库存分页、已付款未到货采购、待审垫付、到货完成及首次使用反馈。使用临时 loopback 服务和 fgas_test；令牌只在服务进程内存中，由测试运行时注入，未写文件或对话。体验已完成并由父 agent 通过实际 MCP 读取核对；详见下方验收记录。


真实 Agent 验收：DSH agent `ad138e45-5fa0-45b8-a709-b4d84efbf990` completed；查询27条库存，采购120元，公账1000→880，货物10→12，32.50元提议保持pending，仅一笔采购付款。四次写调用均一次成功。17次help查询各不相同。模型提示完成路径、完成结果ID和库存member字段不够明确，已在对应短帮助与guide补充；模型声称缺少stock_transfer_id/status与实际返回不符，未按误读修改接口。详情裁剪、聚合结构或命名变化不在本轮扩展。

后续仅帮助文案与字段说明变化，运行 `pytest backend/tests/test_agent_access.py -k 'help or compact' -q`：8 passed，12 deselected；`git diff --check`通过。临时凭据停用，服务进程停止，专属preset删除，DSH运行时关闭。无密钥验收证据保留 `/tmp/fgas-agent-trial/`。未重新运行全量测试、未做浏览器流程或生产部署。
