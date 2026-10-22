# 部署 FGAS

推荐使用 Docker Compose。服务器只需 Docker Engine、Compose 插件和 SSH，不需要安装 Python、Node、uv、PM2，也不用手工维护虚拟环境。前端镜像已经包含 Nginx，网页、API 和 MCP 共用一个入口。

可通过以下方式交付；Coolify 使用独立的 Compose 和变量模板：

| 方式 | 在哪里构建 | 怎么送到服务器 |
| --- | --- | --- |
| 手动发布 | 本机 | SSH 传完整镜像包，服务器加载后启动 |
| GitHub 自动发布 | GitHub Actions | 镜像放 GHCR，服务器拉取后启动 |
| Coolify | 本机 | 镜像放 ACR，Coolify 读取 Git 中的 Compose 并拉取镜像 |

目前仅支持 Linux amd64。Python 依赖在构建镜像时用现有 requirements.txt 安装，服务器不会现场执行 pip 或 uv。手动镜像包还包含 PostgreSQL，目标机无需访问镜像仓库；第一次在本机构建仍需联网下载基础镜像和依赖。

登录支持两种模式：本地试用可把 `AUTH_MODE` 设为 `development` 使用账号选择；正式部署默认 `casdoor`，通过既有 Casdoor OIDC 登录。先在 Casdoor 为本系统建立应用，回调地址与 `CASDOOR_REDIRECT_URI` 完全一致，scope 默认 `openid profile email`；再在 `.env` 填写 client id/secret 和 `INITIAL_ADMIN_SUBJECT`。首次登录自动建立本地用户，默认普通用户；初始管理员只按首次登录的 Casdoor `sub` 或用户名绑定一次，之后角色由本系统管理员维护。默认入口是服务器的 `127.0.0.1:8080`，不直接开放公网；正式公网仍需域名、HTTPS 和真实 Casdoor 联调验收。原生部署步骤保留在 [README.native.md](README.native.md)。

不要复用仓库或本机其他工具里的 `CASDOOR_KEY` / `CASDOOR_SECRET`；FGAS 只读取下文的 `CASDOOR_CLIENT_ID` / `CASDOOR_CLIENT_SECRET`。`CASDOOR_REDIRECT_URI` 必须与 Casdoor 应用登记值完全一致，否则登录回调会被拒绝。

## Coolify：ACR 镜像部署

使用 [compose.coolify.yaml](compose.coolify.yaml) 和 [coolify.env.example](coolify.env.example)。本节独立于后面的 SSH 发布流程，不使用 `/opt/fgas`、固定 Compose 项目名或 `apply-release.sh`。

1. 本机登录 ACR，选择一个新的版本号，构建并上传前后端镜像：

   ```bash
   docker login crpi-bug4nt14ryr5n8sw.cn-beijing.personal.cr.aliyuncs.com
   bash scripts/push-acr.sh coolify-20261022-1
   ```

   脚本成功后输出 `FGAS_API_IMAGE` 和 `FGAS_WEB_IMAGE`。每次发布使用新版本号，两份镜像应来自同一版本源码。

2. 在部署服务器上，以 Coolify 实际使用的 SSH 用户登录同一个 ACR。当前服务器使用 root。准备备份目录：

   ```bash
   docker login crpi-bug4nt14ryr5n8sw.cn-beijing.personal.cr.aliyuncs.com
   install -d -m 700 /data/fgas-backups
   ```

3. 在 Coolify 创建项目和 production 环境，通过 GitHub App 选择本仓库的部署分支，构建方式选择 Docker Compose。Base Directory 为 `/`，Docker Compose Location 为 `/deploy/compose.coolify.yaml`。保存并加载 Compose，首次保持 Auto Deploy 关闭、Raw Compose Deployment 关闭。

4. 在 Environment Variables 中填写变量模板的内容。两个镜像变量使用步骤 1 的完整地址；`POSTGRES_PASSWORD` 使用 `openssl rand -hex 24` 生成的十六进制密码；Casdoor Client ID、Client Secret 和初始管理员 subject 使用 FGAS 应用的实际值。正式站点保持 `AUTH_MODE=casdoor` 和 `COOKIE_SECURE=true`。真实凭据仅存入 Coolify，不提交到 Git。

