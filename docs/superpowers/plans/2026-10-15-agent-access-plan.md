# FGAS Agent 接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户的工作约定优先：不机械新增测试、不逐步全量检查、不逐任务提交或反复完整复审。

**Goal:** 让外部 MCP 客户端读取 FGAS 业务信息，使用低权限连接提交待审申请，使用高权限连接办理现有业务，并由人工管理连接。

**Architecture:** 在现有 FastAPI 后端挂载 `/mcp`，入口认证后把真实用户和连接上下文交给 Agent 应用接口；业务操作继续调用现有资金、货物、目录、结算和盘点服务。固定 `low/high` 两档共用业务读取，提议工具固定待审，直接工具仅供高权限使用。首版不另建 Agent HTTP 业务入口。

**Tech Stack:** 现有 Python 3.13、FastAPI、SQLAlchemy、PostgreSQL、Pydantic、Vue 3、TypeScript、Naive UI；拟新增官方 Python SDK `mcp==2.3.0`。

**Spec:** [Agent 接入设计](../specs/2026-10-15-agent-access-design.md)，执行时与本计划一起读取。

**状态：** 2026-10-15，仅规划，尚未实施。MCP 首版、两档权限及业务范围已确认；SDK、挂载、凭据与来源字段、服务接口等具体技术方案仍须整体确认后实施。本计划不代表已获数据库升级、依赖安装或正式部署授权。

## 全局约束

- 仅 `admin/trusted` 可签发自己的连接；`trusted` 只能签发和维持 `low`，`admin` 可签发 `low/high`；`untrusted` 不可签发。
- 两档共享相同业务读取工具与输出。`low` 只能另做资金转移、货物转移、完成申请三种待审提交，不能创建或维护账户、SKU、联系人、保管或盘点。
- `high` 覆盖现有业务操作；所有 Agent 均不能管理登录用户、角色或连接，也不能覆盖正式账本历史。
- 不增加对象白名单、来源/去向授权、业务文本开关、grant 能力矩阵或第三种只读等级。
- 不改写 `User.role`，不伪造普通用户；不改人工会话的现有角色语义。令牌不作为人工 HTTP 登录会话。
- 不新增模型 SDK、独立 Agent 运行器、OAuth 服务、HTTP 业务双入口、请求队列、自动重试、幂等回放或恢复机制。
- 现有开发库只能在明确目标后显式非破坏性升级；普通启动不自动升级旧表，不静默 reset，不引入迁移框架。
- 保持模块职责和依赖方向；应用层不导入 `entrypoints`。新增 Schema 只供适配层校验，业务服务继续接收字典和现有模型。
- 文案自然具体，不使用“xxx · xxx”拼接。UI 验证最多必要截图，不自动点击、填写或执行浏览器交互流程。
- 使用现有真实 PostgreSQL/API 验证框架；新增测试只覆盖核心缺口，完整改动后集中检查，不建设新测试工程或 CI 矩阵。

## 审阅重点

- 管理员持有 `low` 时仍须三种提交全部待审，`high` 调用提议工具也相同；由任务 3、5 的同一业务链验证。
- 停用、过期、用户降权或停用后，新 MCP 请求拒绝；发现工具与调用工具均认证，由任务 1、6 的同一认证用例验证。
- 来源连接跟随结算、冲销及钱货联建产生的记录，人工原有路径仍工作；由任务 3 的来源链检查及已有业务测试验证。
- 同名候选、两种日期、当前连接筛选和分页可支持结果回查；由任务 4 的单个真实数据查询用例验证。
- 负数余额、元字符串和 Patch 缺省/null 不丢失含义；由任务 4、5 的代表性用例验证，不为每种目录复制场景。

## 文件职责与依赖

