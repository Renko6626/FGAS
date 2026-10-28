# 网页助手本地原型

设计见 [接入设计](superpowers/specs/2026-10-28-web-agent-design.md)，完整分期和实施记录见 [实施计划](superpowers/plans/2026-10-28-web-agent-prototype.md)。2026-10-29 已按用户要求将原型快进合并到主目录 `main`，后续在主目录维护；尚未发布线上。

## 已有能力

- 工作台右下角“网页助手”随时打开独立悬浮组件，切换业务页面或收起面板均保留会话、个人 Key 和正在接收的回复。桌面面板宽 560px，标题、工具栏和输入区缩减留白，主要区域用于聊天记录。模型配置位于独立弹窗，只有手动打开设置、无可用配置时尝试对话，或模型配置报错时才弹出。关闭错误弹窗后再次发送会先引导配置；修改或明确确认配置后再由用户发送。未执行工具、未收到回复时，失败请求的输入回到输入框；已有工具结果保留。桌面和手机沿用现有样式。
- 后端 Pydantic AI 运行多步工具循环，使用本人启用且未过期的 low 连接，MCP 保持 Bearer 认证。模型可以查询资料、提交待审批申请，后续审批仍在原有业务页面完成。
- 个人 DeepSeek Key 或管理员提供的公共模型，官方 Chat Completions 接口；支持 `deepseek-flash`、`deepseek-v4-pro`。
- 助手回复支持基础 Markdown：标题、列表、粗体、引用、代码块、链接和表格。原始 HTML 按文本显示，图片不加载；用户输入仍显示纯文本。FT/ST 编号可以打开现有详情，使用页内链接维持助手连接。
- 工具进度、本页会话 token 用量；停止接收回复后，未返回的工具显示“待核对”，业务是否已提交以记录为准。
- 管理员可以查询公共 DeepSeek 账户余额。原型展示的是本页会话 token，不是全站历史消费账单，也不估算扣款。
- 原型开启时，Casdoor 首次建立用户会同步创建启用的 low“网页助手”；已有用户可以选择本人连接或创建一个。停用连接不会自动重建。

## 启动

以下命令在项目主目录执行。独立虚拟环境避免更新日常开发环境的 Starlette/OpenAI SDK：

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

个人 Key 填入面板“模型设置”，只保存在当前页面内存，通过 Cookie HTTP 请求交给后端调用，不放入 MCP 工具参数。公共 Key 使用环境变量 `FGAS_DEEPSEEK_API_KEY`；启动器可从当前项目 `.env` 读取这一项。填入后重启原型后端生效。其他系统的认证 Key 不用于模型调用。

没有个人 Key 时可以使用已配置的公共模型。个人模型报错时由用户主动切换来源，程序不自动切换并重播业务工具。不要把真实 Key 提交到 Git。后端默认关闭原型；生产依然只安装原有 `backend/requirements.txt`。

## 助手提示词

每轮模型请求由 `backend/application/web_agent.py` 读取并组合两份文档：

- [web-agent.md](ai/web-agent.md)：网页助手提示词初稿，定义身份、语气、任务推进、工具使用、授权与隐私限制、结果和异常表达，并给出少量示例。
- 提示词单独解释 `fgas_help/query/propose/execute` 的职责、low 可用范围及按资源查询帮助的方式；通用 `filters/data` 不能作为自由字段使用。已有完整契约可沿用，缺少实际参数说明时先查具体帮助。
- [overview.md](ai/overview.md)：与外部 MCP Agent 共用的账本模型、业务生效规则和调用约定。具体参数和完整业务指南仍由 `fgas_help` 按需提供。

前者仅供网页助手，不改变外部 MCP 的说明。当前未注入用户所处页面、选中单据等上下文；提示词要求助手如实说明能力，不假装能看见或操控页面。提示词每轮读取，修改后下次发送即可使用；这不等于真实模型已经验收。

工具报错也是 Agent 循环的输入：MCP 已返回的业务错误作为失败结果交给模型；工具参数格式校验提供有限修正预算（2 次），整轮仍最多 10 次模型请求。模型可根据错误查帮助、修正明确未执行的参数或补问用户。权限不足、业务条件不满足不靠换参数绕过；超时或断线导致提交结果未知时仍须先查记录。模型 SDK 的网络自动重试保持关闭。

合并验证：主目录使用独立 Python 环境在专用 `fgas_test` 上运行现有后端检查，85 passed；`npm run build` 与差异检查通过。FunctionModel 替身核对两份文档进入实际模型请求，真实 Cookie/MCP low 身份查询和两轮流式事件完成，未调用供应商。预览已迁回主目录，独立工作树已清理。

## 当前边界

聊天历史、个人 Key 与会话统计仅在当前工作台内存，切换业务页面和收起面板不清空，刷新清空；停止按钮结束接收，退出或切换账号、关闭网页会中止请求。已经提交的待审单据不会因此撤销。

正式版还需要确认默认连接的稳定关联、个人 Key 加密保存、聊天与调用用量的数据库结构、历史统计和已有用户补齐方案。这些改动必须使用新的 Alembic revision。high 网页助手、后台持续运行和断线恢复不属于本轮原型。

## 本轮验证

- 隔离环境 `pip check` 通过，MCP 2.3.0 与 Pydantic AI / FastMCP 客户端导入兼容。
- 隔离依赖组合运行现有全部后端检查：`DATABASE_URL=…/fgas_test FGAS_TEST_DATABASE=1 …/python -m pytest backend/tests -q`，85 passed in 36.95s。此前相关检查 51 passed；新权限用例复用既有 Agent 测试文件，新用户默认连接复用首次登录测试覆盖。
- 使用 Pydantic AI FunctionModel 作为本地模型替身，经过真实 Cookie 登录、本人 low 连接与真实 MCP `fgas_query(me)`，完成工具开始/结束、文本、用量、done 事件；两轮模型请求。该用量是替身数据，不能作为真实消费。
- `npm run build` 的 TypeScript 检查和生产构建通过，保留主 chunk 608.80 kB 超过 500 kB 的提示；桌面 1440px、手机 390px 截图无页面错误或横向溢出。没有浏览器自动点击或填表。
- 当前没有 FGAS 专用 DeepSeek Key，尚未进行真实模型调用、余额查询和真实 token/费用核对。普通用户可以自行填入个人 Key 体验。
- 初次原型验证时未改日常开发库、未新增数据库结构、未合并主线或发布生产；2026-10-29 已合并主线，仍未发布。

## 2026-10-29 悬浮组件调整验证

- `npm run build` 通过；`git diff --check` 通过。只改前端，未重复运行后端测试。
- 直接调用实际 Markdown 渲染器核对标题、列表、引用、表格、代码、FT/ST 页内跳转、已有链接不嵌套及不可信 HTML/URL 转义。未新增测试框架或 CI。
- 1440px 桌面和 390px 手机截图无页面错误和横向溢出；聊天区高度分别约 599px、533px。主页和货物页均能看到收起状态的悬浮入口。截图位于 `/tmp/sunyunbo/fgas-floating-agent/`，有模型状态由只读配置 fixture 展示。
- 未自动点击、填表或执行切页时流式回复的交互验证；未调用真实模型。
