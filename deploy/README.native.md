# Linux 原生部署：systemd 管后端

本文是明确不使用 Docker 时的替代路线，新部署首选 Compose。完整定位见 [部署路线对照表](README.md)；PM2 仅保留兼容用途，新原生部署优先 systemd。

日常更新按“拉代码 → 按需安装依赖 → 备份并迁移 → 构建 → 重启”处理。后端由 systemd 管理 Uvicorn，前端构建后由服务器上的静态网站服务提供，数据库使用现有 PostgreSQL。仍想用 PM2 时见文末的备选方式。

登录支持 `development` 与 `casdoor` 两种模式。本机或内网试用可用开发账号选择；正式环境使用既有 Casdoor OIDC，需要先在 Casdoor 建立应用并填写回调地址、client id/secret 和初始管理员。真实 Casdoor 联调、域名和 HTTPS 尚未验收。这份文档整理运行和更新方式，不会自动开放网站或安装系统服务。

## 第一次部署

服务器准备好 Python 3.13、Node.js 22 或更新版本、PostgreSQL，以及带 systemd 的 Linux 发行版。下面以 `/srv/fgas` 和专用系统账号 `fgas` 为例；路径或账号不同时，同步修改 [fgas.service](fgas.service)、[fgas-migrate.service](fgas-migrate.service) 和 Nginx 配置。

创建运行账号和目录，用它克隆代码并安装依赖：

```bash
sudo useradd --system --user-group --home-dir /srv/fgas --shell /usr/sbin/nologin fgas
sudo mkdir -p /srv/fgas
sudo chown fgas:fgas /srv/fgas
sudo -u fgas -H git clone <仓库地址> /srv/fgas
sudo -u fgas -H bash -c 'cd /srv/fgas && npm run setup'
```

`npm run setup` 创建项目自己的 `.venv`，安装现有 Python 依赖，再按锁文件安装前端依赖。它不会初始化数据库或启动服务。`python3.13` 和 `npm` 必须在该账号的 `PATH` 中。

准备一个 FGAS 专用的 PostgreSQL 数据库和账号，然后复制配置：

```bash
sudo -u fgas -H bash -c 'cd /srv/fgas && cp .env.example .env && chmod 600 .env'
sudo -u fgas -H vi /srv/fgas/.env
```

编辑 `.env`，把 `DATABASE_URL` 换成实际连接信息。默认后端端口为 `API_PORT=10622`，只监听 `127.0.0.1`。HTTPS 网站使用 `COOKIE_SECURE=true`；本机 HTTP 试用保留 false。`AUTH_MODE` 可选 `development` 或 `casdoor`：`casdoor` 时必须填写 `CASDOOR_ISSUER`、`CASDOOR_CLIENT_ID`、`CASDOOR_CLIENT_SECRET`、与 Casdoor 应用登记完全一致的 `CASDOOR_REDIRECT_URI`，以及用于绑定第一个管理员的 `INITIAL_ADMIN_SUBJECT`（优先填 Casdoor `sub`）。不要复用其他工具的 `CASDOOR_KEY` / `CASDOOR_SECRET`。

systemd 通过 `EnvironmentFile` 读取 `.env`：每行 `KEY=value`，`#` 开头的整行是注释，不做 shell 变量展开，含空格的值要加引号。修改 `.env` 后重启服务即可生效。

**确认连接的是新建的 FGAS 数据库后**，初始化一次：

```bash
sudo -u fgas -H bash -c 'cd /srv/fgas && npm run db:init'
```

初始化使用与后端相同的数据库配置，执行 Alembic 基线迁移并写入初始目录，不带清库参数。`npm run db:init` 只读取项目 `.env`，不要求安装 PM2。不要把其他系统的数据库拿来初始化，也不要在部署时使用 `--reset`、`--reset-db` 或测试脚本。

如果接手的是已有 FGAS 数据库，先查看 `alembic_version` 和更新说明。已有基线版本直接执行 `alembic upgrade head`；没有版本号的旧库需要先备份、执行 [upgrade-agent-access.sql](../scripts/upgrade-agent-access.sql)、[upgrade-user-auth.sql](../scripts/upgrade-user-auth.sql)、[upgrade-posted-at.sql](../scripts/upgrade-posted-at.sql)，校验 schema 后 `alembic stamp 0001`；可丢弃的旧库直接重建。所有操作都要先确认目标库和备份。