| 文件 | 职责及所有权 |
| --- | --- |
| `backend/infrastructure/models.py`、新建 `agent_store.py` | 任务 1：凭据及来源持久化；后续任务只消费，不平行改同一字段 |
| 新建 `backend/application/agent_access.py` | 任务 1：固定等级、凭据管理、认证、服务端访问上下文；不导入业务服务 |
| 新建 `backend/entrypoints/agent_schemas.py` | 任务 2 创建管理输入；任务 4、5 顺序扩展查询/结果 Schema，入口复用原业务输入 |
| `backend/entrypoints/http.py` | 任务 2 添加人工连接路由；任务 6 再挂载 MCP 和生命周期，不平行编辑 |
| `backend/application/funds.py`、`warehouse.py`、`settlements.py`、`stock_workflows.py`、`backend/infrastructure/store.py` | 任务 3：提交方式及来源透传，沿用原业务校验 |
| 新建 `backend/application/agent_queries.py`、`agent_operations.py` | 任务 4：查询与结果；任务 5：明确业务操作编排，不直接写账本 |
| 新建 `backend/entrypoints/mcp.py` | 任务 6：认证中间件、固定工具注册、Schema 与结果映射 |
| 新建 `frontend/src/api/agentConnections.ts`、`frontend/src/views/AgentConnectionsView.vue` | 任务 7：人工连接管理；同任务修改导航与既有记录来源显示 |
| 新建 `backend/tests/test_agent_access.py` | 单个核心接入测试文件；任务 1—6 定义所需用例，任务 8 集中运行 |
| 新建 `scripts/upgrade-agent-access.sql`；`README.md`、`architecture.md`、`docs/ai/guide.md`、`docs/prototype-status.md` | 显式增量升级、接入说明与实际验证记录；任务 1 写升级脚本，任务 8 收尾文档 |

依赖顺序：1 → 2、3、4；3、4 → 5；2、4、5 → 6；2、3 → 7；6、7 → 8。可并行处理无共享文件的准备工作；交接须保留本节约束。不得覆盖其他 agent 的修改，出现新架构决策先交主 agent 提请确认。

### 任务 1：固定访问上下文、凭据数据与增量升级

**文件：** 新建 `backend/application/agent_access.py`、`backend/infrastructure/agent_store.py`、`scripts/upgrade-agent-access.sql`；修改 `backend/infrastructure/models.py`。

**接口：** `AgentAccess(user: User, credential_id: str, credential_name: str, level: Literal['low','high'])` 为冻结数据对象；`resolve(db, bearer: str) -> AgentAccess`；`require_high(access: AgentAccess) -> None`；`source_fields(access: AgentAccess | None) -> dict`。只由服务器构造上下文，不接受模型填写。

- [ ] 确认整体技术方案及 SDK `mcp==2.3.0` 后再修改产品代码；确认实际联调客户端及其版本，未明确的“code”不自行解释。
- [ ] 新增 `AgentCredential` / `agent_credentials`：`id`、`owner_user_id`、`name`、唯一 `secret_hash`、`level`、`active`、可空 `expires_at`、`created_at`；`level` 仅允许 `low/high`，不存 grant JSON。
- [ ] 资金 `Transfer`、货物 `StockTransfer`、完成 `StockConfirmation` 各加可空 `submitted_credential_id` 与 `submitted_credential_name`；ID 外键指向凭据，名称保存提交时快照。旧记录及人工提交为空，不回填猜测来源，不删除凭据。
- [ ] 既有 `Audit`、`StockAudit` 加可空 `agent_credential_id`、`agent_credential_name`；不增加新的审计表或目录变更审计体系。
- [ ] `agent_store.py` 提供凭据按摘要查询、按 ID 查询、按 owner 列表及保存；`agent_access.resolve` 校验凭据启用、有效期和 owner 当前状态/角色。`low` owner 必须仍是 active `trusted/admin`；`high` 必须仍是 active `admin`。`require_high` 同时校验等级和真实 owner，不能只看等级。
- [ ] 生成 `secrets.token_urlsafe(32)` 随机 secret，以 SHA-256 摘要保存；明文仅创建响应返回一次。列表、日志、业务结果和 context 都不出现 secret 或 secret_hash。
- [ ] 显式 SQL 仅创建凭据表、添加上述可空列及外键；新库继续由 metadata 建表。README 将说明先确认目标库、停止相关服务、显式执行增量 SQL、核对原业务记录保留；本任务不执行 SQL，不沿用旧 reset 升级说明。

