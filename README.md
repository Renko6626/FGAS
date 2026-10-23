# FGAS 资金与库存工作台

单社团、人民币的开发原型。以账户和 Transfer 表达资金、货物的变化；结算匹配记录成员支出报销及代收交回，薄盘点表组织普通盈亏转移。

业务模型见 [transfer-model](docs/transfer-model.md)，架构见 [architecture](architecture.md)，实际验证状态见 [阶段记录](docs/prototype-status.md)。

## 本地开发

需要 Python 3.13、Node.js 22 及 PostgreSQL。沿用现有环境和 `.env`；连接信息不要提交到仓库。

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install
cp .env.example .env
# 修改 .env，使 DATABASE_URL 指向本项目开发库
npm run dev
```

后端默认 `127.0.0.1:10622`，前端 `5173`，通过 `/api` 代理。认证由 `AUTH_MODE` 切换：本地开发使用 `development` 的账号选择；正式环境使用 `casdoor`，通过既有 Casdoor OIDC 登录。Casdoor 首次登录自动建立本地用户，默认普通用户，角色由管理员在“用户权限”中维护；`INITIAL_ADMIN_SUBJECT` 只在首次建号时把匹配的 Casdoor `sub` 或用户名绑定为管理员。三档角色为管理员、受信任用户、普通用户。

数据库 schema 由 Alembic 管理，当前基线是 `0001_baseline_schema`。`npm run db:init` 会执行 `alembic upgrade head` 并写入开发种子；`npm run dev` 启动前也会 upgrade。已有 FGAS 表但没有 `alembic_version` 的旧库会被明确拒绝，必须先备份并收养或重建，不能回到 `create_all`。修改模型后生成新的 revision，不要手写升级 SQL；完整流程见 [数据库迁移](docs/migrations.md)。

历史 [scripts/upgrade-agent-access.sql](scripts/upgrade-agent-access.sql)、[scripts/upgrade-user-auth.sql](scripts/upgrade-user-auth.sql)、[scripts/upgrade-posted-at.sql](scripts/upgrade-posted-at.sql) 仅用于收养基线前旧库：备份、执行、校验 schema 后 `alembic stamp 0001`。可丢弃的旧库直接重建即可。种子有开发用户、公账资金池、外部收支/期初账户、公账主存放处，没有业务流水，也不为成员自动开私账。

## 服务器部署与更新

推荐使用 Docker Compose：Python 后端、带 Nginx 的静态前端和 PostgreSQL 一起启动，服务器只安装 Docker 与 Compose。

两条发布路径共用同一套配置：

- 手动发布：本机构建完整镜像，打包后通过 SSH 传到服务器加载。
- 自动发布：GitHub Actions 构建镜像并推送 GHCR，服务器拉取后更新。

首次配置、发布命令和 GitHub Secrets 见 [部署说明](deploy/README.md)。不依赖 Docker 时，可用 [systemd 原生方式](deploy/README.native.md)（含 PM2 备选）。首次部署和普通更新都会先备份数据库、再通过 Compose 一次性 `migrate` 服务执行 Alembic；迁移失败时 API 不启动。

Compose 默认使用 `AUTH_MODE=casdoor`，需要先在 Casdoor 建立 FGAS 应用并填写回调地址、client id/secret 和初始管理员。默认只监听服务器本机的 8080 端口；HTTPS 站点必须设置 `COOKIE_SECURE=true`。真实 Casdoor 联调、域名和 HTTPS 验收尚未完成，部署脚本不代表正式上线已验收。

也可以在腾讯云等支持 systemd 的 Linux 主机上从 GitHub 拉取源码部署：systemd 管理 Uvicorn 后端，Nginx 提供 `frontend/dist` 并转发 `/api`、`/mcp`，数据保存在 PostgreSQL。主机需准备 Python 3.13、Node.js 22+、PostgreSQL 和 Nginx；公网使用需配置域名、HTTPS 和 Casdoor 回调地址。日常更新按“拉代码 → 按需安装依赖 → 构建前端 → 备份并执行 Alembic 迁移 → 重启服务”处理。

仓库提供 [fgas.service](deploy/fgas.service)、一次性的 [fgas-migrate.service](deploy/fgas-migrate.service) 和每日备份的 [fgas-backup.service](deploy/fgas-backup.service) / [fgas-backup.timer](deploy/fgas-backup.timer)，按实际发行版、部署目录和运行用户调整后启用。环境准备、Nginx 转发、手动更新和备份恢复步骤见 [原生部署说明](deploy/README.native.md)。

## 账户与标签

资金表 `fund_accounts`、货物表 `stock_accounts` 共用 `id/name/kind/member_id/avatar_url/tags/active`。类型 `public/private/external` 创建后固定；联系人可空，公私分类不由联系人决定。图片为空或加载失败时显示名称首字，按名称生成稳定的浅背景、深文字配色。SKU 也保存可空 `avatar_url`，可在货物目录中维护缩略图 URL；货物账户复用同名字段。

资金公账合计只计 `public`；私账正数应交回、负数社团应偿还。货物 `public/private` 均计组织库存，外部账户不计入。联系人与实际保管人分别记录，保管交接保留历史。

标签由常用下拉选项加自定义输入组成，保存为 JSON 字符串数组，用于账户和流水筛选，不决定业务准入。停用阻止新建，不阻止已有转移处理。

## HTTP 契约

人工业务入口位于 `/api`，有效登录会话可读，目录维护、匹配和人工审批要求受信任用户或管理员。

| 路径 | 功能 |
| --- | --- |
| `/auth/config` | 公开返回当前登录模式 |
| `/auth/users`、`/auth/login` | 仅 development 模式可用的开发登录 |
| `/auth/casdoor/login`、`/auth/casdoor/callback` | 仅 casdoor 模式可用的 OIDC 登录（授权码 + PKCE） |
| `/auth/logout`、`/auth/me` | 退出登录与当前用户 |
| `/agent-credentials`、`/agent-credentials/{id}` | 人工 Cookie 会话管理连接：列表、签发、修改；明文只在签发时返回 |
| `/users`、`/users/{id}` | 管理员查看用户、修改角色和启停；最后一名启用管理员受保护 |
| `/users/{id}/logout` | 管理员强制撤销该用户全部网页会话 |
| `/members`、`/members/{id}` | 联系人目录，列表/创建/修改；不自动建账 |
| `/accounts`、`/accounts/{id}` | 资金账户列表/创建/修改 |
| `/stock-accounts`、`/stock-accounts/{id}` | 货物账户列表/创建/修改 |
| `/stock-accounts/{id}/custody` | 当前保管成员维护，`{member_id:null}` 结束保管 |
| `/skus`、`/skus/{id}` | SKU 目录，已引用后单位固定 |
| `/transfers/preview`、`/transfers`、`/transfers/{id}` | 资金转移预览/提交/列表/详情 |
| `/transfers/{id}/approve`、`reject`、`reverse` | 资金审批、拒绝、冲销 |
| `/funds/summary` | 公账合计 |
| `/dashboard` | 首页汇总：公账余额、组织库存、按实际入账时间统计的近 7 天变化、近期转移和待办计数 |
| `/accounts/{id}/settlement-overview` | 私账净余额、原收支及逐笔结算情况 |
| `/settlements` | 创建普通结算付款并匹配，`{transfer,allocations:[{item_transfer_id,amount}]}` |
| `/transfers/{id}/settlement-matches` | 向已有付款追加上述匹配 |
| `/stock-transfers`、`/stock-transfers/{id}` | 多 SKU 货物转移创建/列表/详情 |
| `/stock-transfers/{id}/approve`、`reject`、`cancel` | 货物审批、拒绝、取消 |
| `/stock-transfers/{id}/completion` | 整笔完成申请，仅 `{effective_date}` |
| `/stock-confirmations/{id}/approve`、`reject` | 完成申请审批 |
| `/stock-transfers/{id}/fund-references` | 补充已有资金引用 |
| `/stock-operations` | `{stock,money}` 一次事务创建货物和普通资金转移 |
| `/inventory`、`/stock-moves` | 正式数量查询；库存支持账户、SKU、联系人、保管人筛选 |
| `/fund-stocktakes`、`/stock-stocktakes` | 薄盘点列表/创建 |
| 上述盘点路径加 `/{id}`、`/{id}/end` | 详情/修改说明/结束 |

账户列表支持 `tag/kind/member_id`，两类转移列表支持单个 `tag`。金额输入是元字符串，数据库按整数分；数量输入为正整数字符串，数据库按整数数量。资金 Transfer 主要输入 `source_account_id/destination_account_id/amount/effective_date/description/tags/counterparty`；货物主要输入来源/去向账户、日期、说明、标签、可选单据与原单引用、多 SKU `lines` 和资金引用。

资金普通转移由可信用户自动批准过账，普通用户待人工审批。货物批准后在途，额外整笔完成才记数量；普通用户的完成申请也需审批。拒绝/取消/冲销填写原因，正式流水不能覆盖改写。货物实际账户出库不得造成负库存，两个外部货物账户间不转移。用途不再强制匹配供应商、客户或动作枚举。

## 结算与盘点

已批准的私账→外部支出可报销，外部→私账收款可代收交回。匹配归属于具体私账，与联系人无关；支持部分和多笔结算，不自动净额抵扣。匹配不产生资金流水。匹配任何一端被冲销后历史保留但失效，界面显示剩余未结或付款未匹配金额；不自动级联冲销。

盘点保存名称、说明、状态、两个专属外部账户和创建信息，不保存清点明细或独立差异账本。详情查询任一端涉及专属账户的转移及资金直接冲销。结束默认隐藏端点，仍可补录，不表示差异已结清。

## 验证

```bash
./tools/run_tests.sh
npm run build
```

测试脚本仅允许 `fgas_test`，每次集中运行先重建该测试库的 FGAS 表；不要把日常开发库传给测试。迁移测试会在同一 PostgreSQL 实例上创建并删除独立临时库，验证 upgrade、drift check 和 downgrade，不触碰 `fgas_test` 的共享表。测试使用真实数据库及 HTTP 生产路径，Casdoor 流程通过 mock IdP 覆盖，不访问外部服务。前端验证为 TypeScript 检查和生产构建，未经要求不做浏览器自动点击/填表。

真实 Casdoor 联调、附件、生产部署、备份恢复尚未验收，本轮不实现估值、利润、订单、清点明细或请求恢复。

## Agent 接入（MCP v2，开发阶段）

网页页脚提供无需登录的 `/agent-setup.md` 接入指南，链接直接写在原始 HTML 中。可以将该站点文档地址交给外部 Agent，让它自行识别客户端、配置 MCP 并做只读验证；缺少连接密钥时再由用户在网页签发。文档源文件为 [agent-setup.md](frontend/public/agent-setup.md)。

后端通过官方 `mcp==2.3.0` Streamable HTTP 在 `http://127.0.0.1:10622/mcp` 提供业务工具。先由人工登录“Agent 连接”签发令牌，再由客户端运行时提供 `Authorization: Bearer …`。令牌不能作为 `/api` 人工登录会话；Cookie 也不能代替 MCP Bearer。明文仅显示一次，丢失请新建连接，勿放入对话、仓库或工具参数。

