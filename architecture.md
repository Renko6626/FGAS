# FGAS 第一阶段架构

2026-10-14 建立自由账户与 Transfer 架构，当前状态核对至 2026-10-25。模块化单体，单社团、人民币、独立实例。业务定义见 [Transfer 模型](docs/transfer-model.md)，实施边界见 [实施计划](docs/superpowers/plans/2026-10-14-flexible-transfer-core-plan.md)，验证与运行状态见 [阶段记录](docs/prototype-status.md)。旧阶段设计文件保留当时方案，新代码以本文及当前 Transfer 模型为准。

2026-10-27 范围收敛：薄盘点暂时停用，网页不显示入口，HTTP 路由拒绝访问并从 OpenAPI 隐藏，MCP 不发现或接受盘点资源。盘点代码与表保留，下文盘点结构为休眠实现。恢复由现有盘点模块的 `ENABLED` 与 `frontend/src/features.ts` 的常量控制，不增加运行时开关平台。货物在途及整笔完成流程保留；历史余额／库存查询默认实际入账时间，业务日期作为明确指定的备选。货物账户统一为 internal/external；完整内容快照删除，审计仅保留操作信息，前端不显示原始 JSON。本轮开发数据按用户授权备份后重建。

## 1 核心目标与第一阶段范围

记录钱和货如何变化、当前账面余额及数量、各私账原收支结清多少、谁发起批准和完成，以及如何留痕更正。核心业务覆盖资金收付、内部转账、成员报销与代收交回、采购到货、销售赠送、调拨退回、损耗、期初与阶段盘点。

社团成员私人完整余额不纳入系统，私账只记录其与社团的往来。货物账户仅分 `internal` 实际保管和 `external` 外部，实际保管含社团仓库及成员长期代管；外部账户表达边界，不管理商家或客户真实库存。货物按数量记录，第一阶段不估值，不推算成本或利润。

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
| `application/identity.py` | 人工身份与会话、用户管理，以及共用的可信角色和目录写入授权检查 |
| `application/directory_views.py` | 联系人、账户、SKU 与负责人信息的基础视图；人工和 Agent 查询保留各自的输出字段 |
| `application/agent_access.py` | 独立连接凭据、真实所属用户解析与 low/high 固定授权 |
| `application/agent_queries.py`、`agent_operations.py` | 共同业务查询及明确命名的业务操作，复用原服务 |
| `application/funds.py` | 普通资金提交、审批、过账与冲销，无垫付标记判断 |
| `application/settlements.py` | 私账报销/交回匹配、单私账详情及跨私账未匹配明细查询；匹配本身不另记付款 |
| `application/warehouse.py` | 货物审批、整笔完成、当前库存和生命周期检查 |
| `application/stock_workflows.py` | 钱货共同创建的事务编排，生命周期独立 |
| `application/stocktakes.py` | 薄盘点及专属端点组织 |
| `application/catalogs.py`、`members.py`、`warehouse_catalogs.py` | 账户、联系人、SKU、负责人历史 |
| `kernel`、`modules` | 通用金额/数量和流水方案，不依赖 FastAPI 或具体业务表单 |
| `infrastructure` | 持久化、快照查询、事务与已有简单写锁，不独立决定业务策略 |
| `infrastructure/inventory_queries.py` | 库存 SQL、筛选、分页与汇总查询；应用层组织数量格式及返回结果 |

前端按数据加载与记录展示分工：`App.vue` 保留工作台壳、导航和全局编辑入口，会话及工作台资料加载由 composable 组织；API 类型和调用按身份、账户、成员、资金与货物等现有业务归属存放。资金和货物列表页面负责远程筛选与分页，盘点详情使用本地记录容器，两者共用记录展示和详情操作组件。资金关联搜索与账户筛选只复用已有简单逻辑，不增加通用查询框架或状态管理依赖。

## 3 技术与实例边界

沿用 FastAPI、SQLAlchemy、PostgreSQL、Vue 3、TypeScript、Vite 和 Naive UI，不新建微服务、队列、缓存或多主同步。每实例仅一个社团，仅人民币，其他社团独立部署。

