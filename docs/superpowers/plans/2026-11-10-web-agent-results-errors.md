# 网页助手工具结果与错误分类

用户确认优先实施工具业务结果和错误分类。沿用现有 MCP 业务契约、权限、原生历史和 SSE；只给 tool_end 增加 outcome/summary/code，error 增加 code，并准确设置 configuration_error。无新依赖、存储、恢复、重试、日志平台或用量改造。

## 行为

- 成功摘要只取业务编号、状态和正式流水影响，钱货组合分别显示；完成报告说明 SC 与父 ST 状态。
- 工具失败优先显示 MCP 的业务错误说明，框架参数错误使用固定安全文案；不输出原始异常、参数或结果 JSON。
- 工具阶段显示成功、失败、待核对，写操作与失败结果默认展开。模型文字中断仍可看到已经收到的摘要。
- 运行错误区分模型凭据、余额、限流、服务不可用、连接/超时、请求被拒绝、上下文过长、本轮上限及其他执行错误。只有明确配置问题打开设置，不自动重放操作。
- 原有 HTTP 聊天准备校验仍使用现有 400/403 配置引导，模型流错误由明确分类决定。

## 实施与验证

- [x] 修改 backend/application/web_agent.py 的结果投影和异常分类，并连接到 SSE。
- [x] 修改 frontend/src/api/webAgent.ts 和 FloatingWebAgent.vue，展示摘要与结果状态，保留前轮 UI 改动。
- [x] 复用 backend/tests/test_agent_access.py：补充必要结果/错误回归及既有流式断言。
- [x] 仅在 fgas_test 执行相关 Agent 检查，运行 npm run build 与 git diff --check，进行一次只读审阅。

不做浏览器自动交互或真实模型调用；不提交或发布。测试覆盖重点：待审不当成入账、SC/ST 不混淆、组合结果独立、失败不当成功、429 不当配置错误。

## 验证记录

使用与 requirements-agent.txt 一致的 /tmp/fgas-agent-review-venv（pydantic-ai-slim 2.63.0、fastmcp-slim 4.1.4）。新增关键回归先因缺少实现失败，实施后 11 passed。显式指定 DATABASE_URL 为本机专用 fgas_test、FGAS_TEST_DATABASE=1，运行 `/tmp/fgas-agent-review-venv/bin/python -m pytest backend/tests/test_agent_access.py -q`：58 passed。最后收紧协议重试分类后仅复查 `-k "tool_failure or can_correct_tool_arguments"`：4 passed。测试前专用库备份到 /tmp/fgas-test-before-agent-results-20261110.dump，日常库未改。

`npm run build`（vue-tsc + Vite）通过，保留主包体积提示；`git diff --check` 通过。一次独立只读审阅未发现核心问题。未进行浏览器自动交互或真实模型调用，未提交或发布。
