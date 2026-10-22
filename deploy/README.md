# Linux 原生部署：PM2 管后端

日常更新按“拉代码 → 构建 → 重启”处理。后端用 PM2 管理，前端构建后由服务器上的静态网站服务提供，数据库使用现有 PostgreSQL。

目前 FGAS 仍使用开发账号选择登录，只适合本机、内网或有外部访问限制的试用环境。正式公网使用前还需要完成 Casdoor 登录接入。这份文档整理运行和更新方式，不会自动开放网站或安装系统服务。

## 第一次部署

服务器准备好 Python 3.13、Node.js 22 或更新版本，以及 PostgreSQL。用同一个普通 Linux 用户维护代码和 PM2 进程。

在服务器上克隆代码，进入项目目录，然后安装 PM2 和项目依赖：

```bash
npm install -g pm2
npm run setup
```

`npm run setup` 创建项目自己的 `.venv`，安装现有 Python 依赖，再按锁文件安装前端依赖。它不会初始化数据库或启动服务。PM2 官方支持用 ecosystem 文件统一管理进程，项目配置见 [ecosystem.config.cjs](../ecosystem.config.cjs)。[PM2 配置说明](https://pm2.keymetrics.io/docs/usage/application-declaration/)

准备一个 FGAS 专用的 PostgreSQL 数据库和账号，然后复制配置：

```bash
cp .env.example .env
chmod 600 .env
```

编辑 `.env`，把 `DATABASE_URL` 换成实际连接信息。默认后端端口为 `API_PORT=8000`，只监听 `127.0.0.1`。HTTPS 网站使用 `COOKIE_SECURE=true`；本机 HTTP 试用保留 false。当前 `AUTH_MODE` 只能是 development，不能改成 production 来代替正式登录接入。

PM2 配置从项目根目录读取 `.env`，文件中的值优先于同名环境变量。文件没写的项可以从启动命令的环境变量读取；没有 DATABASE_URL 会直接报错，不会猜测数据库地址。

**确认连接的是新建的 FGAS 数据库后**，初始化一次：

```bash
npm run db:init
```

初始化使用与 PM2 相同的数据库配置，创建缺少的表和初始目录，不带清库参数。不要把其他系统的数据库拿来初始化，也不要在部署时使用 `--reset`、`--reset-db` 或测试脚本。

如果接手的是已有 FGAS 数据库，先查看版本和更新说明。初始化不会给旧表自动增加字段；例如早期版本的 Agent 接入升级使用 [upgrade-agent-access.sql](../scripts/upgrade-agent-access.sql)，需要先核对目标库和备份，再按确认后的步骤执行。

构建前端，启动后端：

```bash
npm run build
pm2 start ecosystem.config.cjs
pm2 status fgas
curl --fail http://127.0.0.1:8000/api/health
```

健康接口应返回 status=ok。检查失败时先看 `pm2 logs fgas --lines 100`，修好后再继续；PM2 显示 online 本身不能证明数据库可用。

## 网页和 MCP 如何对外提供

前端构建产物在 `frontend/dist`。让现有网站服务使用这个目录作为站点根目录，按下面的路径分流：

| 请求 | 处理方式 |
| --- | --- |
| `/`、`/assets/*`、`/agent-setup.md` | 读取 `frontend/dist` 中的文件 |
| `/api/*` | 转发到 `http://127.0.0.1:8000`，保留路径 |
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
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location = /mcp {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $proxy_host;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
}
```

MCP 转发中的 Host 使用本机后端地址，与当前 SDK 的回环 Host 校验相配合。原始 Origin 仍会传入后端；如果以后要从浏览器直接调用 MCP，还需按实际域名配置 SDK 的 Origin 许可，不能靠删除 Origin 或关闭认证绕过。[Nginx 转发头说明](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)

网页打开后，检查 `/agent-setup.md` 能读到 Markdown，登录后的 API 可以访问，再按指南连接 MCP 做一次只读查询。直接打开 `/mcp` 得到401只是说明需要密钥，不是完整的 MCP 验收。

## 平时更新

没有依赖或数据库结构变化时，在项目目录执行：

```bash
git pull --ff-only
npm run build
pm2 startOrRestart ecosystem.config.cjs --update-env
```

一条成功后再执行下一条。构建失败时先查看错误，不要继续重启。这里采用直接更新工作目录的简单方式，构建会更新 `frontend/dist`；更新时选一个没人操作的时间即可。暂不增加发布目录切换或自动回退流程。

如果这次修改了 `backend/requirements.txt`、前端 package.json 或锁文件，在构建前多执行一次：

```bash
npm run setup
```

更新后查看服务和健康状态：

```bash
pm2 status fgas
curl --fail http://127.0.0.1:8000/api/health
```

只改前端时，构建后网站就会读取新文件；重启后端是统一流程的一部分。只改 `.env` 时，使用上述带配置文件的 startOrRestart 命令重新加载，不要只执行 `pm2 restart fgas` 期望它重读文件。

正常更新和 PM2 重启都不会调用数据库初始化，也不自动执行升级 SQL。遇到数据库结构变更，按该版本说明单独安排。数据库定期备份由服务器维护者负责，不能用测试脚本检查正式库。

## 日志、停止和开机启动

```bash
pm2 logs fgas --lines 100
pm2 stop fgas
```

确认服务运行正常后，保存进程列表：

```bash
pm2 save
pm2 startup
```

`pm2 startup` 会打印一条适合这台机器的安装命令，照提示执行即可。它由 PM2 处理开机恢复，不用另写 FGAS 的 systemd 配置。以后改变了部署路径、端口或环境配置并确认运行正常后，再执行一次 `pm2 save`。原有 PM2 列表也会一起保存，不要使用会影响其他项目的 `delete all` 或 `kill`。[PM2 开机启动说明](https://pm2.keymetrics.io/docs/usage/startup/)

原来的 [Dockerfile](Dockerfile) 和 [compose.yaml](compose.yaml) 留作备选，当前维护流程不依赖它们。CI 可以以后补上前端构建和已有后端测试；发布阶段复用这里的命令即可，不需要再设计一套部署系统。
