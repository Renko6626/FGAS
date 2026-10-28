# FGAS 的 Actions 与 Coolify 发布

用户于 2026-10-28 确认重新接入现有 Coolify，选择 GitHub Actions 构建镜像，发布交给 Coolify。源码构建方案较省配置，但占用 VPS 构建资源；本次采用用户选定的 CI 镜像方案，使用 Coolify 全局已配置的阿里云 ACR。域名为 `fgas.secret-sealing.club`，首位管理员用户名 `Renko_1055`，首次使用空库。

- Actions 沿用 `v*` 标签与手动触发、现有前端构建和容器检查，通过后发布精确版本的 API/web 镜像，再更新 Coolify 镜像变量与源码提交并触发部署。普通 push 不发布。
- Coolify 使用 Git Compose，保留仓库以执行部署脚本，关闭 Git push 和预览自动部署。仅 web 的 80 端口接入现有 Traefik；API、PostgreSQL 不映射公网端口。
- 沿用 PostgreSQL 14、现有三服务和一次性 migrate。发布脚本先拉镜像、启动数据库，已有表时备份到 `/data/fgas-backups`，再显式执行 Alembic 迁移，最后更新应用并等待健康检查。沿用备份保留 30 天，不增加自动恢复或自动降级。
- 新库由 Alembic 创建，不复制本地开发数据，不创建开发用户。管理员由首次 Casdoor 登录绑定。
- 本机 `.env` 的 `FGAS_CASDOOR_KEY` → 运行时 `CASDOOR_CLIENT_ID`；`FGAS_CASDOOR_SECRET` → `CASDOOR_CLIENT_SECRET`。不使用认证系统管理用的 `CASDOOR_KEY`、`CASDOOR_SECRET`。issuer 为 `https://auth.fantasyguide.cn`，回调为 `https://fgas.secret-sealing.club/api/auth/casdoor/callback`，`COOKIE_SECURE=true`。
- 密钥保存于 Coolify/GitHub Secrets，不进入 Git、镜像或日志。用户已选择沿用阿里云 ACR 私有镜像和平台已有登录配置；CI 推送凭据保存在 GitHub Secrets。
- 验证限于现有构建、容器检查和部署后的只读检查；不执行浏览器自动点击、填表，不写业务记录，不扩大永久测试或 CI 范围。
