# Compose 与 SSH 部署实施计划

用户已确认回到 Docker Compose，希望前后端省心，Nginx 随部署提供，手动传镜像包，并使用 GHCR 作为自动发布仓库。目标与构建机均为 linux/amd64。本计划沿用该路线直接实施，不重复要求流程确认。

## 范围与边界

- 三个服务：PostgreSQL 14、现有 FastAPI/MCP、Nginx静态前端；后端和数据库不映射主机端口。
- Node22只用于前端镜像构建，Python3.13放进后端镜像。Nginx配置打进前端镜像。
- 镜像本机构建并docker save到发布包，含Postgres镜像；SSH传输后load，目标up使用--no-build/--pull never。
- 数据库数据卷固定项目名保留，包内不含真实.env或业务数据。首次初始化显式--init-db，普通更新不执行初始化/升级SQL。
- Nginx提供网页和agent-setup.md，转发/api与/mcp；MCP Host保持回环许可，Authorization透传，Origin不移除。
- 当前开发账号登录限制仍存在，默认只映射本机127.0.0.1:8080，外网访问与正式身份/HTTPS要按实际站点另行配置。
- GitHub Actions 构建并检查容器后推送 GHCR；发布包使用精确版本标签，SSH 更新默认关闭，配置凭据后可启用。
- 不新增自动回滚、发布队列或数据迁移框架；不操作实际远程服务器。

## 实施步骤

- [x] 完整Compose、前后端Dockerfile、Nginx、.dockerignore及部署环境模板；本地构建覆盖文件与运行Compose分开。
- [x] 添加package-release.sh，构建及导出三镜像，附runtime Compose、版本环境和apply脚本。
- [x] 添加apply-release.sh（本地包加载或GHCR拉取，显式可选初始化）；push-release.sh（SSH/SCP传输并调用apply）。
- [x] 添加GitHub Actions镜像构建、启动检查、GHCR发布和可选SSH部署。
- [x] 文档改为Compose主线，保留PM2原生方式作备选，说明首次配置、后续更新和数据卷/备份。
- [x] 集中验证shell语法、Compose变量解析与端口/服务关系、前端构建；尝试镜像构建，权限阻止时如实记录。
- [x] 独立只读审阅部署逻辑，无必修问题；交付代码，不推送或部署。

## 初始证据

- 初始工作区仅用户temp/未跟踪，分支feature/agent-tools-v2。
- Docker CLI29.0.2与Compose2.40.3可用；访问/var/run/docker.sock被permission denied拒绝，尚不能构建或启动容器。

## 验证结果

- bash -n：三个新增脚本及工作流内所有 shell 步骤通过；工作流 YAML 可解析。
- Docker Compose 运行配置与源码构建覆盖配置均解析通过，确认仅网页映射本机端口，数据库卷名固定。
- 实际生成 GHCR 小发布包，在临时目录解包，核对内容及精确镜像引用；启动脚本缺配置时创建0600模板并退出。无效参数在Docker/SSH调用前拒绝。临时包已清除。
- npm run build 通过（vue-tsc、Vite），保留已有约511kB主JS体积提示。
- Docker info 返回 /var/run/docker.sock permission denied：真实镜像构建、容器/Nginx/MCP运行、GitHub Actions及SSH部署均未执行，不宣称通过。
- 不操作真实配置、业务数据或远程服务；用户temp/保持原样。