5. 为 `web` 服务添加 HTTPS 域名，内部端口为 `80`，路径留空。例如 `https://fgas.secret-sealing.club:80`，其对应回调为 `https://fgas.secret-sealing.club/api/auth/casdoor/callback`，必须先登记到 Casdoor 应用。`api` 和 `db` 不配置公网域名或宿主端口。Coolify 生成代理路由和证书，现有宿主 Nginx 无需修改。

6. 点击 Deploy，检查 `db` 健康、`backup` 和 `migrate` 退出码为 0、`api` 和 `web` 健康。新库由 Alembic 建表，Casdoor 首次登录建立用户，不导入开发示例账号和账户。之后手动登录确认管理员身份。

Compose 默认使用 PostgreSQL 17，数据库保存在 Coolify 为该资源管理的数据卷。不要直接挂载其他主版本的数据卷，也不要删除资源的数据卷。Docker Hub 无法拉取时，可把相同主版本的 PostgreSQL 镜像同步到 ACR，再设置 `FGAS_DB_IMAGE`。

发布新版本时，先构建上传，再同时更新两个镜像变量并部署。后端镜像地址变化会重建 `backup` 和 `migrate` 一次性任务：已有数据库先备份到 `/data/fgas-backups`，保留约 30 天，再迁移；全新空库跳过初始备份。迁移失败会阻止新 API 启动，同机备份不代表异机备份或恢复已验收。

Git 来源用于读取 Compose；这份文件只有 `image`，不会在 VPS 构建源码。现有 GitHub Actions 工作流仍使用 GHCR 和可选 SSH 发布，未接通 ACR/Coolify 自动发布，使用 Coolify 时保持旧 SSH 自动部署关闭。

