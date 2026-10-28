# FGAS Coolify 发布实施计划

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用 GitHub Actions 构建镜像，并由现有 Coolify 发布 FGAS。

**Architecture:** 沿用 GitHub Actions、阿里云 ACR、Docker Compose 与 Alembic；把服务器更新步骤从 SSH 发布包替换为 Coolify API。Coolify 通过自定义启动脚本保留备份、迁移与健康检查顺序。

**Tech Stack:** 现有 Python、Vue、PostgreSQL 14、GitHub Actions、Coolify。

**Spec:** `docs/superpowers/specs/2026-10-28-coolify-actions-design.md`

## Global Constraints

- 域名 `fgas.secret-sealing.club`，首位管理员 `Renko_1055`，全新数据库。
- 仅使用本机 FGAS 专用 Casdoor 凭据，不读取认证系统管理凭据用于 FGAS 登录。
- 不触碰其他项目、开发库或公网代理主配置；不引入自动恢复、回退或额外测试框架。
- 验证使用已有检查；不执行浏览器交互或生产业务写入。

## Review Focus

- 新库必须走 Alembic，不注入开发用户。
- 后续发布必须在迁移前备份，迁移失败不启动新版 API。
- API/web/migrate 必须引用同一次构建的精确镜像版本；Coolify 源码提交与该构建一致。
- 运行时密钥不出现在构建参数、镜像、Git 或日志。
- Coolify 使用自己生成的 Compose，保留平台网络、路由和项目名。

### Task 1: 接入配置与发布脚本

**Files:** 创建 `docker-compose.coolify.yml`、`deploy/apply-coolify.sh`、`scripts/deploy-coolify.py`；调整 `.github/workflows/release.yml`、`deploy/README.md` 及当前状态导航。

- [x] 添加 Coolify Compose 和备份/迁移/启动脚本，复用现有服务配置与健康探针。
- [x] Actions 通过 Coolify API 更新精确镜像引用、源码提交，触发并等待发布结果；移除该工作流的 SSH 更新步骤。
- [x] 更新部署文档，明确凭据来源、首发与后续发布操作。
- [x] 运行 `bash -n`、Python 编译检查、Compose 配置检查、`git diff --check`；不新增永久测试。

### Task 2: 平台接入、构建与首发

**Interfaces:** 消费 Task 1 的 Compose、启动脚本与 CI；平台变量使用 `FGAS_API_IMAGE` 和 `FGAS_WEB_IMAGE`。

- [x] 创建 FGAS 项目/应用，设置域名、自定义启动命令、持久化与运行时变量；关闭 push/预览自动部署。
- [x] 配置专用 CI 部署凭据及镜像访问方式；不输出凭据。
- [ ] 提交并推送已验证的配置；运行现有 Actions 构建和容器检查，再首发到 Coolify。
- [ ] 只读检查容器健康、schema、空业务数据、HTTPS、SSO 重定向和 MCP 未认证响应，记录实际结果及未验收项。

## 执行记录

- 初始工作区干净；实现使用 `deploy/coolify-actions-20261028` 分支。用户已确认技术路线，本计划仅落实该路线，不重复请求部署架构确认。
- 本机只核对 FGAS 专用凭据存在；DNS 公共查询已指向 `47.94.44.152`；Coolify 4.5.0 可用，GitHub App 可访问仓库。

- Task 1 检查通过：shell 语法、Python 编译、工作流 YAML/内嵌 shell、占位凭据下的 Compose config、实际生成 ACR 小发布包并校验镜像引用；独立只读审阅无阻塞项。未新增永久测试，构建和容器检查由现有 Actions 执行。
- ACR 的 `renko/fgas-api` 与 `renko/fgas` 已存在，平台全局登录有效；CI 使用同一 ACR 登录，专用 Coolify read/write/deploy token 有效期 365 天，值不记录。