**可观察验收：** 凭据持久化不含明文；旧业务记录无需重写即可读取；上下文保留真实用户。任务 8 运行的 `test_credential_issue_limits_and_invalidation` 覆盖签发权限、停用/过期及 owner 降权，直接使用既有真实库/API 夹具。

### 任务 2：人工连接管理 API

**文件：** 扩展 `backend/application/agent_access.py`；新建 `backend/entrypoints/agent_schemas.py`；修改 `backend/entrypoints/http.py`。

**接口：** `list_credentials(db, user) -> list[dict]`、`create_credential(db, user, data: dict) -> dict`、`update_credential(db, user, identifier: str, changes: dict) -> dict`。创建返回 `{'credential': CredentialView, 'secret': str}`；其他响应只有 `CredentialView`。

- [ ] 增加 `CredentialCreate(name, level='low', expires_at=None)`、`CredentialPatch(name?, level?, active?, expires_at?)`，沿用 `extra='forbid'`；expiry 使用含时区时间。拒绝 owner、hash、secret 等客户端字段。
- [ ] 在原人工会话下提供 `GET/POST /api/agent-credentials` 和 `PATCH /api/agent-credentials/{id}`；无新建用户、代签、删除或找回 secret API。创建者只能给自己签发，trusted 不能创建或调整为 high。
- [ ] trusted 列出并管理自己的连接；admin 可列出所有连接，管理自己的连接，并停用他人的连接。非 owner 的管理员只可将 `active` 设为 false，不能借 PATCH 改他人等级、名称或归属。
- [ ] 管理服务使用现有事务与写锁习惯，刷新操作者后校验当前角色；连接改名不改历史名称快照。令牌停用不撤回待审申请或删除业务。
- [ ] `CredentialView` 返回 `id/owner_user_id/owner_name/name/level/active/expires_at/created_at`；API 继续只认人工 cookie，不增加 Bearer 回退。

**可观察验收：** 同一 `test_credential_issue_limits_and_invalidation` 通过人工 API 验证普通用户被拒、trusted 仅 low、admin 可 high、越权 PATCH 被拒、创建后列表无法再次取得 secret，不另搭 UI 权限测试。

### 任务 3：让现有业务识别提议、直接执行与来源

**文件：** 修改 `backend/application/agent_access.py`、`funds.py`、`warehouse.py`、`settlements.py`、`stock_workflows.py`、`backend/infrastructure/store.py`。

**接口：** `funds.submit`、`warehouse.submit_transfer`、`warehouse.request_completion` 保留现有参数，新增 keyword-only `access: AgentAccess | None = None`、`submit_mode: Literal['propose','direct'] | None = None`；`funds.preview` 若被接入，使用相同两参数。已有审批/冲销/结算/联建入口加可选 keyword-only `access=None`，逐层透传。

- [ ] 在 `agent_access.py` 增加小函数 `auto_apply(user: User, *, access=None, submit_mode=None) -> bool`：人工两参数省略时保持原角色行为；有 access 必须匹配真实 user 且提供明确 mode；propose 返回 false；direct 经 `require_high` 后返回 true。非法组合报错，不暴露为工具参数。
- [ ] 三个提交点通过该函数决定是否自动生效；提议始终保存 pending。直接资金提交为 posted；直接货物提交仅为 in_transit；直接完成才写 `StockMove`。不改库存约束、资金内核、事务或既有审批状态规则。
- [ ] 创建三类记录时写入 `source_fields(access)`；`funds.reverse`、`settlements.create`、`submit_stock_with_money` 调用底层提交时保留 access，Agent 调用固定直接模式，人工调用仍省略 mode。联建仍同事务，钱生效、货物在途。
- [ ] 既有 audit 写入函数和货物审批/执行快照保存实际操作连接。Agent 直接生效使用 `approval_mode='agent_direct'`，Agent 批准已有申请使用 `agent_approval`；人工仍为 automatic/manual。原提交来源与后来审批来源分别保留。
- [ ] 扩展 `funds.transfer_view`、`warehouse.transfer_view`、`confirmation_view` 及既有 audit 投影，返回新增来源；来源不从客户端 payload 读取。`request_completion` 保留现有父单返回字段并增加本次创建的 `confirmation_id`，供 Agent 结果准确引用；审批函数使用传入的申请 ID，不以“最后一条申请”推测。

