# FGAS 资金与库存工作台

单社团、人民币的开发原型。以账户和 Transfer 表达资金、货物的变化；结算匹配记录成员支出报销及代收交回，薄盘点实现暂时停用并保留代码。

2026-10-27 起，资金与货物盘点暂时停用：隐藏网页入口，HTTP 返回 404，MCP 不再提供盘点资源；原实现与表保留。期初及账面调整仍可登记普通转移。历史余额／库存默认按实际入账时间查询，业务日期仅作明确指定的备选口径。本轮开发数据已按用户确认备份后重建。

业务模型见 [transfer-model](docs/transfer-model.md)，架构见 [architecture](architecture.md)，实际验证状态见 [阶段记录](docs/prototype-status.md)。资金、结算、库存、首页、身份管理及 MCP v2 已实现；薄盘点代码保留但入口暂停。当前分支后端 84 项测试与前端构建通过，定向真实模型复测和生产验收见阶段记录。

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

数据库 schema 由 Alembic 管理，当前基线是 `0001_baseline_schema`。`npm run db:init` 会执行 `alembic upgrade head` 并写入开发种子；`npm run dev` 启动前也会 upgrade。已有 FGAS 表但没有 `alembic_version` 的旧库会被明确拒绝，必须先备份并收养或重建，不能回到 `create_all`。本轮业务编号经用户确认直接同步 `0001`，不新增 revision、迁移或回填旧库；日常 `fgas` 未改，旧库不能直接沿用新契约。此后模型变更应新增 revision；完整流程见 [数据库迁移](docs/migrations.md)。

历史 [scripts/upgrade-agent-access.sql](scripts/upgrade-agent-access.sql)、[scripts/upgrade-user-auth.sql](scripts/upgrade-user-auth.sql)、[scripts/upgrade-posted-at.sql](scripts/upgrade-posted-at.sql) 仅用于收养基线前旧库：备份、执行、校验 schema 后 `alembic stamp 0001`。可丢弃的旧库直接重建即可。种子有开发用户、公账资金池、外部收支/期初账户、公账主存放处，没有业务流水，也不为成员自动开私账。

## 服务器部署与更新

推荐使用 Docker Compose：Python 后端、带 Nginx 的静态前端和 PostgreSQL 一起启动，服务器只安装 Docker 与 Compose。

两条发布路径共用同一套配置：

- 手动发布：本机构建完整镜像，打包后通过 SSH 传到服务器加载。
- 自动发布：GitHub Actions 构建镜像并推送 GHCR，服务器拉取后更新。

首次配置、发布命令和 GitHub Secrets 见 [部署说明](deploy/README.md)。不依赖 Docker 时，可用 [systemd 原生方式](deploy/README.native.md)（含 PM2 备选）。Compose 发布脚本在首次部署和普通更新时先备份数据库、再通过一次性 `migrate` 服务执行 Alembic；迁移失败时 API 不启动。原生部署按其文档执行备份与迁移。部署路线定位见[部署说明中的对照表](deploy/README.md)。

Compose 默认使用 `AUTH_MODE=casdoor`，需要先在 Casdoor 建立 FGAS 应用并填写回调地址、client id/secret 和初始管理员。默认只监听服务器本机的 8080 端口；HTTPS 站点必须设置 `COOKIE_SECURE=true`。真实 Casdoor 联调、域名和 HTTPS 验收尚未完成，部署脚本不代表正式上线已验收。

也可以在腾讯云等支持 systemd 的 Linux 主机上从 GitHub 拉取源码部署：systemd 管理 Uvicorn 后端，Nginx 提供 `frontend/dist` 并转发 `/api`、`/mcp`，数据保存在 PostgreSQL。主机需准备 Python 3.13、Node.js 22+、PostgreSQL 和 Nginx；公网使用需配置域名、HTTPS 和 Casdoor 回调地址。日常更新按“拉代码 → 按需安装依赖 → 构建前端 → 备份并执行 Alembic 迁移 → 重启服务”处理。