构建前端，安装并启动 systemd 服务：

```bash
sudo -u fgas -H bash -c 'cd /srv/fgas && npm run build'
sudo cp /srv/fgas/deploy/fgas.service /srv/fgas/deploy/fgas-migrate.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fgas
systemctl status fgas --no-pager
curl --fail http://127.0.0.1:10622/api/health
```

健康接口应返回 status=ok。检查失败时先看 `journalctl -u fgas -n 100 --no-pager`，修好后再继续；systemd 显示 active 本身不能证明数据库可用。接口还会返回 `version`、`git_sha` 和 `schema_revision`，用于确认部署版本与迁移状态；版本信息可用 `.env` 中的 `FGAS_VERSION`、`FGAS_GIT_SHA` 覆盖，未设置时 `git_sha` 从项目 `.git` 读取。

单元文件默认开启 `ProtectSystem=strict`、`PrivateTmp` 等加固，项目目录对服务只读；后端不需要写文件，日志交给 journald。代码放在家目录时 `ProtectHome=read-only` 仍可读取，若以后新增本地写文件需求，再用 `ReadWritePaths` 精确放行，不要直接关闭整个加固。端口写死在 `ExecStart` 中：修改 `.env` 的 `API_PORT` 时，要同步修改 [fgas.service](fgas.service) 的 `--port` 和 Nginx 配置，然后 `sudo systemctl daemon-reload` 再重启。

## 网页和 MCP 如何对外提供

前端构建产物在 `frontend/dist`。让现有网站服务使用这个目录作为站点根目录，按下面的路径分流：

| 请求 | 处理方式 |
| --- | --- |
| `/`、`/assets/*`、`/agent-setup.md` | 读取 `frontend/dist` 中的文件 |
| `/api/*` | 转发到 `http://127.0.0.1:10622`，保留路径 |
| `/mcp` | 转发到同一个后端，保留路径及 Authorization 请求头 |

无需在服务器上长期运行 Vite 开发服务器。构建后的网页使用同源 `/api`，Agent 接入指南也按同源 `/mcp` 定位服务。

如果服务器已经使用 Nginx，可以把下面的 location 配置放进该站点已有的 server 块。先把 root 换成真实绝对路径；后端端口改过时同步修改 proxy_pass。域名、HTTPS 证书和访问限制沿用服务器的站点配置，本示例不创建或开放新站点。

```nginx
root /实际项目目录/frontend/dist;
index index.html;

location / {
    try_files $uri $uri/ /index.html;
}

location /api/ {
    proxy_pass http://127.0.0.1:10622;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location = /mcp {
    proxy_pass http://127.0.0.1:10622;
    proxy_http_version 1.1;
    proxy_set_header Host $proxy_host;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
}
```

MCP 转发中的 Host 使用本机后端地址，与当前 SDK 的回环 Host 校验相配合。原始 Origin 仍会传入后端；如果以后要从浏览器直接调用 MCP，还需按实际域名配置 SDK 的 Origin 许可，不能靠删除 Origin 或关闭认证绕过。[Nginx 转发头说明](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)

网页打开后，检查 `/agent-setup.md` 能读到 Markdown，登录后的 API 可以访问，再按指南连接 MCP 做一次只读查询。直接打开 `/mcp` 得到401只是说明需要密钥，不是完整的 MCP 验收。

Casdoor 模式下，首次登录会自动建立本地用户并默认为普通用户；只有首次建号时匹配 `INITIAL_ADMIN_SUBJECT` 的用户成为管理员，之后角色由“用户权限”页面维护。管理员可停用用户或强制下线：停用会撤销网页会话并阻止 Agent 访问，强制下线只撤销网页会话，不撤销 MCP 凭据。Casdoor 侧退出不会撤销已有 FGAS 会话。最后一名启用管理员不能被降级或停用。

## 平时更新

没有依赖或数据库结构变化时，在项目目录执行：

```bash
sudo -u fgas -H bash -c 'cd /srv/fgas && git pull --ff-only'
sudo -u fgas -H bash -c 'cd /srv/fgas && npm run build'
sudo systemctl restart fgas
```

一条成功后再执行下一条。构建失败时先查看错误，不要继续重启。这里采用直接更新工作目录的简单方式，构建会更新 `frontend/dist`；更新时选一个没人操作的时间即可。暂不增加发布目录切换或自动回退流程。