**可观察验收：** 任务 5 的一条资金/货物链验证 low 和 high-propose 均无分录/数量变化、high-direct 按实际阶段生效及来源正确。已有资金、结算、货物测试继续覆盖人工行为和业务规则，不为 Agent 重复全部规则。

### 任务 4：共同读取、候选辨认及可回填结果

**文件：** 新建 `backend/application/agent_queries.py`；扩展 `backend/entrypoints/agent_schemas.py`；按需要扩展 `backend/infrastructure/agent_store.py` 的固定查询。

**接口：** 查询函数统一 `(db, access: AgentAccess, filters: dict) -> dict`，按 ID 详情为 `(db, access, identifier: str) -> dict`；命名与下表工具名去掉 `fgas_` 后对应。所有查询适用于两档；复用现有余额、库存、结算和盘点计算，不建立另一套算法。

| 工具名 | 业务来源 |
| --- | --- |
| `fgas_list_fund_accounts`、`fgas_list_stock_accounts`、`fgas_list_skus`、`fgas_list_members` | 既有目录；联系人列表默认 id/name，不塞整段备注 |
| `fgas_get_fund_balances`、`fgas_list_fund_transfers`、`fgas_get_fund_transfer` | `funds` 与既有资金存储 |
| `fgas_get_inventory`、`fgas_list_stock_transfers`、`fgas_get_stock_transfer`、`fgas_list_stock_moves` | `warehouse`、`stock_queries` |
| `fgas_get_settlement_overview` | `settlements.overview`，两档均可读完整业务概况 |
| `fgas_list_fund_stocktakes`、`fgas_get_fund_stocktake`、`fgas_list_stock_stocktakes`、`fgas_get_stock_stocktake` | `stocktakes`，固定映射 fund/stock |

- [ ] 所有列表有 `page=1`、`limit=20`，limit 上限 100；目录按 name/id 升序，业务记录按 created_at/id 倒序。响应 `api_version='1'`，`data` 含 `items/page/has_more/filters/snapshot_at`；filters 说明实际查询条件，不另建授权对象集合或重复的 scope 配置。
- [ ] 目录以 `q` 检索名称；账户另支持 kind/member_id/tag/active，SKU 支持 active。账户候选含 `id/name/kind/member_id/member_name/active`，SKU 含 `specification/unit/active`，帮助区分同名。列表简洁，详情返回办理业务所需说明、往来方、依据及关联记录；不返回认证资料或用户权限配置。
- [ ] 转移过滤使用 `status/tag/source_account_id/destination_account_id`，货物加 `sku_id`；`effective_date_from/to` 是含首尾的业务日期，`created_at_from/to` 是带时区 ISO 录入时间，采用 `[from,to)`。未给的端点不限制。
- [ ] 增加 `submitted_by_current_connection: bool=False`；true 时服务端用当前凭据 ID 过滤后分页。资金匹配主单来源；货物匹配主单来源，或以 EXISTS 匹配本连接提出的完成申请，父单去重。不能用 owner ID 替代连接 ID，也不开放任意凭据 ID 输入；完成申请仍从父单 confirmations 按 ID 回查。
- [ ] `minor_to_yuan(value: int) -> str` 以符号、绝对值和 `divmod(...,100)` 形成两位小数，禁止 float。金额结果配对 `amount_minor/amount`、`balance_minor/balance`，结算金额沿用同名去掉 `_minor` 的元字符串；保留 CNY 和数量字符串。
- [ ] 输出 Schema 为固定业务结构，列表和详情共用必要行类型；不以 `dict[str, Any]` 冒充完整 outputSchema。列表不夹带完整审计快照；库存分清实际账面数量、在途计划量与未估值。

