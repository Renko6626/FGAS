# FGAS 第一阶段架构

2026-10-14，自由账户与 Transfer 整理。模块化单体，单社团、人民币、独立实例。业务定义见 [Transfer 模型](docs/transfer-model.md)，实施边界见 [实施计划](docs/superpowers/plans/2026-10-14-flexible-transfer-core-plan.md)，验证与运行状态见 [阶段记录](docs/prototype-status.md)。旧阶段设计文件保留当时方案，新代码以本文及当前 Transfer 模型为准。

## 1 核心目标与第一阶段范围

记录钱和货如何变化、当前账面余额及数量、各私账原收支结清多少、谁发起批准和完成，以及如何留痕更正。核心业务覆盖资金收付、内部转账、成员报销与代收交回、采购到货、销售赠送、调拨退回、损耗、期初与阶段盘点。

社团成员私人完整余额不纳入系统，私账只记录其与社团的往来。公私货物账户均保存社团货物，外部账户表达边界，不管理商家或客户真实库存。货物按数量记录，第一阶段不估值，不推算成本或利润。

## 2 层次与依赖

```text
Vue / 人工 HTTP       Agent / MCP
    ↓
应用服务：身份、目录、审批、结算、完成、盘点、事务编排
    ↓
账本方案与内核：精确金额、平衡分录、整数数量
    ↓
基础设施适配：数据库表、查询、事务、锁、正式流水唯一性
```

内核自由表达账户间的变化，不识别印刷、采购、报销或盘点用途。服务层解释具体入口并维护授权、审核、状态、审计和业务约束；内核不能被外部入口直接调用以绕过授权。

账本基础约束为引用有效、金额/数量有效、来源去向不同、借贷平衡与数量守恒、同一条单据只正式记账一次，以及事务一致性。标签可改且不驱动这些规则。数据库外键、唯一约束与服务校验共同维护已确认的不变量，不建设通用规则引擎。

| 代码 | 职责 |
| --- | --- |
| `entrypoints` | 人工 HTTP 与 MCP 协议适配、Schema 校验和身份解析，调用应用服务 |
| `application/agent_access.py` | 独立连接凭据、真实所属用户解析与 low/high 固定授权 |
| `application/agent_queries.py`、`agent_operations.py` | 共同业务查询及明确命名的业务操作，复用原服务 |
| `application/funds.py` | 普通资金提交、审批、过账与冲销，无垫付标记判断 |
| `application/settlements.py` | 私账报销/交回匹配及未结查询，不另记付款 |
| `application/warehouse.py` | 货物审批、整笔完成、当前库存和生命周期检查 |
| `application/stock_workflows.py` | 钱货共同创建的事务编排，生命周期独立 |
| `application/stocktakes.py` | 薄盘点及专属端点组织 |
| `application/catalogs.py`、`members.py`、`warehouse_catalogs.py` | 账户、联系人、SKU、保管目录 |
| `kernel`、`modules` | 通用金额/数量和流水方案，不依赖 FastAPI 或具体业务表单 |
| `infrastructure` | 持久化、快照查询、事务与已有简单写锁，不独立决定业务策略 |

## 3 技术与实例边界

沿用 FastAPI、SQLAlchemy、PostgreSQL、Vue 3、TypeScript、Vite 和 Naive UI，不新建微服务、队列、缓存或多主同步。每实例仅一个社团，仅人民币，其他社团独立部署。

认证由 `AUTH_MODE` 切换。`development` 保留账号选择，仅供本地与测试；`casdoor` 复用既有 Casdoor OIDC，使用授权码、PKCE 和签名 state，不自建密码平台。Casdoor 首次登录自动建立本地用户，默认普通用户；`INITIAL_ADMIN_SUBJECT` 只在该用户首次建号时匹配 Casdoor `sub` 或用户名并授予管理员，之后角色完全由本系统管理员维护，不从 SSO 推断过账权限。本地 `users.id` 与 Casdoor `sub` 解耦，`sso_subject` 唯一且可空；不按邮箱或用户名关联历史账号。三档角色固定为管理员、受信任用户、普通用户；业务联系人无需登录账户，联系人绑定也不赋予权限。