仓库提供 [fgas.service](deploy/fgas.service)、一次性的 [fgas-migrate.service](deploy/fgas-migrate.service) 和每日备份的 [fgas-backup.service](deploy/fgas-backup.service) / [fgas-backup.timer](deploy/fgas-backup.timer)，按实际发行版、部署目录和运行用户调整后启用。环境准备、Nginx 转发、手动更新和备份恢复步骤见 [原生部署说明](deploy/README.native.md)。

## 账户与标签

资金表 `fund_accounts`、货物表 `stock_accounts` 公开目录共用 `code/name/kind/avatar_url/tags/active`。资金类型为 `public/private/external`；货物仅为 `internal`（实际保管）或 `external`（外部），均在创建后固定。资金联系人可空；货物公开的 `member_code/member_name` 来自当前负责人历史。图片为空或加载失败时显示名称首字，按名称生成稳定的浅背景、深文字配色。SKU 也保存可空 `avatar_url`，可在货物目录中维护缩略图 URL；货物账户复用同名字段。

资金公账合计只计 `public`；私账正数应交回、负数社团应偿还。货物 `internal` 计组织库存，成员长期代管同样属于实际保管；外部账户不计入。资金账户可关联联系人；货物账户只维护一名负责人，变更自动保留历史。

货物不保存批准／执行的完整内容快照，审计仅保留操作人、时间、原因及必要的申请、资金引用编号和批准方式。2026-10-27 用户确认本轮直接同步 `0001` 并备份后重建开发 FGAS 表，不新增迁移或旧结构兼容；负责人历史的模型保留，重建后的开发数据从种子开始。

标签由常用下拉选项加自定义输入组成，保存为 JSON 字符串数组，用于账户和流水筛选，不决定业务准入。停用阻止新建，不阻止已有转移处理。

## HTTP 契约

人工业务入口位于 `/api`，有效登录会话可读，目录维护、匹配和人工审批要求受信任用户或管理员。

| 路径 | 功能 |
| --- | --- |
| `/auth/config` | 公开返回当前登录模式 |
| `/auth/users`、`/auth/login` | 仅 development 模式可用的开发登录 |
| `/auth/casdoor/login`、`/auth/casdoor/callback` | 仅 casdoor 模式可用的 OIDC 登录（授权码 + PKCE） |
| `/auth/logout`、`/auth/me` | 退出登录与当前用户 |
| `/agent-credentials`、`/agent-credentials/{id}` | 人工 Cookie 会话管理连接：列表、签发、修改；列表不返回密钥 |
| `/agent-credentials/{id}/secret` | 本人通过 Cookie 会话再次查看连接密钥，管理员不能查看他人的密钥 |
| `/users`、`/users/{id}` | 管理员查看用户、修改角色和启停；最后一名启用管理员受保护 |
| `/users/{id}/logout` | 管理员强制撤销该用户全部网页会话 |
| `/members`、`/members/{code}` | 联系人目录，列表/创建/修改；不自动建账 |
| `/accounts`、`/accounts/{code}` | 资金账户列表/创建/修改 |
| `/stock-accounts`、`/stock-accounts/{code}` | 货物账户列表/创建/修改 |
| `/stock-accounts/{code}` | 货物账户详情含负责人历史；编辑 member_code 更改负责人，null 清空 |
| `/skus`、`/skus/{code}` | SKU目录，代号唯一；按code/q/tag/active查询，已引用后单位固定 |
| `/transfers/preview`、`/transfers`、`/transfers/{code}` | 资金转移预览/提交/列表/详情 |
| `/transfers/{code}/approve`、`reject`、`reverse` | 资金审批、拒绝、冲销 |
| `/funds/summary` | 公账合计 |
| `/dashboard` | 首页汇总：公账余额、组织库存、按实际入账时间统计的近 7 天变化、近期转移和待办计数 |
| `/accounts/{code}/settlement-overview` | 私账净余额、原收支及逐笔结算情况 |
| `/settlement-outstanding` | 全局已过账未匹配明细；按 account_code、direction=expense/receipt、kind=item/payment 筛选并分页，不限近30天 |
| `/settlements` | 创建普通结算付款并匹配，`{transfer,allocations:[{item_transfer_code,amount}]}` |
| `/transfers/{code}/settlement-matches` | 向已有付款追加上述匹配 |
| `/stock-transfers`、`/stock-transfers/{code}` | 多 SKU 货物转移创建/列表/详情 |
| `/stock-transfers/{code}/approve`、`reject`、`cancel` | 货物审批、拒绝、取消 |
| `/stock-transfers/{code}/completion` | 整笔完成申请，仅 `{effective_date}` |
| `/stock-confirmations/{code}/approve`、`reject` | 完成申请审批 |
| `/stock-transfers/{code}/fund-references` | 补充已有资金引用 |
| `/stock-operations` | `{stock,money}` 一次事务创建货物和普通资金转移 |
| `/inventory`、`/stock-moves` | 正式数量及货物流水查询；库存支持账户、SKU、负责人筛选，当前计划按流入/流出及组织进出/内部调拨区分 |
| `/fund-stocktakes`、`/stock-stocktakes` | 薄盘点列表/创建 |
| 上述盘点路径加 `/{id}`、`/{id}/end` | 详情/修改说明/结束 |

