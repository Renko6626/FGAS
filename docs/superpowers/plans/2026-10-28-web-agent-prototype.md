# 网页助手接入与原型实施计划

> **For agentic workers:** Use superpowers:executing-plans for inline implementation. 本轮是用户明确要求的本地原型；持久化方案待确认后再实施。

**Goal:** 提供可运行的页面对话原型，验证后端 Pydantic AI、DeepSeek、用户 low MCP 连接与流式界面。

**Architecture:** 现有 FastAPI 内加入可选网页助手服务，Cookie 解析网页用户，MCP 使用该用户本人连接的 Bearer 凭据。Vue 保存当前页面会话，通过 fetch 接收服务端事件。原型不新增数据库结构。

**Tech Stack:** Python 3.13、FastAPI、Pydantic AI 2.63.0 slim openai/mcp、FastMCP client 4.1.4、MCP 2.3.0、Vue 3、Naive UI。

**Spec:** `docs/superpowers/specs/2026-10-28-web-agent-design.md`

## Global Constraints

- 只实现已确认的后端循环与 DeepSeek，原型开关默认关闭，不改生产部署或业务数据模型。
- 用户创建时为本人创建启用的 low 网页助手；既有用户在原型里选择/创建本人 low 连接。
- BYOK 与历史只存当前页面内存；公共 Key 使用 FGAS_DEEPSEEK_API_KEY，不复用其他服务密钥。
- Cookie 与 MCP Bearer 分离，工具只走应用授权链，密钥不进入模型提示、工具参数、日志或 Git。
- 数据库验证仅 fgas_test；UI 仅类型/构建与截图，不自动点击/填表。

## Review Focus

- Cookie 登录用户不能选用他人的连接；管理员在聊天入口也只能用本人连接。
- 停用、过期及 high 连接不能被原型误当成默认 low。
- 框架依赖独立验证，不升级共享开发虚拟环境或生产运行环境。
- 工具执行与事务不在模型网络等待期间占用业务数据库会话。
- Key 错误、余额不足或流中断只展示已完成结果，不自动重发写入。

### Task 1: 框架与后端原型

**Files:** `backend/requirements-agent.txt`、`backend/application/web_agent.py`、`backend/entrypoints/web_agent.py`、`backend/entrypoints/http.py`、`backend/application/sso.py`。

**Interfaces:** Cookie `/api/web-agent/config` 返回当前用户可用 low 连接及模型来源；`POST /api/web-agent/chat` 接收连接 ID、新消息、文本历史、模型与临时个人 Key，返回 SSE；`GET /api/web-agent/balance` 仅管理员查询公共 Key 的供应商余额。

- [x] 建立隔离虚拟环境，安装独立依赖并检查 MCP/FastAPI 导入兼容性。
- [x] 实现真实用户和连接解析、DeepSeek 模型构造及 Pydantic AI 事件映射，复用现有 MCP。
- [x] 增加默认关闭的 HTTP 路由和新用户默认 low 连接创建。
- [x] 复用真实 HTTP/数据库测试验证所有权、停用与新用户创建，运行受影响的已有检查。

### Task 2: 页面内对话

**Files:** `frontend/src/components/WebAgentPanel.vue`、`frontend/src/api/webAgent.ts`、`frontend/src/App.vue`、`frontend/src/api/auth.ts`。

**Interfaces:** 消费 Task 1 的配置与事件；组件按当前 user.id 与 identityEpoch 重建。页面只保留文本历史、临时个人 Key 和本次会话 token 汇总。

- [x] 在工作台顶栏增加网页助手入口，使用既有黑白样式构建浮动对话面板。
- [x] 显示用户 low 连接、个人/公共模型来源、文本、工具进度与 FT/ST 链接；支持停止当前请求和清空会话。
- [x] 管理员显示公共余额查询，明确本次会话用量与全站历史统计的区别。
- [x] 运行前端类型检查与生产构建；桌面/手机只截图。

### Task 3: 联调与交付

**Files:** `docs/web-agent-prototype.md`、`docs/prototype-status.md`、本计划执行记录。

- [x] 使用 fgas_test 启动独立本地端口，使用本地模型替身驱动真实 MCP 检查多步循环、身份和流式事件。
- [ ] 如用户提供专用 Key，执行少量只读 DeepSeek 联调，不自动执行业务写入。
- [x] 一次独立只读审阅，修复实际阻塞问题，记录启动方式、地址及未验证项。
- [x] 保留原型分支，正式存储接入作为后续阶段，不发布生产。

## 后续正式接入任务（待存储方案确认）

- 新 Alembic revision：默认连接稳定关联、个人模型配置与加密 Key、会话/消息、逐请求用量记录。
- 用户首次创建与已有用户补齐默认连接；停用、权限变化继续沿用既有授权。
- 管理员公共模型配置、历史用量聚合与供应商余额查询；token 与估算费用分开，账本业务不混入模型计费。
- 持久会话、历史展示与部署变量/备份文档，集中执行相关既有检查后再发布。

## 执行记录

- 用户已确认后端循环、DeepSeek 优先、OpenAI 兼容协议、默认个人 low 网页助手和 Pydantic AI；本轮授权是先计划再写原型。
- 工作区 `.worktrees/web-agent-prototype`，分支 `feature/web-agent-prototype`，基于 f9ff39f。

- 原型验证完成：隔离环境 `/tmp/sunyunbo/fgas-web-agent-venv`，pip check 通过；Pydantic AI FunctionModel 通过真实本人 low MCP 查询 me，两个模型回合和完整 SSE 事件链通过。无真实 Key，未调用 DeepSeek，替身用量不代表真实计费。
- 完整保留后端检查在 fgas_test 上 85 passed in 36.95s；前端 npm run build 通过，主 chunk 608.80 kB 的既有类型提示仍在；git diff --check 通过。
- 桌面 1440px、手机 390px 截图无 pageerror/横向溢出，未执行浏览器点击或填表。截图 `/tmp/sunyunbo/fgas-web-agent-preview/`。
- 独立只读审阅无授权或工具执行阻塞项；修正过期连接默认候选及停止/报错后工具状态提示，不增加恢复机制。
- 本地后端 10632、前端 5186 已启动；启动器只接受 fgas_test，公共 Key 未配置时网页可填个人 Key。持久化方案仍待确认，不合并 main 或部署生产。
