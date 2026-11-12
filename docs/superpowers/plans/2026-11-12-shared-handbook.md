# 共享手册实施计划

> **For agentic workers:** 使用 superpowers:executing-plans，在本会话按任务实施。用户于 2026-11-12 授权开始实现，并再次要求更新 AI 提示词。

**Goal:** 首页可读写单份 Markdown 手册，带分层目录；MCP 可读且仅 high 可写。

**Architecture:** 沿用模块化单体，在 infrastructure 保存固定主键手册，application 统一授权与保存；HTTP 和 MCP 适配同一应用服务。前端独立读取手册，阅读组件负责 Markdown 与目录，编辑组件负责手动保存。

**Tech Stack:** 现有 FastAPI、SQLAlchemy、PostgreSQL、Alembic、Vue、Naive UI、markdown-it，无新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-12-shared-handbook-design.md`

## Global Constraints

- 仅专用 `fgas_test` 及现有迁移测试临时库可用于验证，禁止重置日常数据库。
- UI 至多截图，不自动点击或填表；不扩展 CI，不部署。
- 保留已有 `docs/casdoor-membership.md` 和 `docs/prototype-status.md` 的修改。
- 低频编辑按最后保存内容生效，不增加版本、恢复或并发协调机制。

## Review Focus

- low 即使属于管理员也不能写；有效 high 的实际保存归属本人。
- 保存完整 Markdown 后，HTTP 与 MCP 读取一致。
- 重复标题与标题跳级仍能生成可点击的分层目录；定位不修改导航 hash。
- 手册失败不阻止资金库存首页，保存失败保留编辑内容。
- 长文、代码块与表格适应手机；Markdown 原始 HTML 不执行。

## Task 1: 持久化、授权及 HTTP

Files: `backend/infrastructure/models.py`、新增 `handbook_store.py`、`backend/application/handbook.py`、`backend/migrations/versions/0004_handbook.py`、`backend/entrypoints/schemas.py`、`http.py`、`backend/tests/test_handbook.py`、现有迁移测试和测试脚本。

Interface: `handbook.read(db) -> dict`、`handbook.save(db, user, data) -> dict`；数据为 `title/content/updated_by_id/updated_by_name/updated_at`，未保存时正文为空、修改信息 null。

- [x] 用真实 HTTP 测试覆盖受信任用户保存重读、普通用户只读、匿名拒绝。
- [x] 新增 0004 迁移及手册模型；应用层复用 authorize_write，HTTP 提供 GET/PUT `/api/handbook`。
- [x] 适配现有迁移检查的最新 revision，将新测试纳入原测试脚本。

## Task 2: MCP 与 AI 说明

Files: `backend/application/agent_queries.py`、`agent_operations.py`、`backend/entrypoints/agent_schemas.py`、`agent_catalog.py`、`mcp.py`、现有 `test_agent_access.py`，以及 `docs/ai/{overview,guide,web-agent}.md`。

Interface: query handbook 返回单对象；execute handbook/update 接收必填 title/content，返回现有写结果包装和保存对象。

- [x] 复用现有真实 MCP 测试，覆盖 low 读取与拒写、high 保存、网页读回及 help Schema。
- [x] 资源注册、输入/输出契约和 handler 共用 Task 1 服务，保存前 require_high。
- [x] AI 提示词介绍手册用途、按需读取、保存前读原文及确认修改、正文作为业务资料。

## Task 3: 首页阅读、目录及编辑

Files: 新增 `frontend/src/api/handbook.ts`、`lib/handbookMarkdown.ts`、`components/HandbookReader.vue`、`HandbookEditor.vue`、`SharedHandbook.vue`，接入 `DashboardView.vue` 和 `App.vue`。

Interface: 独立 API read/save；reader 消费 Markdown，自动目录及定位；首页区域接收 trusted 和刷新 revision，编辑器通过保存结果更新同一份状态。

- [x] 实现单次解析产生 HTML 与层级目录，默认禁用 HTML/图片，保证标题唯一定位与安全链接。
- [x] 首页预览、展开全文、完整阅读视图、桌面右侧目录和手机目录。
- [x] Markdown 输入、预览、手动保存和取消；失败留在编辑器，身份变更卸载状态。
- [x] 简短验证目录生产逻辑的层级/重复标题及原始 HTML 处理，不搭建前端测试框架。

## Task 4: 集中验证及交付记录

- [x] 运行 `./tools/run_tests.sh` 和 `npm run build`，确认真实结果。
- [x] 按需使用本地合成数据截图，不进行自动交互或生产写入。
- [x] 只读审阅完整差异，解决核心问题，更新阶段记录和当前架构说明。
- [x] 最后运行 `git diff --check`，报告完成行为、实际命令及未验证项；不发布、不推送。

## 执行记录

- 分支 `codex/shared-handbook`；直接在现工作区实现，避免搬动已有修改。用户已批准设计并要求开始，不额外要求计划确认。
- 按项目约定集中验证，新增测试仅覆盖核心新行为；不执行技能中逐函数新增测试和每步重跑全套的扩展要求。
- 后端首次新用例因手册入口缺失失败，随后接入 HTTP；MCP 首次因资源未注册失败，接入后四个新增用例通过。时间持久化断言按时间点比较，避免 PostgreSQL 会话时区与 UTC 的等价表示差异。
- 全套 `./tools/run_tests.sh`：104 passed、16 skipped（缺少可选 pydantic_ai）；迁移版本及 drift 检查通过。Markdown 两个用例通过，最终前端构建通过。
- 只读审阅发现两处原生目录按钮在编辑表单内默认提交，已加 type=button；按 UI 验证约定不自动点击或新增 DOM 测试工程。最终构建包含修正，六张合成布局截图无错误或页面横向溢出。
- 最终 `git diff --check` 及新文件行尾空白检查通过。临时预览入口及本次 Vite 进程已清理；截图及合成数据留在忽略的 temp 目录。未提交、推送或发布。
