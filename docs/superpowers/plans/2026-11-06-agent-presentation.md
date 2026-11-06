# Agent 信息呈现与 DeepSeek 适配

用户已确认方案 A：保留 MCP 四入口，整理提示词、帮助及结果说明，并核对锁定框架的请求转换。另一方案为拆分强类型工具，会增加发现上下文和客户端适配，本轮不采用。

目标：减少重复概览，让模型明确参数、结果状态与查询范围；保留原生消息历史和现有权限边界。

约束：不改数据库、授权、审批流程，不新增请求恢复、自动重试或工具入口；不部署、不调用付费模型；测试只连接 fgas_test，不做浏览器交互。

- [x] 整理 web-agent.md 与 overview.md 的职责；工具说明允许已有概览的客户端直接查具体帮助。
- [x] 在现有 help 中解释分页、汇总及写入结果字段，不新增业务结果字段；更新指南版本。
- [x] 在隔离环境安装已锁定依赖，检查思考历史、模型切换、截断和 MCP 结果转换；有具体缺口才增加最小行为覆盖或修复。
- [x] 集中运行相关已有检查和必要行为验证，记录结果与限制。

涉及文件：backend/application/web_agent.py、backend/entrypoints/agent_catalog.py、backend/entrypoints/mcp.py、docs/ai/{web-agent,overview}.md、backend/tests/test_agent_access.py。max_tokens=8192 已由用户单独授权。

## 结果

- 锁定 pydantic-ai-slim 2.63.0 的 DeepSeekProvider 配置 reasoning_content 回传；MCP 映射在文本兼容内容与结构化结果同时存在时选择结构化结果。本轮未改这些框架行为。
- 本地 HTTP 模拟响应经过真实 provider 流解析、chat_events、JSON 往返和 load_history 后，出站请求保留两段思考（工具调用轮与纯文字轮）、工具调用 ID 和结果；Flash→Pro 切换通过。
- 新用例先复现 length 结束仍发 done（1 passed, 1 failed）；修复为保留历史及用量、发 error 而非 done，不重试、不恢复执行。
- 隔离环境安装 backend/requirements-agent.txt。显式 DATABASE_URL 指向本机 55438 的 fgas_test，FGAS_TEST_DATABASE=1，运行 `/tmp/fgas-agent-review-venv/bin/python -m pytest backend/tests/test_agent_access.py -q`：47 passed in 18.24s，无跳过。py_compile、git diff --check 通过。
- sandbox 内异步检查曾挂起并被终止，获准在 sandbox 外执行后完成；未改默认开发环境依赖。
- 未调用真实 DeepSeek、未做浏览器交互、未发布。模拟供应商响应证明转换行为，不代表模型实际任务成功率。
- 独立只读最终审阅无重要问题；新 provider 测试以本地工具替代 MCPToolset，不将其描述为真实 MCP 全链路验证。既有 Agent 专项测试另覆盖 MCP 路径。