网页会话是数据库中的不透明 Cookie，带绝对 TTL（默认 168 小时）。停用用户或管理员强制下线会删除其全部网页会话；最后一名启用管理员不可降级或停用。MCP Agent 凭据独立于网页会话，强制下线不撤销凭据，停用用户会通过现有 active 校验阻断 Agent。Casdoor 侧登出或停用不即时撤销 FGAS 已有会话，依赖 TTL 和管理员操作。

正式部署在另一服务器从空库开始，不搬开发测试账目。部署配置提供连接、身份与密钥，初始管理员由正式配置绑定可信身份；日常启动不覆盖已配置权限。部署采用下述 Docker Compose 路线，当前开发环境不视为生产验收。

### 部署与维护

2026-10-22 用户进一步确认采用 Docker Compose，统一管理 PostgreSQL 14、Python 3.13 后端、内置 Nginx 的静态前端。Node 22 只参与镜像构建；目标 Linux amd64 服务器不需要 Python、Node、PM2 或 uv。Nginx 提供网页和接入指南，将 /api 与 /mcp 转发到后端。数据库与后端不映射主机端口，网页默认映射127.0.0.1:8080。

发布保留两条路径：本机构建完整镜像并通过 SSH 传包加载；GitHub Actions 构建镜像并发布 GHCR，服务器拉取。两者共用运行 Compose 和启动脚本，持久配置位于部署根目录.env，数据库位于固定 fgas_postgres-data 卷。首次初始化显式执行，普通启动与更新不建表、不清库、不自动迁移。版本升级 SQL 及备份由维护者按版本说明安排。

工作流在版本标签或手动触发时构建，通过容器启动与反向代理检查后发布。配置服务器凭据并启用后可经 SSH 自动更新；不新增发布服务、队列或自动回滚。开发用 npm run dev 保持原有行为，PM2 方案保留备用。操作说明见 [deploy/README.md](deploy/README.md)。

## 4 数据结构

### 账户与成员

`FundAccount/fund_accounts` 与 `StockAccount/stock_accounts` 共用 `id/name/kind/member_id/avatar_url/tags/active`。`kind` 为公账、私账、外部，创建后不可变。可选成员关联表示对应人/联系人，独立于类型；名称、联系人、头像、标签和启用状态可修改。

SKU 保存名称、规格、单位、启用状态及可空 `avatar_url`，缩略图只用于目录和货物显示，不影响库存规则；已被引用的单位仍固定。货物账户和 SKU 的图片 URL 可修改或清空。文字头像按名称生成稳定配色，不增加颜色存储字段。

成员仅保存 `id/name/note`，不自动开账户、不强制唯一账户、不联动账户名称。`StockAccountCustody/stock_account_custodies` 单独记录保管成员与起止、操作人，联系人不是保管历史。

余额和数量从正式流水计算。资金余额统一借方减贷方即流入减流出，公账合计只计公账。私账为正表示应交回，为负表示社团应偿还。停用不影响历史统计，阻止新单但允许已有单处理。

### 转移与正式记录

资金 `Transfer/transfers` 保留两端、金额分、日期、可选说明/往来方、标签、状态、发起审批、版本、冲销引用及创建时间；`JournalLine/journal_lines` 是正式平衡分录。

货物 `StockTransfer/stock_transfers` 使用账户两端、日期、可选说明/标签/原单引用/原始单据引用、状态及审批记录，明细可含多 SKU，数量为正整数。`StockConfirmation` 保存额外整笔完成申请，`StockMove` 是唯一正式数量流水。不保存父批次、部分完成、预留或虚拟在途库存。

原单引用用于追溯，只要求存在且非自身，不匹配用途、状态、地点或 SKU。关联不能替代结算计算关系，也不扩展通用关系表。

### 双向结算

`SettlementMatch/settlement_matches` 只保存结算 Transfer、原收支 Transfer 和匹配金额。两 Transfer ID 联合主键，无独立结算单、报销认可状态或成员字段。

