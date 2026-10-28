# trusted 用户的 high 连接与聊天切换

用户已确认：trusted 与 admin 可以签发、使用本人的 high 连接，聊天窗可以切换本人 low/high；网页与外部接入的提示词都要求 execute 先得到明确确认。

## 实现范围

- `agent_access.py` 的签发、认证、执行三个门槛统一接受 trusted/admin；普通用户仍只能 low，所属用户降为 untrusted 后 high 失效。用户/角色管理仍仅管理员，Agent 不新增管理工具。
- `web_agent.py` 配置返回本人获准的 low/high，聊天身份记录实际连接等级；每轮将该等级交给模型，开始事件也带等级。默认网页助手仍为 low，不自动创建或选择 high。
- 连接管理页面向 trusted 开放 high；悬浮聊天工具栏与设置中的连接选择显示等级，打开列表时刷新选项。切换保留原生对话历史，运行中禁止切换。提示按实际等级显示。
- 更新 `web-agent.md`、共用 `overview.md/guide.md`、MCP 工具说明和公开接入指南：execute 先说明对象、操作、关键参数与生效影响，得到明确确认后执行；同一已确认批次不反复询问，切换 high 不代表确认。查询、help 和原有 propose 规则保持。
- 不新增数据库、审批或确认状态机，不放宽账本约束，不改模型调用上限，不发布生产。

## 检查与步骤

- [x] 复用既有权限用例覆盖 trusted 签发/升级 high、降级失效、普通用户拒绝；propose 仍待审；真实 MCP high 执行也走 trusted 用户。
- [x] 网页配置测试覆盖本人两档、他人拒绝；原生历史用例增加从 low 切 high，模型收到正确等级和工具集，同时保留先前帮助记录。
- [x] 完成权限、界面与提示词调整，同步当前架构说明。
- [x] 备份当前 fgas_test，集中运行 Agent 与身份相关检查；结束后恢复数据。前端运行 `npm run build`，静态截图至多核对布局，不自动点击或填表。
- [x] 一次独立只读审阅，重启本地预览，记录实际结果及未验证项。

## 验证记录

- 修改核心权限用例后先复现 3 个失败场景：trusted 签发 high 被拒，以及两种角色的网页连接配置仍拒绝 high。
- `AUTH_MODE=development FGAS_TEST_DATABASE=1 DATABASE_URL=<专用 fgas_test> /tmp/sunyunbo/fgas-web-agent-venv/bin/python -m pytest backend/tests/test_agent_access.py backend/tests/test_auth_casdoor.py -q`：**57 passed in 15.82s**。扩展原有用例，未引入独立测试框架。
- 独立只读审阅发现 execute 写入未触发前端 changed 通知，已接入现有刷新逻辑；未引入额外恢复状态。其他权限和提示词检查无实质问题。
- 最终 `npm run build` 通过，保留主 chunk 608.86 kB 的既有提示；`git diff --check` 通过。截图 `/tmp/sunyunbo/fgas-trusted-high/`，桌面 1440px、手机 390px 均无 pageerror 或横向溢出；未自动点击或填写表单。
- 测试前完整备份 fgas_test，结束后恢复成功。本地预览 API 健康检查返回 200；共享模型状态由截图只读 fixture 展示，不代表真实模型调用。
- execute 确认依赖提示词，尚未用真实模型验收确认话术和遵循情况；未发布生产。
