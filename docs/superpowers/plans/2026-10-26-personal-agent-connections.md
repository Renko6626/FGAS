# 个人 Agent 连接 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 所有用户可按需创建个人 low 连接，复用统一审批，并同步 AI 接入文档。

**Architecture:** 沿用 User → AgentCredential 与现有业务服务，不新增 AI 用户、角色或审批分支。按用户后续确认，原文保存供本人再次查看，直接同步当前模型与建库基线，不新增迁移、旧密钥兼容或回退。

**Tech Stack:** Python 3.13、FastAPI、SQLAlchemy、PostgreSQL、Vue 3、TypeScript、Naive UI。

**Spec:** `docs/superpowers/specs/2026-10-26-personal-agent-connections-design.md`

## Global Constraints

- 只在 `fgas_test` 运行后端测试；不修改日常数据库。
- 保留现有未提交文档改动，不提交密钥、数据库连接或个人配置。
- 不增加依赖、角色、审批分类或请求恢复机制；新增存储和接口先得到用户选择。
- 不自动点击、填表；前端使用现有类型检查及生产构建。

## Review Focus

- 普通用户只管理自己的连接，不能创建或升级为 high。
- low 不继承所属用户的人工过账权限，统一待审且保留来源。
- 普通用户可进入连接页面；非管理员的权限选择固定 low。
- 用户停用仍阻断所有连接；管理员降级阻断 high，但不阻断 low。
- 接入文档不再要求先取得受信任角色，不承诺网页内运行模型。

### Task 1: 个人 low 权限

**Files:** `backend/application/agent_access.py`、`backend/tests/test_agent_access.py`。

**Interfaces:** 保持现有 list/create/update 及 MCP 接口签名；扩展 low 所属用户至所有有效角色。

- [x] 调整现有签发和待审测试，覆盖普通用户签发、所有权、禁止 high 与停用。
- [x] 显式指定 `fgas_test` 运行目标测试，确认旧权限导致失败。
- [x] 放开 low 签发与解析，保留所有权、有效用户和 high 管理员检查。

### Task 2: 页面与文档

**Files:** `frontend/src/App.vue`、`frontend/src/views/AgentConnectionsView.vue`、`frontend/public/agent-setup.md`、`docs/ai/overview.md`、`docs/ai/guide.md`、`backend/entrypoints/mcp.py`、`README.md`、`architecture.md`、`docs/prototype-status.md`。

**Interfaces:** 继续使用 `/api/agent-credentials`；所有用户可访问页面，默认个人名称及 low。

- [x] 开放导航和页面，默认名称为显示名加“的 AI”，非管理员固定 low；沿用原页面结构。
- [x] 同步身份、签发权限与统一审批说明，更新 AI 指南版本。
- [x] 按已确认的原文保存方案，补齐必填原文列、建库基线、本人查看接口、页面入口；在现有 Agent 测试中覆盖重复读取、本人权限、列表不泄露及 Cookie/Bearer 隔离。
- [x] 集中运行后端相关检查、`npm run build`、`git diff --check`；独立审阅完整改动。
- [x] 将已验证的改动带回用户工作目录，核对原有文件未被并行修改，不自动发布。


### Task 3: 登录响应与事务提交时机（用户后续确认修复）

**Files:** `backend/entrypoints/http.py`、`backend/requirements.txt`、`backend/tests/test_auth_casdoor.py`、`frontend/public/agent-setup.md`。

**Interfaces:** 人工 HTTP 数据库依赖复用同一个 `Depends(database, scope="function")`，提交完成后再发送成功响应。现有 JSON 接口、身份、权限和 MCP 业务事务不变。FastAPI 最低版本收紧至支持该作用域的 `0.121.1`，当前已安装 `0.139.0`，不安装或替换依赖。

- [x] 在真实登录路由发出响应头时，以独立数据库连接核对会话可见性；旧实现稳定失败，新实现通过。
- [x] 将 HTTP 数据库依赖统一设为 function scope，避免登录及其他写入的成功响应早于事务提交。
- [x] 在接入指南说明缺少 MCP 能力时引导启用、配置原生插件或切换支持的客户端/模式，重载后验证，不让模型手写协议代替正常接入。
- [x] 集中运行已有后端检查、前端构建与差异检查，审阅并同步回当前工作目录。