参考：[Coolify Compose](https://coolify.io/docs/applications/builds/docker-compose)、[域名与容器端口](https://coolify.io/docs/core/networking/domains)。

## SSH 发布：第一次准备服务器

下面统一使用 `/opt/fgas`。部署用户需要能创建这个目录、通过 SSH 登录，并运行 `docker` 和 `docker compose`。建议使用 Compose v2.24 或更新版本；先确认：

```bash
docker info
docker compose version
mkdir -p /opt/fgas
```

把仓库中的 [env.example](env.example) 复制为服务器上的 `/opt/fgas/.env`，限制权限，再编辑：

```bash
chmod 600 /opt/fgas/.env
openssl rand -hex 24
```

将生成的十六进制密码填到 `POSTGRES_PASSWORD=` 后，补全 Casdoor 配置：

- `AUTH_MODE` 保持 `casdoor`。
- `CASDOOR_REDIRECT_URI` 填与 Casdoor 应用登记完全一致的地址，例如 `https://你的域名/api/auth/casdoor/callback`。
- 填写 `CASDOOR_CLIENT_ID`、`CASDOOR_CLIENT_SECRET`。
- `INITIAL_ADMIN_SUBJECT` 填第一个管理员的 Casdoor `sub`（优先）或用户名。
- HTTPS 站点把 `COOKIE_SECURE` 改为 `true`。

密码用十六进制字符，避免数据库 URL 中的特殊字符问题。不要把真实 `.env` 提交到仓库或放进发布包。如果忘了准备，首次执行发布脚本会创建模板并停下，填好后重试即可；Casdoor 必填项缺失时后端会拒绝启动，错误只指出变量名。

配置保存在部署根目录，后续发布不会覆盖。数据库创建后，再改 `.env` 的密码不会修改库内密码；需要另行操作数据库，平时保持不变。

## 手动发布：本机打包，SSH 传过去

在本机项目根目录执行，用一个没用过的版本号：

```bash
bash scripts/package-release.sh manual-20261022-1
bash scripts/push-release.sh .releases/fgas-manual-20261022-1.tar.gz deploy@你的服务器 /opt/fgas --init-db
```

第一条构建前后端镜像，连同 PostgreSQL 导出为 `.releases/fgas-版本号.tar.gz`。包内只有镜像、Compose 和启动配置模板，没有真实密码或业务数据。第二条通过 SCP 传包、解压，并调用服务器上的启动脚本；SSH 密钥、端口等使用本机常规 SSH 配置。

**`--init-db` 只用于确认过的新 FGAS 数据库**：先执行 Compose migrate 建表，再由 initialize 写入初始目录，不带清库参数。日常更新换一个版本号，去掉它；普通更新也会自动备份并迁移：

```bash
bash scripts/package-release.sh manual-20261023-1
bash scripts/push-release.sh .releases/fgas-manual-20261023-1.tar.gz deploy@你的服务器 /opt/fgas
```

发布目录保存在 `/opt/fgas/releases/fgas-版本号/`。路径仅支持字母、数字、下划线、连字符、点和斜杠，不能含空格或 `..`。同一版本号不要重复用于不同内容。传输或启动失败时，先查看输出和日志，修好后可重跑；脚本不自动回退。

也可以自己用 SCP 传输，在服务器解压到上述 releases 目录，再执行：

```bash
bash /opt/fgas/releases/fgas-版本号/apply-release.sh --init-db
```

## GitHub Actions：构建、发布 GHCR、按需更新服务器

工作流在 [.github/workflows/release.yml](../.github/workflows/release.yml)。推送 `v*` 版本标签或在 Actions 页面手动运行 **Build and deploy** 时触发，普通提交不发布。

每次运行会：

1. 构建 amd64 前后端镜像，前端构建同时执行现有类型检查。
2. 在 runner 的临时数据库上初始化并启动容器，检查 Nginx 提供的网页、指南、API 健康接口和 MCP 未认证响应。
3. 推送镜像到 `ghcr.io/仓库所有者/仓库名-api` 和 `…-web`，标签含提交 SHA、运行编号及重试编号，不覆盖旧发布。
4. 上传名为 `fgas-release` 的小发布包。这里没有镜像，服务器启动时会拉取 GHCR 镜像及 PostgreSQL。

GHCR 发布使用工作流自带的 `GITHUB_TOKEN`，已声明 `packages: write`。仓库或组织若禁用了包发布，需要先允许。第一次发布的包通常是私有的；若保持私有，在服务器上以实际部署用户登录一次：

```bash
docker login ghcr.io -u 你的GitHub用户名
```

密码输入有对应包读取权限的 PAT classic（`read:packages`），不要填 GitHub 登录密码，也不要把令牌写进 `.env`。如果主动把镜像包设为公开，拉取无需登录。[GitHub 的 GHCR 权限说明](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

### 第一次从 GHCR 部署

先运行一次工作流，不勾选部署。从运行页面下载 `fgas-release` artifact，解开 GitHub 外层 ZIP 后得到 `fgas-版本号.tar.gz`。用同一个传包脚本发布它：

```bash
bash scripts/push-release.sh /下载目录/fgas-版本号.tar.gz deploy@你的服务器 /opt/fgas --init-db
```

脚本会识别包中没有 images.tar，改为拉取镜像。确认服务正常后，再启用后续自动更新。

### 启用 SSH 自动更新

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 配置：

| 类型 | 名称 | 内容 |
| --- | --- | --- |
| Secret | `DEPLOY_HOST` | 服务器主机名或 IPv4 地址 |
| Secret | `DEPLOY_USER` | 运行 Docker 的 SSH 用户 |
| Secret | `DEPLOY_SSH_KEY` | 专用部署私钥，无交互口令；对应公钥已加入服务器 authorized_keys |
| Secret | `DEPLOY_KNOWN_HOSTS` | 经可信渠道核对的服务器 SSH 主机公钥记录 |
| Variable | `DEPLOY_PATH` | `/opt/fgas`，与首次部署保持一致 |
| Variable | `DEPLOY_ENABLED` | 填 `true` 后，推送 `v*` 标签会自动更新服务器 |

不要关闭 SSH 主机校验。`DEPLOY_KNOWN_HOSTS` 使用完整 known_hosts 行；可以采集后通过服务器控制台核对指纹，再填入。GitHub runner 必须能连接目标机默认 SSH 端口 22；只在内网可达的服务器先用手动方式。

手动运行工作流时，勾选 **Deploy to the configured server after publishing** 也会部署，不要求 `DEPLOY_ENABLED=true`。未勾选且未启用标签自动部署时，只构建和发布，不连接服务器。自动部署会先备份数据库，再运行 Compose 一次性 `migrate` 服务；迁移失败时不会启动新 API。

工作流提交到默认分支后才能从 Actions 页面手动运行。这里仅准备配置，没有替你创建 Secrets、推送版本标签或执行远程部署。

## 访问、日志和维护

服务器本机检查：

```bash
curl --fail http://127.0.0.1:8080/api/health
curl --fail http://127.0.0.1:8080/agent-setup.md
```

从自己的电脑临时访问，可以开 SSH 隧道：

```bash
ssh -L 8080:127.0.0.1:8080 deploy@你的服务器
```

然后打开 `http://127.0.0.1:8080`。网页里的 Agent 指南使用同源 `/mcp`；另一台电脑连接时也需要能访问这个入口。Nginx 配置已包含 SPA 回退、API 转发、MCP Authorization 透传和关闭响应缓冲，无需另外安装服务器 Nginx。域名、HTTPS 和真实 Casdoor 联调留待实际站点确定后配置；HTTPS 时在 `.env` 设置 `COOKIE_SECURE=true`，并用同一 HTTPS 域名作为 `CASDOOR_REDIRECT_URI`。

Casdoor 侧退出不会撤销 FGAS 已有网页会话。管理员可在“用户权限”中停用用户或强制下线；停用会同时撤销网页会话并阻止 Agent 继续访问，强制下线只撤销网页会话，不撤销 MCP 凭据。最后一名启用管理员不能被降级或停用。

查看当前容器及日志，不需要记住发布版本：

```bash
docker ps --filter label=com.docker.compose.project=fgas
docker logs --tail 100 fgas-api-1
docker logs --tail 100 fgas-web-1
```

需要使用 Compose 操作时，指定实际发布目录及同一份配置：

```bash
cd /opt/fgas/releases/fgas-版本号
docker compose --env-file /opt/fgas/.env --env-file release.env -f compose.yaml ps
```

固定项目名为 `fgas`，数据库保存在 `fgas_postgres-data` 卷，替换镜像和普通 `down` 不删除它。**不要执行 `down -v`、删除该卷，或对正式数据库运行测试脚本。** 已有其他 Compose 项目的数据卷不会自动迁移过来；接手旧环境先核对卷名、数据库和版本。

健康接口只检查数据库可连接，不能证明 schema 已升级。`apply-release.sh` 在每次更新前把数据库备份到 `/opt/fgas/backups`（`pg_dump -Fc`，保留 30 天），再执行一次性 `migrate` 服务（`alembic upgrade head`）；迁移失败会中止发布，不自动降级。手工 `docker compose up` 可能复用已退出的 one-shot 容器，更新前应显式执行 `docker compose run --rm migrate`，数据重要时先备份。

基线前旧库的收养路径：备份 → 执行 [upgrade-agent-access.sql](../scripts/upgrade-agent-access.sql)、[upgrade-user-auth.sql](../scripts/upgrade-user-auth.sql)、[upgrade-posted-at.sql](../scripts/upgrade-posted-at.sql) → 校验 schema → `alembic stamp 0001`。可丢弃的旧库直接重建即可。发布目录和镜像不会自动清理；确认不用后手动清理旧文件，数据库备份与恢复仍由维护者负责。

## 可选：在服务器从源码构建

网络和机器资源允许时，也可在源码目录直接构建。不必另写 Dockerfile：

```bash
cp deploy/env.example deploy/.env
# 编辑 deploy/.env，填写数据库密码
chmod 600 deploy/.env
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.build.yaml build
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.build.yaml up -d db
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.build.yaml run --rm api python -m backend.application.initialize
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.build.yaml up -d --wait
```

初始化命令仍只用于首次新库。这条方式需要服务器访问依赖源，并在服务器完成前端与 Python 镜像构建；资源较少或网络不稳时优先传完整镜像包。同一台机器上的源码方式和发布包方式共用 `fgas` 项目名及数据卷，不要当作两套独立环境同时启动。