账户列表支持`tag/kind/member_code`，两类转移列表支持单个tag。资金账户、货物账户、联系人、资金单、货物单和完成申请使用自动、不可编辑的 FA/SA/M/FT/ST/SC 编号；公开业务输入、输出、筛选及路径使用 `code` 或 `*_code`，内部 UUID 仅用于关联。SKU有必填唯一code（如ARC-01-A），完整name包含款式规格，tags可标类别和角色；录单lines使用`{sku_code,quantity}`，库存/货物/数量流水按sku_code筛选。代号去首尾空格、转大写后去重，重复返回409。金额输入是元字符串、库内整数分；数量为正整数字符串。资金Transfer输入来源/去向、金额、业务日期、说明及标签；货物另含多SKU lines、原单/原始单据和资金引用。

资金普通转移由可信用户自动批准过账，普通用户待人工审批。货物批准后在途，额外整笔完成才记数量；普通用户的完成申请也需审批。拒绝/取消/冲销填写原因，正式流水不能覆盖改写。货物实际账户出库不得造成负库存，两个外部货物账户间不转移。用途不再强制匹配供应商、客户或动作枚举。

## 结算与盘点

下述薄盘点结构暂时保留，当前不能通过网页、HTTP 或 MCP 使用。恢复时同时启用 `backend/application/stocktakes.py` 的 `ENABLED` 和 `frontend/src/features.ts` 的 `stocktakesEnabled`，并重启后端、重建前端。

已批准的私账→外部支出可报销，外部→私账收款可代收交回。匹配归属于具体私账，与联系人无关；支持部分和多笔结算，不自动净额抵扣。匹配不产生资金流水。匹配任何一端被冲销后历史保留但失效，界面显示剩余未结或付款未匹配金额；不自动级联冲销。

盘点保存名称、说明、状态、两个专属外部账户和创建信息，不保存清点明细或独立差异账本。详情查询任一端涉及专属账户的转移及资金直接冲销。结束默认隐藏端点，仍可补录，不表示差异已结清。

## 验证

东方社团Agent基准配置见[基准包说明](benchmarks/gensokyo-circle-v1/README.md)：32件带业务代号和角色/类别标签的商品、49笔资金单、52笔货物单及24张任务卡。用`.venv/bin/python scripts/benchmark.py init`创建独立`fgas_benchmark`并沿真实HTTP业务入口加载，`check`核对固定答案，`serve`启动独立回环服务。写任务之间用`reset`备份后恢复基线，不改日常开发库或测试库。任务和黄金答案分开提供，加载成功不表示模型任务已经通过。

2026-10-27用户确认本轮SKU结构直接同步0001新基线，不做迁移、回填或旧字段兼容；旧日常开发库不能原地升级成该结构，需另行处理，脚本不会自动重建它。

```bash
./tools/run_tests.sh
npm run build
```

测试脚本仅允许 `fgas_test`，每次集中运行先重建该测试库的 FGAS 表；不要把日常开发库传给测试。迁移测试会在同一 PostgreSQL 实例上创建并删除独立临时库，验证 upgrade、drift check 和 downgrade，不触碰 `fgas_test` 的共享表。测试使用真实数据库及 HTTP 生产路径，Casdoor 流程通过 mock IdP 覆盖，不访问外部服务。前端验证为 TypeScript 检查和生产构建，未经要求不做浏览器自动点击/填表。

