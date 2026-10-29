# 部署 FGAS

推荐使用 Docker Compose。服务器只需 Docker Engine、Compose 插件和 SSH，不需要安装 Python、Node、uv、PM2，也不用手工维护虚拟环境。前端镜像已经包含 Nginx，网页、API 和 MCP 共用一个入口。

部署路线的定位如下，其他文档沿用此表：

| 路线 | 定位 | 适用情况 |
| --- | --- | --- |
| Coolify + GitHub Actions | 当前正式路线 | Actions 构建 ACR 镜像，Coolify 管理 Compose、域名和持久化 |
| Docker Compose / SSH | 手动备选 | 本机打包后传给独立服务器，不与 Coolify 管理同一实例 |
| systemd 原生部署 | 替代 | 明确不使用 Docker，按 [原生部署说明](README.native.md)维护主机依赖和服务 |
| PM2 | 保留的兼容备选 | 继续维护既有 PM2 环境；新原生部署优先 systemd |

`scripts/push-acr.sh` 是保留的手动镜像上传工具，不是第四套部署流程；当前自动发布使用阿里云 ACR。不要同时用 Compose、systemd 或 PM2 启动同一实例。

有两种交付方式，启动和配置完全相同：

| 方式 | 在哪里构建 | 怎么送到服务器 |
| --- | --- | --- |
| 手动发布 | 本机 | SSH 传完整镜像包，服务器加载后启动 |
| GitHub 自动发布 | GitHub Actions | 镜像放 ACR，Coolify 拉取后部署 |

目前仅支持 Linux amd64。Python 依赖在构建镜像时使用 `backend/requirements-agent.txt` 安装，包含基础服务和已验证的网页助手依赖；服务器不会现场执行 pip 或 uv。手动镜像包还包含 PostgreSQL，目标机无需访问镜像仓库；第一次在本机构建仍需联网下载基础镜像和依赖。

登录支持两种模式：本地试用可把 `AUTH_MODE` 设为 `development` 使用账号选择；正式部署默认 `casdoor`，通过既有 Casdoor OIDC 登录。先在 Casdoor 为本系统建立应用，回调地址与 `CASDOOR_REDIRECT_URI` 完全一致，scope 默认 `openid profile email`；再在 `.env` 填写 client id/secret 和 `INITIAL_ADMIN_SUBJECT`。首次登录自动建立本地用户，默认普通用户；初始管理员只按首次登录的 Casdoor `sub` 或用户名绑定一次，之后角色由本系统管理员维护。独立手动路线的默认入口是服务器的 `127.0.0.1:8080`；当前 Coolify 站点已完成 HTTPS 与登录跳转检查，真实用户登录仍需验收。原生 systemd 部署步骤见 [README.native.md](README.native.md)，PM2 作为备选保留。

当前线上 Casdoor 的 FGAS 应用已通过 `fgas-member` 标签限制普通账号登录，并关闭该应用注册及游客登录。成员开通、停用及现有会话的处理见 [Casdoor 成员准入](../docs/casdoor-membership.md)。FGAS 角色仍由本系统维护，未增加网站侧标签校验。

不要复用仓库或本机其他工具里的 `CASDOOR_KEY` / `CASDOOR_SECRET`；FGAS 只读取下文的 `CASDOOR_CLIENT_ID` / `CASDOOR_CLIENT_SECRET`。`CASDOOR_REDIRECT_URI` 必须与 Casdoor 应用登记值完全一致，否则登录回调会被拒绝。

## 第一次准备服务器

本节是独立 Compose/SSH 手动路线，Coolify 路线跳到后面的专节。下面统一使用 `/opt/fgas`。部署用户需要能创建这个目录、通过 SSH 登录，并运行 `docker` 和 `docker compose`。建议使用 Compose v2.24 或更新版本；先确认：

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

## GitHub Actions 与 Coolify

当前正式站点为 `https://fgas.secret-sealing.club`。工作流在 [.github/workflows/release.yml](../.github/workflows/release.yml)，推送 `v*` 标签或手动运行 **Build and deploy** 时触发，普通 push 不发布。Actions 构建 amd64 API/web 镜像，执行原有前端类型检查和容器/Nginx/API/MCP 基础检查，通过后推送阿里云 ACR。镜像标签包含完整提交 SHA、运行编号与重试编号，不覆盖旧版本。

仓库 Actions 配置：

| 类型 | 名称 | 用途 |
| --- | --- | --- |
| Variable | `ACR_REGISTRY` | ACR 实例域名 |
| Variable | `ACR_NAMESPACE` | 命名空间，当前为 `renko` |
| Secret | `ACR_USERNAME` / `ACR_PASSWORD` | Actions 推送镜像 |
| Secret | `COOLIFY_API_TOKEN` | CI 专用 Coolify read/write/deploy 凭据 |
| Variable | `COOLIFY_APPLICATION_UUID` | FGAS 应用 UUID |
| Variable | `DEPLOY_ENABLED` | 为 `true` 时，推送版本标签会部署 |