如果这次修改了 `backend/requirements.txt`、前端 package.json 或锁文件，在构建前多执行一次 `npm run setup`。遇到数据库结构变更，按下面的顺序先备份、再迁移、后重启：

```bash
# 1. 按现有 PostgreSQL 流程备份，例如 pg_dump -Fc
# 2. 显式执行迁移（一次性 unit）
sudo systemctl start fgas-migrate
# 3. 确认迁移成功后再构建和重启
sudo -u fgas -H bash -c 'cd /srv/fgas && npm run build'
sudo systemctl restart fgas
```

`fgas-migrate` 读取与后端相同的 `.env`，执行 `alembic upgrade head`；不会自动运行，也不会自动降级。失败时查看 `journalctl -u fgas-migrate -n 100 --no-pager`，修好前不要重启后端。数据库定期备份由服务器维护者负责，不能用测试脚本检查正式库。

更新后查看服务和健康状态：

```bash
systemctl status fgas --no-pager
curl --fail http://127.0.0.1:10622/api/health
```

只改前端时，构建后网站就会读取新文件；重启后端是统一流程的一部分。只改 `.env` 时直接 `sudo systemctl restart fgas` 即可，每次启动都会重新读取 `EnvironmentFile`。修改了单元文件本身时，先 `sudo systemctl daemon-reload` 再重启。

## 日志、停止和开机启动

```bash
journalctl -u fgas -n 100 --no-pager
journalctl -u fgas -f
sudo systemctl stop fgas
sudo systemctl restart fgas
```

`systemctl enable --now fgas` 已经处理开机自启；`sudo systemctl disable --now fgas` 取消自启并停止。修改服务账号、路径或端口后，先确认运行正常，再按需调整单元文件；不要用会波及其他服务的全局操作。

如果服务器由个人账号维护代码而不是专用 `fgas` 账号，把单元里的 `User`/`Group` 改成该账号，并确保它对项目目录、`.venv` 和 `frontend/dist` 有读写权限；系统服务与手动目录更新仍可共存。

## 自动备份与恢复

备份使用 `pg_dump -Fc`，由 systemd timer 每天执行一次，写入 `/var/lib/fgas-backup`，默认保留 30 天。服务器需要安装与数据库主版本兼容的 PostgreSQL 客户端（提供 `pg_dump` 和 `pg_restore`）。

安装并启用定时备份：

```bash
sudo cp /srv/fgas/deploy/fgas-backup.service /srv/fgas/deploy/fgas-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fgas-backup.timer
sudo systemctl start fgas-backup
journalctl -u fgas-backup -n 50 --no-pager
systemctl list-timers fgas-backup.timer
```

备份文件位于 `/var/lib/fgas-backup/fgas-<UTC时间>.dump`。`fgas-backup.service` 读取与后端相同的 `.env`，通过 `StateDirectory` 获得备份目录写权限，`ProtectSystem=strict` 仍然生效。`Persistent=true` 表示关机期间错过的任务会在开机后补跑；保留天数可用 `.env` 中的 `FGAS_BACKUP_RETENTION_DAYS` 覆盖（默认 30）。

恢复会覆盖目标库，操作前先确认目标、另存一份当前备份，并停止服务：

```bash
sudo systemctl stop fgas
sudo -u fgas bash -c 'set -a; . /srv/fgas/.env; set +a; pg_restore --clean --if-exists --no-owner -d "${DATABASE_URL/+psycopg2/}" /var/lib/fgas-backup/<备份文件>.dump'
sudo systemctl start fgas
curl --fail http://127.0.0.1:10622/api/health
```

`--clean --if-exists` 会删除并重建对象，不要在未确认目标库时执行。恢复完成后健康接口应返回 status=ok，`schema_revision` 应与当前代码期望的 Alembic 版本一致。

## PM2 方式（备选）

仓库仍保留 [ecosystem.config.cjs](../ecosystem.config.cjs)，安装 PM2 后可用 `pm2 start ecosystem.config.cjs` 启动同一个 Uvicorn 进程，更新命令为 `pm2 startOrRestart ecosystem.config.cjs --update-env`，开机自启用 `pm2 startup` 和 `pm2 save`。PM2 由项目 `.env` 注入环境变量，值优先于同名环境变量；缺少 `DATABASE_URL` 时会直接报错。

两种进程管理方式选一种运行，避免重复启动同一系统。`npm run db:init` 与 systemd 方式共用同一份 `.env` 配置。