认证由 `AUTH_MODE` 切换。`development` 保留账号选择，仅供本地与测试；`casdoor` 复用既有 Casdoor OIDC，使用授权码、PKCE 和签名 state，不自建密码平台。Casdoor 首次登录自动建立本地用户，默认普通用户；`INITIAL_ADMIN_SUBJECT` 只在该用户首次建号时匹配 Casdoor `sub` 或用户名并授予管理员，之后角色完全由本系统管理员维护，不从 SSO 推断过账权限。本地 `users.id` 与 Casdoor `sub` 解耦，`sso_subject` 唯一且可空；不按邮箱或用户名关联历史账号。三档角色固定为管理员、受信任用户、普通用户；业务联系人无需登录账户，联系人绑定也不赋予权限。

网页会话是数据库中的不透明 Cookie，带绝对 TTL（默认 168 小时）。停用用户或管理员强制下线会删除其全部网页会话；最后一名启用管理员不可降级或停用。MCP Agent 凭据独立于网页会话，强制下线不撤销凭据，停用用户会通过现有 active 校验阻断 Agent。Casdoor 侧登出或停用不即时撤销 FGAS 已有会话，依赖 TTL 和管理员操作。

人工 HTTP 入口统一使用 `Depends(database, scope="function")`：响应内容生成后、发送成功响应前提交数据库事务，使紧接着的请求能读取刚保存的会话或业务记录；提交失败时不先发送成功响应。FastAPI 最低版本为 `0.121.1`。

正式部署在另一服务器从空库开始，不搬开发测试账目。部署配置提供连接、身份与密钥，初始管理员由正式配置绑定可信身份；日常启动不覆盖已配置权限。部署采用下述 Docker Compose 路线，当前开发环境不视为生产验收。

### 部署与维护

2026-10-22 用户进一步确认采用 Docker Compose，统一管理 PostgreSQL 14、Python 3.13 后端、内置 Nginx 的静态前端。Node 22 只参与镜像构建；目标 Linux amd64 服务器不需要 Python、Node、PM2 或 uv。Nginx 提供网页和接入指南，将 /api 与 /mcp 转发到后端。数据库与后端不映射主机端口，网页默认映射127.0.0.1:8080。

发布保留两条路径：本机构建完整镜像并通过 SSH 传包加载；GitHub Actions 构建镜像并发布 GHCR，服务器拉取。两者共用运行 Compose 和启动脚本，持久配置位于部署根目录.env，数据库位于固定 fgas_postgres-data 卷。首次初始化与普通更新都通过 Compose 一次性 `migrate` 服务执行 `alembic upgrade head`；API 依赖迁移成功后才启动。发布前自动 `pg_dump` 备份，迁移失败即停止发布；不自动清库、不自动 downgrade。

数据库迁移以 Alembic 为唯一 schema 演进路径，`backend/migrations/versions/0001_baseline_schema.py` 是当前基线；本轮编号经用户确认仅同步现有 `0001`，不迁移旧库；此后模型变更须新增 revision，不能回到 `create_all` 或手写升级 SQL。在线迁移使用独立 advisory lock，避免并发执行；测试在独立临时库验证 upgrade/check/downgrade。历史 `scripts/upgrade-*.sql` 只用于收养基线前旧库：备份、执行、校验后 `alembic stamp 0001`。

工作流在版本标签或手动触发时构建，通过容器启动与反向代理检查后发布。配置服务器凭据并启用后可经 SSH 自动更新；不新增发布服务、队列或自动回滚。开发用 npm run dev 保持原有行为。Compose 为新部署首选；明确不使用 Docker 时，可采用 `deploy/*.service` 提供的 systemd 原生方式；PM2 仅作为兼容备选保留。各路线的定位以 [deploy/README.md 的对照表](deploy/README.md)为准，原生操作见 [deploy/README.native.md](deploy/README.native.md)。

## 4 数据结构

### 账户与成员