手动运行勾选部署也会更新服务器，不要求 `DEPLOY_ENABLED=true`。不勾选则只构建和发布镜像。CI 使用 `scripts/deploy-coolify.py` 更新 `FGAS_API_IMAGE`、`FGAS_WEB_IMAGE` 与源码提交，再触发 Coolify，并等待其部署结果。GitHub Secrets 不放 Casdoor 或数据库密码。

Coolify 使用 Git Compose 应用，GitHub App `renko6626`，仓库 `Renko6626/FGAS`，配置文件 `/docker-compose.coolify.yml`。关闭平台的 push 自动部署和预览部署，避免绕过 CI。开启 **Preserve Repository**，Custom Build Command 为 `true`，Custom Start Command 为：

```bash
bash deploy/apply-coolify.sh
```

当前应用为 `j6grshmlx7t0lxyrwhe7mlmk`，可从 [Coolify 应用配置](https://coolify.secret-sealing.club/project/fsj7tn8gqtnhlmlqrnws4u0i/environment/wr3ynnxmxkkcxibfk7xuu9ft/application/j6grshmlx7t0lxyrwhe7mlmk) 维护。web 绑定上述 HTTPS 域名，内部端口 80；API 和数据库不映射宿主机端口。全局 ACR 登录负责拉取镜像。平台保留的仓库用于运行部署脚本，脚本使用 Coolify 生成的 Compose、`.env` 和项目名，不另建一套容器。

运行时变量在 Coolify 配置：`POSTGRES_PASSWORD`、`CASDOOR_ISSUER`、`CASDOOR_CLIENT_ID`、`CASDOOR_CLIENT_SECRET`、`CASDOOR_REDIRECT_URI`、`INITIAL_ADMIN_SUBJECT`，以及 CI 管理的两个镜像变量。会话 Cookie 固定为 Secure，登录模式固定为 Casdoor。

网页助手在 Coolify Compose 默认启用；设 `FGAS_WEB_AGENT_PROTOTYPE=0` 可关闭。容器内 MCP 固定连接本机 `http://127.0.0.1:10622/mcp`，不沿用开发预览端口。管理员登录后从“基础资料 → 公共模型设置”配置社团 DeepSeek Key；Key 不进入镜像或 GitHub Secrets。数据库配置优先，`FGAS_DEEPSEEK_API_KEY` 可作后备；没有公共 Key 时成员仍可填写个人 Key。公共设置表由 Alembic `0002` 在迁移前备份后建立。Nginx 对聊天 SSE 关闭缓冲并允许 300 秒上游静默时间；其他 API 沿用原配置。独立手动 Compose 默认关闭助手，可在 `.env` 设置 `FGAS_WEB_AGENT_PROTOTYPE=1` 开启。

本次凭据来源是本机 `.env` 的 `FGAS_CASDOOR_KEY` → `CASDOOR_CLIENT_ID`、`FGAS_CASDOOR_SECRET` → `CASDOOR_CLIENT_SECRET`。不要使用认证系统管理 API 的 `CASDOOR_KEY` / `CASDOOR_SECRET`。issuer 为 `https://auth.fantasyguide.cn`，回调为 `https://fgas.secret-sealing.club/api/auth/casdoor/callback`，首位管理员用户名为 `Renko_1055`。Casdoor 应用必须登记该回调。

首发使用新空库，Alembic 建表，不导入开发记录或创建开发用户；首次真实登录时绑定管理员。后续发布在迁移前备份到宿主机 `/data/fgas-backups`（目录 0700，文件 0600，保留 30 天），检查备份归档可读后执行迁移，失败停止发布，不自动恢复或降级。不要在面板中移除自定义启动命令，否则会绕过备份步骤。

现有 Traefik 为兼容旧站开启了 ACME bypass，FGAS 的证书验证需保留专用 HTTP 路由：[fgas-acme.yaml](fgas-acme.yaml) 对应 VPS `/data/coolify/proxy/dynamic/fgas-acme.yaml`。它仅将当前域名的 `/.well-known/acme-challenge/` 转给 `acme-http@internal`，避免验证请求被 HTTPS 跳转截获；无需修改主代理或重启。

数据库使用应用自己的 `postgres-data` 持久卷（当前实际名 `j6grshmlx7t0lxyrwhe7mlmk_postgres-data`）；从 Coolify 删除资源时不要删除该卷。日志和容器状态以应用面板为准。Compose/SSH 的 `/opt/fgas`、回环 8080 和固定 `fgas` 项目名仅适用于下方保留的手动路线，不用于 Coolify 实例。

## 手动 Compose 的访问、日志和维护

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

健康接口还会返回 `version` 和 `git_sha`。手动发布包会将指定版本号和当前 Git 提交写入后端镜像，GitHub Actions 则写入镜像版本号和构建提交；`git_sha` 显示前 12 位。从源码构建时，可在构建前导出 `FGAS_VERSION` 和 `FGAS_GIT_SHA`（例如 `export FGAS_VERSION=local FGAS_GIT_SHA="$(git rev-parse HEAD)"`）。没有 Git 元数据的源码包需显式提供 `FGAS_GIT_SHA` 才能记录提交号。

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