受信任用户只能签发自己的 low，管理员可签自己的 low/high；普通用户不能签发。MCP v2 的 low 只暴露 `fgas_help`、`fgas_query`、`fgas_propose`，high 增加 `fgas_execute`。通过对象、动作及参数覆盖原有业务能力，具体参数按需查 help。连接及所属用户的启停、角色和过期时间每次调用重新检查；Agent 不能管理登录用户、角色或连接。初始化说明先讲清账户、Transfer、正式流水、结算和盘点的关系，见 [核心模型](docs/ai/overview.md) 与 [完整指南](docs/ai/guide.md)。

以下变量由启动客户端的运行时安全注入：`FGAS_MCP_URL` 为上述 URL，`FGAS_AGENT_TOKEN` 为一次性签发所得令牌。回环地址仅供与后端同机的客户端访问；另一台机器的 `127.0.0.1` 指向它自己。当前保留 SDK 默认回环 Host 校验；自定义域名、远程 HTTPS、OAuth 和部署尚未联调。

DeepSeek Harness 0.1.5-rc.3 的 `cordis.yml` 插件条目如下。字段及 `!!js` 环境变量写法依据其已安装官方包 README/Config；工具名称在 Harness 中为 `mcp__fgas__fgas_*`；2026-10-15 曾用实际 MCP 插件/ToolRuntime 在专用测试库验证 v1 的两档发现、读取、待审提交及 high 直接过账，未调用模型；该历史结果不代表 v2 已完成外部客户端联调。将条目加入现有配置，不需要改变模型或调用模型完成连接验证。

