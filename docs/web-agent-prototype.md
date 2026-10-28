# 网页助手本地原型

设计见 [接入设计](superpowers/specs/2026-10-28-web-agent-design.md)，完整分期和实施记录见 [实施计划](superpowers/plans/2026-10-28-web-agent-prototype.md)。原型分支 `feature/web-agent-prototype`，本地工作区 `.worktrees/web-agent-prototype`，不影响线上已发布版本。

## 已有能力

- 工作台顶栏“网页助手”打开浮动对话面板，主要区域用于聊天记录和输入。模型配置位于独立弹窗，只有手动打开设置、无可用配置时尝试对话，或模型配置报错时才弹出。关闭错误弹窗后再次发送会先引导配置；修改或明确确认配置后再由用户发送。未执行工具、未收到回复时，失败请求的输入回到输入框；已有工具结果保留。桌面和手机沿用现有样式。
- 后端 Pydantic AI 运行多步工具循环，使用本人启用且未过期的 low 连接，MCP 保持 Bearer 认证。模型可以查询资料、提交待审批申请，后续审批仍在原有业务页面完成。
- 个人 DeepSeek Key 或管理员提供的公共模型，官方 Chat Completions 接口；支持 `deepseek-flash`、`deepseek-v4-pro`。
- 文本、工具进度、本页会话 token 用量；FT/ST 编号可以打开现有详情。停止接收回复后，未返回的工具显示“待核对”，业务是否已提交以记录为准。
- 管理员可以查询公共 DeepSeek 账户余额。原型展示的是本页会话 token，不是全站历史消费账单，也不估算扣款。
- 原型开启时，Casdoor 首次建立用户会同步创建启用的 low“网页助手”；已有用户可以选择本人连接或创建一个。停用连接不会自动重建。

## 启动

以下命令在原型工作区执行。独立虚拟环境避免更新日常开发环境的 Starlette/OpenAI SDK：

```bash
python3.13 -m venv .runtime/web-agent-venv
.runtime/web-agent-venv/bin/python -m pip install -r backend/requirements-agent.txt
.runtime/web-agent-venv/bin/python scripts/run-web-agent-prototype.py
```

启动器默认使用主工作区 `.runtime` PostgreSQL socket、55438 端口上的 `fgas_test`；可通过 `DATABASE_URL` 指定同名专用测试库，启动器会检查实际库名并拒绝其他库。它不清库、不执行迁移、不初始化种子；需要已准备好的当前测试库。开发账号为既有 `admin`、`trusted`、`untrusted`。不要把它指向日常 `fgas`。

另开终端启动前端：

```bash
cd frontend
VITE_API_PROXY_TARGET=http://127.0.0.1:10632 npm run dev -- --host 127.0.0.1 --port 5186 --strictPort
```

本轮已运行的后端为 `http://127.0.0.1:10632`，前端为 `http://127.0.0.1:5186/?assistant=1`。先选择开发账号登录；`assistant=1` 会自动展开面板，仅用于方便预览。开发环境会话可以从“当前账号”切换。

本轮隔离虚拟环境实际路径 `/tmp/sunyunbo/fgas-web-agent-venv`；重新启动可用其中的 Python。换机器后按上面的命令重新创建即可。

## 模型 Key

个人 Key 填入面板“模型设置”，只保存在当前页面内存，通过 Cookie HTTP 请求交给后端调用，不放入 MCP 工具参数。公共 Key 使用环境变量 `FGAS_DEEPSEEK_API_KEY`；启动器可从原型工作区 `.env` 或主工作区 `.env` 读取这一项。填入后重启原型后端生效。其他系统的认证 Key 不用于模型调用。

没有个人 Key 时可以使用已配置的公共模型。个人模型报错时由用户主动切换来源，程序不自动切换并重播业务工具。不要把真实 Key 提交到 Git。后端默认关闭原型；生产依然只安装原有 `backend/requirements.txt`。

## 当前边界

聊天历史、个人 Key 与会话统计仅在本页内存，刷新清空；界面关闭后当前请求仍可继续，停止按钮结束接收，退出账号/页面销毁会中止请求。已经提交的待审单据不会因此撤销。

正式版还需要确认默认连接的稳定关联、个人 Key 加密保存、聊天与调用用量的数据库结构、历史统计和已有用户补齐方案。这些改动必须使用新的 Alembic revision。high 网页助手、后台持续运行和断线恢复不属于本轮原型。

## 本轮验证

- 隔离环境 `pip check` 通过，MCP 2.3.0 与 Pydantic AI / FastMCP 客户端导入兼容。
- 隔离依赖组合运行现有全部后端检查：`DATABASE_URL=…/fgas_test FGAS_TEST_DATABASE=1 …/python -m pytest backend/tests -q`，85 passed in 36.95s。此前相关检查 51 passed；新权限用例复用既有 Agent 测试文件，新用户默认连接复用首次登录测试覆盖。
- 使用 Pydantic AI FunctionModel 作为本地模型替身，经过真实 Cookie 登录、本人 low 连接与真实 MCP `fgas_query(me)`，完成工具开始/结束、文本、用量、done 事件；两轮模型请求。该用量是替身数据，不能作为真实消费。
- `npm run build` 的 TypeScript 检查和生产构建通过，保留主 chunk 608.80 kB 超过 500 kB 的提示；桌面 1440px、手机 390px 截图无页面错误或横向溢出。没有浏览器自动点击或填表。
- 当前没有 FGAS 专用 DeepSeek Key，尚未进行真实模型调用、余额查询和真实 token/费用核对。普通用户可以自行填入个人 Key 体验。
- 未改日常开发库、未新增数据库结构、未合并主线或发布生产。