**可观察验收：** `test_queries_support_disambiguation_and_submission_lookup` 使用真实数据覆盖同名候选、两种日期端点、当前连接过滤、两页结果以及两档同一读取结果；本连接对他人父单提交完成申请后仍能找到该父单且不重复。在同一用例断言 `-1` 分输出 `'-0.01'`、`12050` 分输出 `'120.50'`。不新增 ACL 相关测试。

### 任务 5：提议与高权限业务操作编排

**文件：** 新建 `backend/application/agent_operations.py`；扩展 `backend/entrypoints/agent_schemas.py`。依赖任务 3 的已完成业务接口，不另行改账本。

**接口：** 创建操作 `(db, access: AgentAccess, data: dict) -> dict`，针对记录的操作 `(db, access, identifier: str, data: dict) -> dict`；函数名为下表工具名去掉 `fgas_`。命名操作各自检查权限，不接受万能 action、角色、状态或自动审批开关。

| 工具名 | 既有输入与调用 |
| --- | --- |
| `fgas_propose_fund_transfer`、`fgas_propose_stock_transfer`、`fgas_propose_stock_completion` | `Submit/StockTransferInput/CompletionInput`；任务 3 提议模式 |
| `fgas_create_fund_transfer`、`fgas_create_stock_transfer`、`fgas_complete_stock_transfer` | 同上；high 直接模式 |
| `fgas_create_fund_account`、`fgas_update_fund_account`、`fgas_create_stock_account`、`fgas_update_stock_account` | `AccountCreate/AccountPatch`；`catalogs` |
| `fgas_create_sku`、`fgas_update_sku`、`fgas_create_member`、`fgas_update_member`、`fgas_set_stock_custody` | 既有 SKU、Member、Custody Schema；对应目录服务 |
| `fgas_approve_fund_transfer`、`fgas_reject_fund_transfer`、`fgas_reverse_fund_transfer` | `Approval/Rejection/Reversal`；`funds.decide/reverse`，保留 expected_version |
| `fgas_approve_stock_transfer`、`fgas_reject_stock_transfer`、`fgas_cancel_stock_transfer` | `StockApproval/StockRejection`；`warehouse` 对应服务 |
| `fgas_approve_stock_completion`、`fgas_reject_stock_completion` | 完成申请 ID；`warehouse.decide_completion` |
| `fgas_create_settlement`、`fgas_add_settlement_matches` | `SettlementCreate/SettlementMatches`；`settlements` |
| `fgas_create_stock_operation`、`fgas_add_stock_fund_reference` | `StockOperationInput/StockFundReferenceInput`；既有联建/引用服务 |
| `fgas_create_fund_stocktake`、`fgas_update_fund_stocktake`、`fgas_end_fund_stocktake`；对应 `stock_stocktake` 三工具 | `StocktakeCreate/StocktakePatch`；`stocktakes`，固定 kind |