`FundAccount/fund_accounts` 与 `StockAccount/stock_accounts` 公开目录共用 `code/name/kind/avatar_url/tags/active`。资金账户内部保存可空 member_id 联系人，`kind` 为 `public/private/external`；货物账户为 `internal/external`，不保存独立联系人列，公开返回的 member_code/member_name 来自当前负责人历史记录。两类账户的 kind 创建后不可变。可选成员关联表示对应人/联系人，独立于类型；名称、联系人、头像、标签和启用状态可修改。

SKU保留内部ID，并以必填唯一code作为业务入口，去首尾空格并转大写，创建/编辑都拒绝重号。name包含规格与款式，不再单列specification；tags表达类别、角色等简单分类。目录支持code精确查询、q搜索代号/名称和tag筛选，编辑按code定位；库存/货物/数量流水公开筛选与货物明细用sku_code，服务解析内部关联。数量流水保留内部外键，输出同时给出可读代号。用户2026-10-27确认直接同步0001，不做迁移/回填/兼容，不自动重建日常开发库。

SKU另存单位、启用状态及可空avatar_url，已被引用的单位固定。货物账户和SKU的图片URL可修改或清空；文字头像按名称生成稳定配色，不增加颜色字段。

成员公开目录使用 `code/name/note`，不自动开账户、不强制唯一账户、不联动账户名称。`StockAccountCustody/stock_account_custodies` 是货物账户负责人的唯一来源，保存成员、起止时间及设置/结束操作者；create/update 的 member_code 维护该历史，普通列表只投影当前负责人，账户详情才返回完整历史。外部端点也可指定负责人。

余额和数量从正式流水计算。资金余额统一借方减贷方即流入减流出，公账合计只计公账。私账为正表示应交回，为负表示社团应偿还。停用不影响历史统计，阻止新单但允许已有单处理。

### 转移与正式记录

资金 `Transfer/transfers` 保留两端、金额分、日期、可选说明/往来方、标签、状态、发起审批、版本、冲销引用及创建时间；`JournalLine/journal_lines` 是正式平衡分录。

货物 `StockTransfer/stock_transfers` 使用账户两端、日期、可选说明/标签/原单引用/原始单据引用、状态及审批记录，明细可含多 SKU，数量为正整数。`StockConfirmation` 保存额外整笔完成申请，`StockMove` 是唯一正式数量流水。不保存父批次、部分完成、预留或虚拟在途库存。

货物不保存批准或执行的完整内容快照。`StockAudit.detail` 仅保存操作原因、状态、批准方式及必要的申请／资金引用编号，操作人、时间和 Agent 来源沿用审计自身字段；不复制账户、SKU 或单据内容。前端通过对应完成审计展示批准方式和连接。2026-10-27 用户明确授权直接同步 `0001` 基线、备份并重建开发 FGAS 表，本轮不新增 migration、回填或兼容。

原单引用用于追溯，只要求存在且非自身，不匹配用途、状态、地点或 SKU。关联不能替代结算计算关系，也不扩展通用关系表。

### 双向结算

`SettlementMatch/settlement_matches` 只保存结算 Transfer、原收支 Transfer 和匹配金额。两 Transfer ID 联合主键，无独立结算单、报销认可状态或成员字段。

服务检查同一私账、相应方向、已过账、正金额、非重复及不超两端剩余额。报销：私账→外部配公账→私账；代收交回：外部→私账配私账→公账。部分和多笔匹配可用，付款可以有未匹配金额；不自动抵扣不同方向。

Transfer 的批准即已认可收支，普通用户待审、可信用户代录自动批准。匹配由可信用户办理。任何一端被冲销后匹配失效但历史保留，不直接改账、不级联冲销；页面显示对应原收支未结或付款未匹配金额，由用户核对更正。

