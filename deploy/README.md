# 部署 FGAS

推荐使用 Docker Compose。服务器只需 Docker Engine、Compose 插件和 SSH，不需要安装 Python、Node、uv、PM2，也不用手工维护虚拟环境。前端镜像已经包含 Nginx，网页、API 和 MCP 共用一个入口。

有两种交付方式，启动和配置完全相同：

| 方式 | 在哪里构建 | 怎么送到服务器 |
| --- | --- | --- |
| 手动发布 | 本机 | SSH 传完整镜像包，服务器加载后启动 |
| GitHub 自动发布 | GitHub Actions | 镜像放 GHCR，服务器拉取后启动 |

目前仅支持 Linux amd64。Python 依赖在构建镜像时用现有 requirements.txt 安装，服务器不会现场执行 pip 或 uv。手动镜像包还包含 PostgreSQL，目标机无需访问镜像仓库；第一次在本机构建仍需联网下载基础镜像和依赖。

登录支持两种模式：本地试用可把 `AUTH_MODE` 设为 `development` 使用账号选择；正式部署默认 `casdoor`，通过既有 Casdoor OIDC 登录。先在 Casdoor 为本系统建立应用，回调地址与 `CASDOOR_REDIRECT_URI` 完全一致，scope 默认 `openid profile email`；再在 `.env` 填写 client id/secret 和 `INITIAL_ADMIN_SUBJECT`。首次登录自动建立本地用户，默认普通用户；初始管理员只按首次登录的 Casdoor `sub` 或用户名绑定一次，之后角色由本系统管理员维护。默认入口是服务器的 `127.0.0.1:8080`，不直接开放公网；正式公网仍需域名、HTTPS 和真实 Casdoor 联调验收。原生部署步骤保留在 [README.native.md](README.native.md)。

不要复用仓库或本机其他工具里的 `CASDOOR_KEY` / `CASDOOR_SECRET`；FGAS 只读取下文的 `CASDOOR_CLIENT_ID` / `CASDOOR_CLIENT_SECRET`。`CASDOOR_REDIRECT_URI` 必须与 Casdoor 应用登记值完全一致，否则登录回调会被拒绝。

## 第一次准备服务器

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

**`--init-db` 只用于确认过的新 FGAS 数据库**，创建表和初始目录，不带清库参数。日常更新换一个版本号，去掉它：

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

手动运行工作流时，勾选 **Deploy to the configured server after publishing** 也会部署，不要求 `DEPLOY_ENABLED=true`。未勾选且未启用标签自动部署时，只构建和发布，不连接服务器。自动部署始终不初始化数据库、不执行升级 SQL。

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

健康接口只检查数据库可连接，不能证明已有库结构已升级。数据库结构变化按版本说明先备份、单独执行 SQL，普通更新不负责迁移。从开发库升级到本版本需先备份、停服务并确认目标库，再显式执行 [scripts/upgrade-user-auth.sql](../scripts/upgrade-user-auth.sql)，为 `users` 和 `login_sessions` 增加 SSO、时间与到期字段；本版本的截止余额查询还需要 [scripts/upgrade-posted-at.sql](../scripts/upgrade-posted-at.sql)，为 `transfers` 增加 `posted_at`、回填过账时间并创建索引；正式新库由 metadata 建表，不需要执行。发布目录和镜像不会自动清理；确认不用后手动清理旧文件，数据库备份与恢复仍由维护者负责。

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