真实 Casdoor、域名与 HTTPS、生产发布和备份恢复尚未验收；附件尚未实现。估值、成本、利润、订单、清点明细和请求恢复不在第一阶段范围。

## Agent 接入（MCP v2，开发阶段）

网页页脚提供无需登录的 `/agent-setup.md` 接入指南，链接直接写在原始 HTML 中。可以将该站点文档地址交给外部 Agent，让它自行识别客户端、配置 MCP 并做只读验证；缺少连接密钥时再由用户在网页签发。文档源文件为 [agent-setup.md](frontend/public/agent-setup.md)。

后端通过官方 `mcp==2.3.0` Streamable HTTP 在 `http://127.0.0.1:10622/mcp` 提供业务工具。先由人工登录“Agent 连接”签发令牌，再由客户端运行时提供 `Authorization: Bearer …`。令牌不能作为 `/api` 人工登录会话；Cookie 也不能代替 MCP Bearer。密钥按内部使用方案保存原文，所属用户可登录后点击“查看密钥”反复查看；认证仍使用 SHA-256 摘要，列表不返回原文。允许用户将密钥粘贴到对话，由 Agent 填写本机 MCP 认证配置，无需先设置环境变量；密钥不提交仓库，不放进业务工具参数。

所有启用中的登录用户均可按需签发自己的 low，默认名称为“某某的 AI”；管理员可额外签发自己的 high。连接归属真实用户，不另建 AI 用户，业务申请沿用统一审批流程。MCP v2 的 low 只暴露 `fgas_help`、`fgas_query`、`fgas_propose`，不继承所属用户的人工自动批准权限；high 增加 `fgas_execute`。通过对象、动作及参数覆盖原有业务能力，具体参数按需查 help。连接及所属用户的启停、角色和过期时间每次调用重新检查，high 始终要求所属用户为管理员；Agent 不能管理登录用户、角色或连接。初始化说明先讲清账户、Transfer、正式流水、结算和盘点的关系，见 [核心模型](docs/ai/overview.md) 与 [完整指南](docs/ai/guide.md)。

当前客户端配置见[公开接入指南](frontend/public/agent-setup.md)，包含 Codex CLI、DSH 0.2 和 OpenCode 示例。DSH 首次自助安装推荐创造模式（`cordis`）：本机 `0.2.1-rc.3` 普通 Web 会话已验证，在用户粘贴密钥并允许一次安装后，模型自行配置官方 MCP 插件、热加载工具并提交待审批申请，无需父代理代装或重启。标准模式缺少安装工具时需先由用户配置连接；先前 SDK 试验不能代表普通创造模式的体验，见[客户端实验记录](docs/ai/2026-10-27-mcp-client-trials.md)。

也可沿用环境变量：`FGAS_MCP_URL` 为服务完整地址，`FGAS_AGENT_TOKEN` 为用户签发的连接密钥。回环地址仅供与后端同机的客户端访问；另一台机器的 `127.0.0.1` 指向它自己。当前保留 SDK 默认回环 Host 校验；自定义域名、远程 HTTPS、OAuth 和部署尚未联调。客户端不得自动重发业务写操作。

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

成功连接后阅读初始化的核心模型说明，用 `fgas_help()` 查看权限与索引，再用 `fgas_query({"resource":"me"})` 核对真实用户角色及当前连接等级，并做一次正常只读查询。按需查某一对象/动作的精确参数；完整输出 Schema 用 `include_output_schema=true`。`fgas_propose` 对两档始终 pending；`fgas_execute` 仅 high 使用，资金直接过账，货物创建只进在途，整笔完成才记库存。调用成功保存业务编号；断线后查记录并人工核对，不自动重发。低权限交接可并列给人工网页与用户已授权的 high Agent，附业务编号和现状。详情见 [Agent 指南](docs/ai/guide.md)。

从 v1 升级：原50个工具名已移除执行能力，只返回迁移提示。MCP 地址和凭据沿用，客户端需重新发现工具，硬编码旧名称的脚本需改为四入口；返回 `api_version=2`。没有数据库变更。当前仍未正式发布，实际验证与未做项见阶段记录。
