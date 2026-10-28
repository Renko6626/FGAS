# 网页助手合并与提示词初稿

用户已确认现有原型，并要求先合并到主目录，再按已讨论的角色、语言风格和核心限制写一稿助手提示词。

## 范围与实现

- 将 `feature/web-agent-prototype` 的三个提交快进合并到主目录 `main`，不推送或发布。
- 新增 `docs/ai/web-agent.md`，定义网页助手身份、表达、任务推进、事实来源、授权边界、隐私和异常处理，含少量结果示例。
- `backend/application/web_agent.py` 每轮读取该文件及现有 `docs/ai/overview.md`，替代原先追加的两句指令。保持共用业务规则不变，不新增提示词框架、数据库结构或接口。
- 更新当前状态和启动说明，将本地预览迁回主目录；保留原型开关默认关闭和独立 Python 依赖环境。

## 验证与交付

- 合并后的完整改动集中验证：在专用 `fgas_test` 上用既有隔离依赖运行现有后端测试；`npm run build` 检查前端集成；`git diff --check` 检查差异。
- 使用本地 FunctionModel 替身经过真实 Cookie/MCP 路径核对提示词注入和流式查询，不访问模型供应商，不新增永久测试或浏览器交互流程。
- 审阅提示词与实际能力是否一致，尤其是 low 权限、未提供页面上下文、查询与执行意图区分，以及失败后不自动重发写入。
- 验证通过后清理本次原型工作树；其他工作树、日常开发库、生产部署和共享 Python 依赖不动。

## 进度

- [x] 主目录快进合并至 `15e66b1`，无冲突。
- [x] 提示词初稿与读取接入。
- [x] 合并验证、预览迁回主目录及工作树清理。

## 验证记录

- 主目录安装锁定的前端依赖：`npm --prefix frontend ci`，通过。
- 后端命令：`AUTH_MODE=development FGAS_TEST_DATABASE=1 DATABASE_URL=<本机专用 fgas_test> /tmp/sunyunbo/fgas-web-agent-venv/bin/python`，先执行 `SELECT current_database()` 护栏，再调用 `pytest.main(['backend/tests', '-q'])`；**85 passed in 36.47s**。未重置日常库，未扩充永久测试。
- `npm run build`：通过；既有主 chunk 608.84 kB 提示保留。`git diff --check`：通过。
- 临时离线检查：`/tmp/sunyunbo/fgas-web-agent-venv/bin/python /tmp/sunyunbo/fgas-main-agent-prompt-client.py`，通过。模型替身接收到完整助手指令与账本说明，经真实 Cookie/MCP 查询 low 身份，完成两轮模型请求、工具开始/结束、文本、usage 和 done 事件。框架会去除指令末尾空白，核对文档正文时忽略该末尾空白；未改动生产逻辑或放宽业务断言。
- 独立只读审阅未发现本次提示词/读取接入的实质问题。真实 DeepSeek 的语言风格、判断与工具选择未验收；没有浏览器自动交互。
- 主目录原型后端 10632、前端 5186 启动成功，HTTP 健康检查和首页返回 200。本次 `.worktrees/web-agent-prototype` 与已合并分支已清理；其他工作树未动。