```yaml
- id: mcp-fgas
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: fgas
    transport: streamable-http
    url: !!js process.env.FGAS_MCP_URL
    headers:
      Authorization: !!js '`Bearer ${process.env.FGAS_AGENT_TOKEN}`'
    reconnect:
      enabled: false
```

DSH 插件来源：[官方 MCP 客户端说明](https://github.com/deepseek-ai/deepseek-harness/tree/main/packages/mcp/mcp-client)。关闭重连方便本地人工排查；客户端不得自动重发业务写操作。

OpenCode 的 `opencode.json` 使用标准远程配置，依据 [官方 MCP 文档](https://opencode.ai/docs/mcp-servers/#disabling-oauth)。本机未安装 OpenCode，下面配置尚未由实际 OpenCode 联调。

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "fgas": {
      "type": "remote",
      "url": "{env:FGAS_MCP_URL}",
      "oauth": false,
      "headers": {"Authorization": "Bearer {env:FGAS_AGENT_TOKEN}"}
    }
  }
}
```

成功连接后阅读初始化的核心模型说明，用 `fgas_help()` 查看当前权限与索引，再按需查某一对象/动作的精确输入参数和示例；需要完整输出 Schema 时加 `include_output_schema=true`。状态等枚举以帮助声明为准，已知参数可直接调用。`fgas_propose` 对两档始终 pending；`fgas_execute` 仅 high 使用，资金直接过账，货物创建只进在途，另行完成才记库存。调用成功保存返回 ID；断线后查记录并人工核对，不自动重发。结果、查询分页和 Patch 规则以帮助契约与指南为准。

从 v1 升级：原50个工具名已移除执行能力，只返回迁移提示。MCP 地址和凭据沿用，客户端需重新发现工具，硬编码旧名称的脚本需改为四入口；返回 `api_version=2`。没有数据库变更。当前仍未正式发布，实际验证与未做项见阶段记录。