- [ ] 仅前三个 propose 操作允许 low；其他写操作先 `require_high(access)` 再调用服务，不能只在工具发现时隐藏。高权限新建目录后立即可查询并引用，不需要追加范围配置。
- [ ] 输入复用现有 Schema；Patch 使用 `model_dump(exclude_unset=True)`，省略字段不改。账户的 member_id/avatar_url、SKU 的 avatar_url 可显式 null 清空；保管的 member_id=null 表示结束保管。名称、kind、unit、active 等非空字段在 MCP 适配校验时拒绝显式 null，文本清空沿用空字符串，不把 Pydantic 的默认 None 当成可清空授权。不要用 `exclude_none=True` 吞掉清空意图，也不添加独立 clear_* 开关。
- [ ] 写结果以 `api_version/data` 包装，明确 resource_type、各业务 ID、status、`ledger_effect_applied`、`approval_required`。完成操作同时给 confirmation_id、stock_transfer_id 及父单状态；目录成功和匹配成功不伪装为正式账本变化。
- [ ] 对余额/库存影响沿用现有规则：结算只追加匹配不再记账；保管不转移库存；盘点创建/结束不自动调整；冲销不退货、取消不退款。输入用户未表达的业务动作不在编排层补做。

**可观察验收：** `test_proposals_always_require_approval` 使用管理员签发的 low/high 参数化验证三种提议均 pending 且无账本变化。`test_high_direct_business_and_source` 通过 Agent 应用接口走一条资金/货物链：high 新建对象可查询/使用，资金直接过账、货物在途后另行完成；完成 ID 可回查；low 直接调用 high 函数被拒。代表性 AccountPatch 验证遗漏不改、null 清空；来源断言覆盖一次冲销及既有结算/联建服务的透传，不在协议层再重复业务断言。

### 任务 6：MCP 适配、认证与上下文

**文件：** 新建 `backend/entrypoints/mcp.py`；修改 `backend/entrypoints/http.py`、`backend/requirements.txt`；扩展 `backend/entrypoints/agent_schemas.py`；读取 `docs/ai/guide.md`。

**接口：** `create_mcp_app()` 构建 SDK ASGI 应用及其生命周期；固定工具声明映射任务 4、5 的函数和 Schema。`get_context(access: AgentAccess) -> dict` 返回 `api_version/guide_version/guide/level/available_tools` 及固定业务语义，不返回 secret、hash 或多档能力配置。

- [ ] 确认后添加锁定依赖 `mcp==2.3.0`；采用官方 Streamable HTTP，由宿主 FastAPI lifespan 启停 `session_manager`，核对挂载结果确为 `/mcp`，不手写协议兼容栈。
- [ ] MCP ASGI 认证覆盖初始化、工具发现和调用，验证 Bearer 后绑定仅本请求可见的身份；不保存全局当前用户，不把人工 cookie 当替代凭据。每次新调用重新确认 token 与 owner，SDK 协议会话不固化业务权限。
- [ ] 在每个工具调用的同一数据库事务内解析凭据、取得 User 并构造 `AgentAccess`，传给应用函数；不把认证中间件已结束 Session 的 ORM User 传进另一事务，以免破坏现有 `store.refresh`。参数先由现有输入/新增查询 Schema 校验，拒绝多余身份字段。复用现有事务提交/回滚，不让 SDK 自动重试写业务。
- [ ] 注册上表所有明确工具及 `fgas_get_context`；两档可发现相同读取和 propose 工具，high 另外发现直接业务工具。每个操作本身仍校验权限；没有 SQL、任意 URL 或万能 action 工具。
- [ ] 工具提供 inputSchema、具体 outputSchema 和 structuredContent，兼容文本内容序列化同一结果；读工具标 readonly，propose 也标会写记录。`pending` 是普通成功，不挂起等待人工。
- [ ] 认证失败在认证层拒绝；将 Pydantic/DomainError 转为稳定业务 code 与 message（validation_error、permission_denied、not_found、state_conflict），按 SDK 规则映射工具错误；不泄漏堆栈、凭据或数据库连接信息。
- [ ] context 说明 low/high、提议固定待审、货物在途与正式库存区别、金额/日期/分页、Patch、人工管理限制和失败后回查；业务说明来自指南。说明文本不替代服务器授权。

**可观察验收：** `test_mcp_auth_discovery_and_structured_results` 使用官方 SDK 客户端/测试传输接真实 ASGI 与同一 PostgreSQL 夹具，覆盖无效 Bearer、cookie 不能代替 token、工具列表及一次只读/提议调用的结构化结果。直接猜 high 工具必须被拒；不在协议层重复任务 5 全部账本断言。

