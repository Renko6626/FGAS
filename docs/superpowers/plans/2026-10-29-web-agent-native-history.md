# 网页助手完整消息历史

用户已确认沿用常规 Agent 做法，跨轮保留工具调用历史；采用此前提出的最小方案：框架原生消息保存在当前网页内存，下轮回传，界面保持简洁。

## 范围与接口

- `backend/application/web_agent.py` 使用 `ModelMessagesTypeAdapter`、`sanitize_messages` 读取客户端历史，直接作为 `message_history`；不再重组为纯文本。每轮通过原生 `capture_run_messages` 捕获完整轨迹，SSE 新增 `history` 事件，携带原生 JSON 消息列表。普通失败前已捕获的消息也返回；连接取消不新增恢复机制。
- `backend/entrypoints/web_agent.py` 的 `history` 接收原生 JSON 对象列表，进入流之前解析、清理，格式错误返回 422。移除原先把工具消息也计入的 40 条限制；现有界面的聊天长度约束保持不变。不兼容旧文本历史，开发预览需刷新重新开始。
- `frontend/src/api/webAgent.ts` 定义不透明的 `AgentHistory` 类型和事件；`FloatingWebAgent.vue` 单独保存模型历史并原样回传，聊天文本只供显示；清空会话同时清空两份记录。
- 不新增数据库、后端会话存储、签名算法、重试或压缩机制，不改原有权限、工具契约和单轮调用上限。

## 实施与验证

- [x] 复用既有 HTTP + 真实 MCP + FunctionModel 的第二轮纠错用例：第一轮先查 help，第二轮原生回传，模型确实能看到旧调用 ID、参数和帮助结果，再处理新调用及错误反馈。
- [x] 实现前后端历史传递，保留历史中的原生消息信息；普通失败采用框架捕获的已有消息，不伪造结果。
- [x] 保留当前 fgas_test 数据备份，运行 `backend/tests/test_agent_access.py`；结束后恢复测试库。运行 `npm run build`、差异检查和一次独立只读审阅。
- [x] 更新当前说明，重启本地原型；不调用真实模型、不自动操作浏览器、不发布生产。

## 验证记录

- 修改既有用例后先复现缺失原生历史事件，两个场景均失败；接入后跨轮帮助调用 ID、参数、真实结果均到达模型替身，并继续完成参数纠错和身份查询。
- 同一用例继续模拟第三轮已查询后中断，服务端仍返回已捕获的完整轨迹；验证两次已成功身份查询均保留。模型 Key 和 MCP 认证凭据不出现在返回历史中。
- `AUTH_MODE=development FGAS_TEST_DATABASE=1 DATABASE_URL=<专用 fgas_test> /tmp/sunyunbo/fgas-web-agent-venv/bin/python -m pytest backend/tests/test_agent_access.py -q`：**39 passed in 12.09s**。未重跑无关后端检查，未新增独立测试框架。
- `npm run build`：通过，保留主 chunk 608.84 kB 的既有提示；`git diff --check` 通过。未自动点击或填表，未调用真实模型验证缓存命中率。
- 独立只读审阅未发现实质问题。原有 fgas_test 备份已恢复，ST-000216/ST-000217 仍在；日常库未改。预览后端从主目录重新启动。