服务检查同一私账、相应方向、已过账、正金额、非重复及不超两端剩余额。报销：私账→外部配公账→私账；代收交回：外部→私账配私账→公账。部分和多笔匹配可用，付款可以有未匹配金额；不自动抵扣不同方向。

Transfer 的批准即已认可收支，普通用户待审、可信用户代录自动批准。匹配由可信用户办理。任何一端被冲销后匹配失效但历史保留，不直接改账、不级联冲销；页面显示对应原收支未结或付款未匹配金额，由用户核对更正。

### 薄盘点

资金与货物仍各一张薄盘点表，只保存名称、说明、进行中/结束、创建信息和两个专属外部账户。账户归属固定，标签不决定归属。盘点不改变余额或数量，普通 Transfer 才表达盘盈盘亏。

详情查任何一端涉及两账户的全部状态记录，包含反向更正；资金额外包含直接冲销。结束不截断日期、不撤销已有转移，端点默认隐藏但仍可补录。不建立结构化实点明细、自动差异计算或差异结清流程。

## 5 服务流程与更正

可信用户普通资金记录自动过账，普通用户待人工审批；每次成功提交是独立记录，没有请求去重或完整回放。资金正式过账产生借贷平衡分录，错误以关联原单的冲销、更正处理，不覆盖历史。

货物批准只进在途，不扣库存；额外整笔完成才产生 StockMove。普通用户完成申请待可信用户审批，可信用户确认直接完成。现阶段出库不得造成组织库存负数、禁止外部到外部，规则归货物服务；账户/SKU 停用不阻止旧单完成。完成后不取消或覆盖数量，实际退回或更正新增普通转移。

钱货联合入口同一数据库事务，失败整体回滚；批准付款不表示到货、完成到货不再付款、取消货物不自动退钱、冲销资金不自动退货。已有资金记录可引用，不重复创建。

审核与执行身份、业务内容和结果在服务层组织审计。已有简单串行锁内重新读取必要状态并正式写入，不引入一般恢复状态机、幂等键、自动重试、Outbox 或通用工作流。网络结果不确定先查记录，独立重复录入留痕更正。

## 6 查询与验证

页面分别展示公账余额、私账净往来与逐笔未结、实际货物数量、在途计划量及普通状态。标签、类型与联系人支持查找，保管人独立筛选。库存价值显示未估值，不显示为零价值或利润。

验证复用已有真实 PostgreSQL/API 测试框架；关键新行为补覆盖，不按每次修改机械新增测试。前端运行类型检查和构建，UI 至多截图，不自动点击或填表。集中检查通过后结束验证，遇新改动或具体问题再做相关检查，不扩展 CI 环境。

## 7 重建、上线配套与后续边界

用户允许本轮破坏性更新，显式重建开发 FGAS 应用表，包含退役表；不引入 Alembic、旧接口兼容或旧账目迁移。普通启动不清库，测试仅运行于 `fgas_test`。当前权威账本是单数据库，不将成员散放货物解释为数据库分布式同步。

正式使用前需确认期初日期、公账资金、私账往来及各账户 SKU 数量，通过普通期初记录建立，并保留不足的原始依据。正式 SSO、票据附件、生产部署和备份恢复仍需后续落实。附件按既有私有存储方向实施，不能随意公开；数据库与附件备份应保存对应恢复时点和版本信息，在空环境验证基本恢复，不把开发备份搬成正式账本。不在本次新增实现。

第二阶段再设计取得成本、批次、估值及销售成本，后续再设计经营归属、分摊和管理分析，不根据第一阶段付款自动推库存价值。正式事实不能因分析口径变化自动重写。第一阶段不建立订单、完整报表、复杂寄售结算、备用金专用流程、CRM、人事、自动 POS 导入。Agent/MCP 接入按下节实现，外部集成必须经过相同服务与账本校验，不直接写数据库或绕过授权。

## 8 Agent/MCP 接入（v2，开发阶段）