人工 `GET /api/settlement-outstanding` 与 MCP query resource `settlement_outstanding` 共用结算应用服务，在同一只读快照中按现有有效匹配规则计算各普通已过账单的剩余额。按私账、费用/代收方向、原收支/结算付款类型筛选，跨全部历史排序分页，不从账户净余额推断未结；原收支和付款是关系两侧，不设全局金额相加汇总。MCP low/high 均可查询，保存关联仍只经 high 的 settlement/create、match；不新增顶层工具、存储或审批流程。

### 薄盘点

资金与货物仍各一张薄盘点表，只保存名称、说明、进行中/结束、创建信息和两个专属外部账户。账户归属固定，标签不决定归属。盘点不改变余额或数量，普通 Transfer 才表达盘盈盘亏。

详情查任何一端涉及两账户的全部状态记录，包含反向更正；资金额外包含直接冲销。结束不截断日期、不撤销已有转移，端点默认隐藏但仍可补录。不建立结构化实点明细、自动差异计算或差异结清流程。

## 5 服务流程与更正

可信用户普通资金记录自动过账，普通用户待人工审批；每次成功提交是独立记录，没有请求去重或完整回放。资金正式过账产生借贷平衡分录，错误以关联原单的冲销、更正处理，不覆盖历史。

货物批准只进在途，不扣库存；额外整笔完成才产生 StockMove。普通用户完成申请待可信用户审批，可信用户确认直接完成。现阶段出库不得造成组织库存负数、禁止外部到外部，规则归货物服务；账户/SKU 停用不阻止旧单完成。完成后不取消或覆盖数量，实际退回或更正新增普通转移。

钱货联合入口同一数据库事务，失败整体回滚；批准付款不表示到货、完成到货不再付款、取消货物不自动退钱、冲销资金不自动退货。已有资金记录可引用，不重复创建。

审核与执行身份、业务内容和结果在服务层组织审计。已有简单串行锁内重新读取必要状态并正式写入，不引入一般恢复状态机、幂等键、自动重试、Outbox 或通用工作流。网络结果不确定先查记录，独立重复录入留痕更正。

## 6 查询与验证

页面分别展示公账余额、私账净往来与逐笔未结、实际货物数量、在途计划量及普通状态。标签、类型与关联人员支持查找，货物目录与库存均按 member_code 筛选当前负责人。库存价值显示未估值，不显示为零价值或利润。当前库存行分别显示待完成流入、流出；逐 SKU 汇总区分组织外部流入、组织外部流出、内部调拨，内部调拨每条只计一次。历史查询的计划量为 null，表示无法重建过去在途。

2026-10-26 确认成员私账尽量归零、非零及时处理的管理原则；在及时清理成员往来的前提下，日常可用资金沿用公账余额口径，不新增净额可用余额指标。首页利用已有账户列表展示全部 `kind=private` 且 `balance_minor != 0` 的账户，包含未绑定联系人和已停用账户，分别标明成员应交回或社团应偿还的金额并分方向汇总。存在提醒时应先核对处理未清往来，公账金额仍表示账面资金；私账归零不等于逐笔匹配全部完成。此展示复用现有前端数据与结算入口，不增加接口、数据库字段或自动处理流程。

验证复用已有真实 PostgreSQL/API 测试框架；关键新行为补覆盖，不按每次修改机械新增测试。前端运行类型检查和构建，UI 至多截图，不自动点击或填表。集中检查通过后结束验证，遇新改动或具体问题再做相关检查，不扩展 CI 环境。

## 7 重建、上线配套与后续边界

2026-10-22 以当前模型重建开发 FGAS 应用表，并以 Alembic `0001` 作为基线；此后 schema 只通过 revision 演进，不再用 `create_all` 或手写 SQL 升级。开发入口 `npm run dev` 经 `scripts/run-backend.sh` 执行初始化与 `alembic upgrade head`，保留已有业务数据；直接启动 Uvicorn 不执行迁移。Compose 发布脚本先备份，再由一次性 `migrate` 服务执行迁移；原生部署按其独立步骤操作。测试仅运行于 `fgas_test`，迁移测试使用独立临时库。当前权威账本是单数据库，不将成员散放货物解释为数据库分布式同步。