### 任务 7：人工连接页面与记录来源显示

**文件：** 新建 `frontend/src/api/agentConnections.ts`、`frontend/src/views/AgentConnectionsView.vue`；修改 `frontend/src/App.vue`、`frontend/src/api/funds.ts`、`frontend/src/api/warehouse.ts`、`frontend/src/views/TransfersView.vue`、`frontend/src/views/StockTransfersView.vue`。

**接口：** `agentConnections.list/create/update` 使用现有 `request` cookie 客户端和任务 2 响应；页面接收当前 `User`。来源类型对应任务 1、3 字段，不从用户名称猜测 Agent 来源。

- [ ] 仅 trusted/admin 显示“Agent 连接”导航；列表显示名称、归属、等级、启用和到期时间。trusted 仅 low，admin 新建默认 low；选择 high 时明确说明可直接办理业务和创建对象。
- [ ] 创建成功显示一次性 secret 和配置用 `/mcp` 地址，提供复制；关闭显示或切换用户清除页面内 secret，不保存 localStorage。丢失后提示新建连接，不提供找回明文。
- [ ] 允许按任务 2 权限改名、等级、到期时间和启停；管理员对他人连接仅显示停用。使用现有页面错误提示与人工重试，不新增请求队列或恢复状态机。
- [ ] 资金/货物详情及完成申请显示“由连接名称提交”并保留所属用户；审批显示 Agent 直接执行/Agent 批准与人工来源。旧记录来源空时继续按人工既有信息显示。

**可观察验收：** 任务 8 的前端类型检查与构建通过，必要时最多截图查看连接页面和记录详情。不新增样式测试，不启动浏览器自动交互测试。

### 任务 8：集中验证、接入说明与交接

**文件：** 新建/完成 `backend/tests/test_agent_access.py`；修改 `tools/run_tests.sh`、`README.md`、`architecture.md`、`docs/ai/guide.md`、`docs/prototype-status.md`。

- [ ] 把前述核心用例加入单个测试文件，复用 `backend/tests/conftest.py`、TestClient、真实应用服务及 PostgreSQL；仅增加必要短辅助函数。`tools/run_tests.sh` 在已有三个文件之后加该文件，保留专用库名称校验。
- [ ] 在完整实现后确认 `DATABASE_URL` 指向专用 `fgas_test`，执行一次 `./tools/run_tests.sh`；该 runner 会清理专用测试库，必须打印 `Test database: fgas_test` 且测试全通过。不能让测试指向日常开发库。
- [ ] 执行 `npm run build`，要求 vue-tsc 与 Vite 均成功；只有新修改、实际失败或具体未决风险才补跑受影响检查。记录实际命令和结果，不用收集成功代替测试通过。
- [ ] 在确认的开发/测试数据上选一个实际客户端验证标准发现、读取和待审/直接业务链；另一已明确客户端只做必要发现/读取核对。使用客户端协议调用而非浏览器自动点击，不建全客户端矩阵，不创建日常真实账目；无可用客户端则明确记录未联调。
- [ ] README 写 DeepSeek Harness 与 OpenCode 的标准 URL/Bearer 配置示例，引用运行时变量，不写真实 token；明确开发机回环地址的访问边界，HTTP/OAuth/部署留后续。旧 reset 升级段落改为说明历史更新，Agent 增量只引用显式非破坏性 SQL。
- [ ] 同步 architecture 与 AI 指南为实际实现的工具、字段、状态和限制；只有实际发布时才去掉 draft 标记。状态文档记录 SDK/客户端版本、实际检查、截图/联调未做项与残留限制，不复制历史讨论。

**完成证据：** 文档中列出真实运行命令、退出结果、相关业务状态与记录来源；没有实施、数据库升级或客户端联调的部分保持“未执行”。本计划编写阶段仅检查文档一致性，不运行本节产品命令。