官方 Python MCP SDK 2.3.0 提供 `/mcp` Streamable HTTP，FastAPI lifespan 启停 SDK session manager。Bearer 中间件覆盖初始化、发现和调用，并通过请求 ContextVar 传递令牌；每次工具调用在同一业务事务重新解析凭据和真实 User。人工 `/api` 只用 Cookie，连接管理也只供人工会话。应用层不依赖 entrypoints 或协议 Schema。

`AgentCredential/agent_credentials` 保存 ID、所属用户、名称、low/high、启用、到期、创建时间和 SHA-256 摘要，不保存明文。可信用户仅自己的 low，管理员可自己的 low/high，只能停用他人的连接。实际授权同时检查凭据及所属用户；不改变 User.role，不新增对象白名单、grant 矩阵或只读第三档。

low 暴露 help/query/propose，high 再增加 execute，共3/4个公开工具。所有原有业务能力通过固定 resource/action 组合保留，列表与详情共用 query。MCP 适配层的 agent_catalog 契约表共用于帮助、精确参数校验与固定函数分派，应用层不反向依赖它。公开 Schema 只声明小型外壳，具体操作参数按需由 help 返回，服务端仍按选中的输入/输出模型校验。propose 对两档始终待审，execute 及其应用函数均校验 high。返回结构化结果及同内容文本。查询按固定字段过滤，目录按名称/ID排序、业务按创建时间/ID倒序，page/limit/has_more 标明分页；业务日期闭区间、带时区录入时间左闭右开。当前连接来源过滤由服务端取凭据 ID，货物通过主单来源或完成申请 EXISTS 匹配后分页，不重复父单。事件列表（资金单、货物单、货物流水）默认最近 30 天按 `created_at` 录入时间，`all_time=true` 或显式时间条件才查更早/全量；`identifier` 详情不受窗口影响。`fund_balances` 和 `inventory` 支持 `as_of`/`basis`：默认按 `transfers.posted_at` 或 `stock_moves.created_at` 的过账时间，`basis=effective_date` 按业务日期；库存 as-of 只计算 on-hand，历史在途不可用。

三种 propose 对管理员所属 high 也固定待审。资金 direct 过账、货物 direct 在途、完成 direct 才写 StockMove。`submit_mode` 仅服务内部参数，客户端不能指定。资金和货物主单、完成申请记录 `submitted_credential_id/name`；审计记录实际操作者 `agent_credential_id/name`，审批/执行快照保留连接。`approval_mode` 区分 `agent_direct`、`agent_approval` 及人工既有 automatic/manual，改连接名称不覆盖历史快照。原历史字段为空时仍按人工记录解释。

结果使用 `api_version='2'`，写入明确 resource_type、业务 ID、status、ledger_effect_applied、approval_required；完成同时给 confirmation_id 和 stock_transfer_id。金额保留整数分并配元字符串；Patch 省略保留，仅允许清空的字段接受 null。输入错误返回 validation_error、字段位置及可调用的帮助参数；业务错误保留 permission_denied、not_found、state_conflict，服务端错误为 internal_error。pending 是普通成功，无自动重试、幂等回放、恢复队列或 OAuth 服务。

核心模型说明 docs/ai/overview.md 随初始化 instructions 提供，并用于 help 默认响应；完整业务指南按需读取。首层解释账户、Transfer、流水与余额/库存的关系，私账方向、资金/货物独立生效、结算匹配及薄盘点，避免模型单凭工具名称推断业务。

v2 直接替换旧公开工具名；旧名只返回 tool_migrated，不调用旧动作。客户端重连/重新发现，固定旧名脚本需更新；地址、凭据与业务数据不变。仍未正式发布。

旧库升级仅显式执行 `scripts/upgrade-agent-access.sql`、`scripts/upgrade-user-auth.sql` 和 `scripts/upgrade-posted-at.sql` 的非破坏性增量；普通启动不升级旧表。本轮日常开发库升级未执行，运行验证仅使用专用 fgas_test。具体命令、客户端版本和联调限制见阶段记录。