正式使用前需确认期初日期、公账资金、私账往来及各账户 SKU 数量，通过普通期初记录建立，并保留不足的原始依据。Casdoor 登录代码与 mock IdP 测试已实现，真实 SSO、域名与 HTTPS、生产发布和备份恢复仍未验收；票据附件尚未实现。附件按既有私有存储方向实施，不能随意公开；数据库与附件备份应保存对应恢复时点和版本信息，在空环境验证基本恢复，不把开发备份搬成正式账本。不在本次新增实现。

2026-10-26 已确认的后续方向：图片附件作为下一步开发待办，统一图片文件夹存储，每条资金或货物转移可关联多张图片；关联数据、上传与访问接口在实施前确认。活动收支沿用名称、说明辅助查找和现有转移 `tags` 分类，后续按标签汇总，不新增独立活动模块。标签录入及筛选已有实现，图片附件与活动收支汇总尚未实现；汇总口径需避免原始收支与结算往来重复计数。

第二阶段再设计取得成本、批次、估值及销售成本，后续再设计经营归属、分摊和管理分析，不根据第一阶段付款自动推库存价值。正式事实不能因分析口径变化自动重写。第一阶段不建立订单、完整报表、复杂寄售结算、备用金专用流程、CRM、人事、自动 POS 导入。Agent/MCP 接入按下节实现，外部集成必须经过相同服务与账本校验，不直接写数据库或绕过授权。

## 8 Agent/MCP 接入（v2，开发阶段）

官方 Python MCP SDK 2.3.0 提供 `/mcp` Streamable HTTP，FastAPI lifespan 启停 SDK session manager。Bearer 中间件覆盖初始化、发现和调用，并通过请求 ContextVar 传递令牌；每次工具调用在同一业务事务重新解析凭据和真实 User。人工 `/api` 只用 Cookie，连接管理也只供人工会话。应用层不依赖 entrypoints 或协议 Schema。

`AgentCredential/agent_credentials` 保存 ID、所属用户、名称、low/high、启用、到期、创建时间、SHA-256 摘要及密钥原文。原文按用户确认的社团内部使用方案保存，仅所属用户通过人工 Cookie 会话的 `GET /api/agent-credentials/{id}/secret` 再次查看，响应禁止缓存；列表不返回密钥，管理员也不能查看他人的密钥。认证仍按摘要检索。2026-10-26 用户确认尚未正式实装密钥机制，本次新增原文列直接同步模型与建库基线 `0001`，不新增迁移、旧密钥兼容或回退逻辑。所有启用中的登录用户均可按需管理自己的 low，前端默认名称为“某某的 AI”；管理员可额外管理自己的 high，并可停用他人的连接。连接归属真实用户，不另建 AI 用户、业务联系人或资金账户。low 不继承所属用户的人工自动批准权限，三种写申请进入原有统一审批，来源只用于追溯。实际授权同时检查凭据及所属用户；停用用户阻断全部连接，high 始终要求管理员身份，普通用户或受信任用户间的角色变化不阻断 low。不改变 User.role，不新增审批分类、对象白名单、grant 矩阵或只读第三档。

