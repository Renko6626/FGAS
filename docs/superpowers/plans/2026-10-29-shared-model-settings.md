# 公共模型设置实施计划

> 使用 superpowers:executing-plans 在当前工作区实施；保留前轮未提交修复，不建立额外设计或部署流程。

**目标：** 管理员在工作台配置社团公共 DeepSeek Key，保存后供新的聊天和余额请求使用。

**已确认方案：** 用户选择 A，单行数据库配置明文保存；数据库备份也包含 Key。管理员可替换和清除，响应只报告状态和来源、不返回完整或部分 Key。数据库配置优先于 `FGAS_DEEPSEEK_API_KEY`，清除后回退环境变量。其他成员只能通过网页助手使用公共模型。个人 Key 行为不变。

**技术与边界：** 沿用 FastAPI、SQLAlchemy、PostgreSQL、Vue、Naive UI。不增加依赖、确认状态机、请求恢复、用量计费或生产发布。使用新 Alembic revision `0002`，保留 `0001`。只升级专用 `fgas_test`，升级前备份；日常库不改。

## 接口与文件

- `backend/infrastructure/models.py`：`WebAgentSettings`，固定使用 id=1，保存 deepseek_api_key；空配置删除行。
- `backend/infrastructure/web_agent_store.py`：上述配置的读取、保存和清除。
- `backend/migrations/versions/0002_web_agent_settings.py`：建表与 downgrade。
- `backend/application/web_agent.py`：公共 Key 解析、管理员状态/保存/清除；聊天与余额共用数据库优先规则。
- `backend/entrypoints/web_agent.py`：Cookie HTTP `GET/PUT/DELETE /api/web-agent/shared-config`。PUT 接收非空 `api_key`，GET/写响应为 `{configured, source: database|environment|null, database_configured}`；原余额入口保留。
- `frontend/src/api/webAgent.ts`、`frontend/src/views/SharedModelSettingsView.vue`、`frontend/src/App.vue`：仅管理员且网页助手开启时显示“公共模型设置”，密码输入框不回填，保存成功后清空输入。清除按钮说明环境变量后备行为；余额由用户主动查询。
- `frontend/src/components/FloatingWebAgent.vue`：打开设置时刷新配置，让已打开的助手获得公共模型可用状态。

## 验证重点

- 未登录 401，普通/受信任用户管理与余额请求 403；MCP Bearer 不代替 Cookie。
- 配置响应不含 Key；其他用户可用公共模型但无法读出 Key。
- 保存、替换、清除分别影响后续聊天使用的真实 Key；个人来源仍使用个人 Key。
- 余额使用相同的有效 Key，供应商使用 mock，不产生外部调用。
- 在已有 0001 数据上 upgrade 0002 不丢记录，模型与迁移一致。

## 任务

- [x] 在现有 Agent 测试文件加入公共配置核心行为用例，运行并确认失败。
- [x] 实现存储、0002、应用服务和 HTTP 管理入口，适配已有迁移检查。
- [x] 实现管理员页面、导航和助手配置刷新，同步说明。
- [x] 集中运行相关 Agent/迁移检查、前端构建和差异检查；UI 最多截图，不点击或填表。
- [x] 复核权限与 Key 流向，报告实际结果和未验证项。

验证：相关检查 46 passed；前端构建通过，保留原主 chunk 体积提示。桌面/手机截图无错误或横向溢出。测试库升级前备份为 `.runtime/backups/fgas_test-20261029-pre-0002-shared-settings.dump`。未调用真实供应商、未自动交互、未改日常库或发布。