low 暴露 help/query/propose，high 再增加 execute，共3/4个公开工具。query 的单对象 `me` 来自当前 AgentAccess，分别报告登录用户角色与连接等级；管理员 low 不因此得到 high 执行权限。FA/SA/M/FT/ST/SC 为自动不可编辑的稳定业务编号，公开业务引用与筛选使用 code，内部 UUID 继续承担关联。资金与货物详情可由网页 hash code 定位，结算可由 FA code 定位；打开链接只读取记录。所有原有业务能力通过固定 resource/action 组合保留，列表与详情共用 query。MCP 适配层的 agent_catalog 契约表共用于帮助、精确参数校验与固定函数分派，应用层不反向依赖它。公开 Schema 只声明小型外壳，具体操作的 help 默认只返回说明、精确输入 Schema 和示例，`include_output_schema=true` 才附完整输出 Schema；服务端仍按选中的输入/输出模型校验。状态分别按资金/货物枚举校验，help 的 resource/action 也从固定契约表声明枚举。propose 对两档始终待审，execute 及其应用函数均校验 high。返回结构化结果及同内容文本。查询按固定字段过滤，目录按名称/内部键排序、业务按创建时间/内部键倒序，page/limit/has_more 标明分页；库存和货物流水直接使用数据库分页与总数，库存 totals 汇总全部筛选结果，货物列表仅读取列表所需资料；联系人提供 note，货物账户通过 member_code/member_name 提供负责人，identifier 详情含 responsibility_history；业务日期闭区间、带时区录入时间左闭右开。当前连接来源过滤由服务端取凭据 ID，货物通过主单来源或完成申请 EXISTS 匹配后分页，不重复父单。事件列表（资金单、货物单、货物流水）默认最近 30 天按 `created_at` 录入时间，`all_time=true` 或显式时间条件才查更早/全量；`identifier` 详情不受窗口影响。`fund_balances` 和 `inventory` 支持 `as_of`/`basis`：默认按 `transfers.posted_at` 或 `stock_moves.created_at` 的过账时间，`basis=effective_date` 按业务日期；库存 as-of 只计算 on-hand，历史在途行字段和汇总字段均返回 null。当前计划仅统计已批准、未整笔完成的货物单；筛选后的明细按原账户类型判定进出组织及内部调拨，内部调拨只计一次，分页 totals 重复全筛选范围。

三种 propose 对管理员所属 high 也固定待审。资金 direct 过账、货物 direct 在途、完成 direct 才写 StockMove。`submit_mode` 仅服务内部参数，客户端不能指定。资金和货物主单、完成申请记录 `submitted_credential_id/name`；审计记录实际操作者 `agent_credential_id/name`。主单 `approval_mode` 及完成审计的 mode 区分 `agent_direct`、`agent_approval` 及人工既有 automatic/manual，连接改名不覆盖已保存的来源名称。

结果使用 `api_version='2'`，写入明确 resource_type、业务 code、status、ledger_effect_applied、approval_required；完成同时给 confirmation_code 和 stock_transfer_code。金额保留整数分并配元字符串；Patch 省略保留，仅允许清空的字段接受 null。输入错误返回 validation_error、字段位置及可调用的帮助参数；业务错误保留 permission_denied、not_found、state_conflict，服务端错误为 internal_error。pending 是普通成功，无自动重试、幂等回放、恢复队列或 OAuth 服务。

核心模型说明 docs/ai/overview.md 随初始化 instructions 提供，并用于 help 默认响应；工具描述明确首次使用先调用 help，以兼容不注入初始化 instructions 的客户端。完整业务指南按需读取。首层解释账户、Transfer、流水与余额/库存的关系，私账方向、资金/货物独立生效、结算匹配及薄盘点，避免模型单凭工具名称推断业务。

v2 直接替换旧公开工具名；旧名只返回 tool_migrated，不调用旧动作。客户端重连/重新发现，固定旧名脚本需更新；地址、凭据与业务数据不变。仍未正式发布。

新装与升级统一执行 Alembic revision；`0001_baseline_schema.py` 包含 Agent 凭据、SSO、`transfers.posted_at` 等全部当前结构。旧库若不可丢弃，先备份并显式执行 `scripts/upgrade-agent-access.sql`、`scripts/upgrade-user-auth.sql`、`scripts/upgrade-posted-at.sql`，校验 schema 与基线一致后 `alembic stamp 0001`；可丢弃的旧库直接重建。有 FGAS 表但无 Alembic 版本记录的旧库不会在普通启动时自动收养；迁移失败即停止，不自动降级。具体命令、客户端版本和联调限制见阶段记录。

2026-10-27 Agent 定向复测已完成：13个最新选定场景为11通过、2回答部分符合（人工入口/权限措辞），共18轮，保留早轮反例；不代表全26场景或生产验收。版本、状态与答案分判、软件检查及基准清理见 [定向复测记录](docs/ai/2026-10-27-agent-access-followup.md)。
