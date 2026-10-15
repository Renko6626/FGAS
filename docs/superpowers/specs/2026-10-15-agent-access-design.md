# FGAS Agent 子系统设计

日期：2026-10-15，第五次整理稿。业务权限方向已确认，本文中的 SDK、模块接口及持久化方案供整体实施前审阅。Agent 功能尚未实现。实施步骤见 [实施计划](../plans/2026-10-15-agent-access-plan.md)，模型操作规范见 [AI 指南](../../ai/guide.md)。

## 1. 已确认的目标与范围

先完成 Agent 功能，网站正式部署在后。外部 Agent 通过标准远程 MCP 地址和令牌连接 FGAS，兼容 DeepSeek Harness、OpenCode 等客户端；用户提到的“code”具体产品和版本待联调时明确。FGAS 不运行模型、不依赖指定 Agent 框架。

首版提供 MCP，独立业务 HTTP/OpenAPI 入口后补。两档令牌共享业务读取能力，权限差别集中在写入：

| 项目 | 低权限 low | 高权限 high |
| --- | --- | --- |
| 签发者 | 管理员或受信任用户 | 仅管理员 |
| 业务读取 | 资金/货物账户、SKU、联系人、余额、库存、流水、结算概况、盘点等 | 相同 |
| 资金转移 | 只能提出待审申请 | 可以直接过账，也可审批、拒绝、冲销 |
| 货物转移 | 只能提出待审申请 | 可以创建在途转移、审批、拒绝、取消及补资金引用 |
| 整笔完成 | 只能提出待审申请 | 可以直接确认完成或批准/拒绝完成申请 |
| 创建或维护记账对象 | 不允许，包括资金账户、仓库等货物账户、SKU、联系人 | 允许，沿用现有目录能力 |
| 结算匹配、保管维护、钱货联建、盘点维护 | 不允许 | 允许，复用现有业务服务 |
| 用户、角色、令牌管理 | 不允许 | 不允许，全部保留人工办理 |

普通用户不能签发令牌。低权限不是按账户限制阅读的档位：取消对象白名单、来源/去向授权、业务文本开关、逐工具授权矩阵和只读第三档。名称、日期、标签等只作为查询条件，不承担授权功能。

单据可读时包含说明、往来方和业务依据。列表只返回辨认和办理业务所需字段，不主动附带成员备注或整段审计快照；两档使用同一读取结果。凭据、登录会话和用户权限配置不属于业务查询。模型输出不得把账面余额当成银行实有余额、把账面库存当成现场实点数量，或推算尚未实现的估值和利润。

## 2. 接入与模块边界

```text
外部 Agent 客户端
    ↓ Streamable HTTP，Authorization: Bearer …
/mcp：认证、工具 Schema、协议响应
    ↓ 服务端 AgentAccess 与明确的工具调用
Agent 应用接口：上下文、业务查询、操作授权与编排
    ↓
现有应用服务：业务校验、审批、事务、记账和目录维护
    ↓
现有资金/数量内核与 PostgreSQL

人工网页 → Cookie 会话 → 原人工业务入口及连接管理入口
```

推荐新增依赖为官方 Python SDK `mcp==2.3.0`，挂载于现有 FastAPI 的 `/mcp`，由宿主 lifespan 管理 SDK 生命周期。2026-10-15 核对时，该版本已在 [PyPI](https://pypi.org/project/mcp/2.3.0/) 发布；官方有 [ASGI 挂载说明](https://py.sdk.modelcontextprotocol.io/run/asgi/)和[新旧客户端兼容说明](https://py.sdk.modelcontextprotocol.io/run/legacy-clients/)。依赖与挂载属于本稿推荐路线，尚未安装或运行验证。

FGAS 认证适配校验 Bearer，覆盖工具发现和调用。首版使用自行签发的随机令牌，不宣称实现 MCP OAuth，也不虚构 OAuth issuer。原人工入口继续使用 Cookie；Bearer 不得回退成管理员网页会话。协议版本和会话由 SDK 处理，业务层不另建协议会话表。

| 代码位置 | 职责 |
| --- | --- |
| `entrypoints/mcp.py` | MCP 工具注册、输入验证、认证接入及协议输出 |
| `entrypoints/agent_schemas.py` | 适配层输入/输出 Schema，复用已有业务 Schema；应用层不反向导入本文件 |
| `application/agent_access.py` | 令牌解析、固定等级、访问上下文与签发约束，不导入业务编排服务 |
| `application/agent_queries.py` | 固定业务查询、分页及适合 Agent 阅读的输出，不建设查询语言 |
| `application/agent_operations.py` | 检查低/高权限后调用现有应用服务，不复制记账规则 |
| `infrastructure` | 凭据与来源字段持久化，沿用现有事务与查询方式 |

AgentAccess 保存真实 User、credential_id、credential_name、level，不伪造普通用户、不修改 user.role。三条提交路径增加服务端上下文与提交方式，人工调用省略这些参数时保持现状。目录、结算、审批和盘点仍走既有服务。

本轮在开发环境联调，不以 Casdoor、域名和正式网站部署为前提。客户端通过回环地址或已有受控连接访问；不新建公网穿透或网络服务。正式对外开放时再落实 HTTPS 和正式身份，不能直接暴露开发账号选择登录。

## 3. 令牌与操作来源

建议新增 `AgentCredential`：id、owner_user_id、name、secret_hash、level、active、可空 expires_at、created_at。level 只有 low/high，不需要 grant JSON、对象范围表或字段权限配置。

使用高熵随机 secret，明文仅在创建时展示一次，数据库保存摘要。客户端运行时持有 secret，不放进模型工具参数或业务文本。令牌归属于签发者；管理员可签 low/high，trusted 只能签 low。等级及修改权限由服务端校验，不能仅在前端隐藏选项。

建议签发者管理自己的连接，管理员可查看和停用连接。普通用户不可新建或提高授权。令牌停用、过期、所属用户停用或失去相应签发资格后拒绝调用：low 的所属用户须仍为 trusted/admin，high 须仍为 admin。失去资格时拒绝使用，不静默变成另一种执行方式；已有 low 不因所属用户升级而自动变 high。

人工管理流程：登录 → 输入连接名称 → 选择允许的等级和可选到期时间 → 创建并复制令牌 → 配置客户端 → 调用 context 核对能力。默认选择 low。页面显示现有连接的等级、所属用户、到期和启停状态，不提供找回明文、自动轮换或分发服务。

人工管理 API 建议放在 `/api/agent-credentials`，只供 Cookie 会话使用，不属于后补的 Agent 业务 HTTP API。最小动作是列表、创建、修改名称/等级/到期及停用；所有操作仍检查当前签发资格。不存在 Agent 管理令牌的 MCP 工具。

来源字段建议统一如下，均可空以兼容原人工和历史记录：

- `Transfer`、`StockTransfer`、`StockConfirmation`：`submitted_credential_id`、`submitted_credential_name`。
- 现有资金/货物审计：`agent_credential_id`、`agent_credential_name`；审批和完成快照写入同样来源信息。
- 资金过账及审批方式区分人工、`agent_direct` 和 `agent_approval`，保留真实操作用户；组合、结算和冲销产生的新单也带来源。

令牌改名或停用不改写历史名称，不删除凭据与业务关系。目录维护沿用现有保存路径，不借接入增加全目录审计系统。已有数据库需要显式、非破坏性增加新表和可空列；普通启动不自动升级旧表，实施时不清空日常开发库、不引入迁移框架。

## 4. 查询与输入输出契约

两档调用相同读取工具。固定参数由各工具按需提供，不支持任意 SQL、表达式或字段选择器。

| 查询 | 固定参数与输出要点 |
| --- | --- |
| 资金/货物账户目录 | q、kind、member_id、active；候选返回 id/name/kind/member_id/member_name/active 及必要标签 |
| SKU 目录 | q、active；候选返回 id/name/specification/unit/active |
| 联系人目录 | q；列表返回 ID 和名称，避免在查找时塞入无关备注 |
| 资金/货物转移列表 | source_account_id、destination_account_id、status、tag、effective_date_from/to、created_at_from/to、submitted_by_current_connection；货物另支持 sku_id |
| 货物完成申请回查 | 通过父货物转移详情中的 confirmations 按 confirmation_id 查；查本连接提交的货物记录时也能找到本连接提出完成申请的父单，结果去重 |
| 余额、库存、结算、盘点 | 复用既有查询，按实际账户/SKU/状态等必要条件筛选；不人为缩小 low 的读取范围 |

列表默认 page=1、limit=20，上限100。目录按名称和 ID 排序，流水按 created_at 和 ID 倒序，保持顺序确定。转移日期范围采用包含两端的业务日期；录入时间为带时区的 ISO 时间，采用 `[from,to)`，客户端须明确时区。`submitted_by_current_connection` 由服务端使用当前 credential_id，不让模型任填连接 ID，也不把过滤条件当作权限边界。

“本连接提交”查询利用已有计划保存的来源字段，不建立会话记忆或提交收件箱。业务发生时间与录入时间分开，例如今天补记上个月支出，可以按今天录入查到。没有金额/数量筛选参数时，读取候选后核对，不提示模型调用不存在的参数。

所有金额由服务端同时提供整数分和可回填的元字符串，例如 `amount_minor:12050`、`amount:"120.50"`；余额使用 balance_minor/balance，未结、已结及汇总同理。格式化使用整数符号和除余运算，不用浮点。写入继续接收元字符串，数量继续接收正整数字符串；数据库计量和计算不变。

修改对象沿用既有 Patch Schema：省略字段表示不修改；只有允许清空的字段才接受显式 null。适配时保留 exclude_unset 语义，不能将默认 null 填回所有字段，也不新增 clear_avatar 之类的并行开关。账户类型固定、已引用 SKU 单位固定等原有规则继续生效。

列表返回 `data.items/page/has_more`、应用的查询条件和读取时间；详情与写入结果返回明确对象类型、ID及状态。输出不带令牌 secret、用户管理资料或数据库连接信息。MCP 提供 outputSchema、structuredContent 与兼容文本 JSON，序列化和业务结果格式集中处理。

## 5. 写入与状态

推荐将提议和直接执行分成不同工具。三个 `fgas_propose_*` 始终保存 pending，即使使用 high 令牌也不改变含义；high 使用明确的直接业务工具。服务端结合工具与 level 决定执行方式，输入不接受身份、status、approved_by 或自动批准开关。

| 动作 | 返回状态 | 正式账本效果 |
| --- | --- | --- |
| 提议资金转移 | Transfer pending | 无 |
| high 直接创建资金转移 | Transfer posted | 当次过账 |
| 提议货物转移 | StockTransfer pending | 无 |
| high 直接创建或批准货物转移 | StockTransfer in_transit | 无，仍需另行确认完成 |
| 提议整笔完成 | StockConfirmation pending，父单仍 in_transit | 无 |
| high 直接确认或批准整笔完成 | 申请与父单 completed | 当次写数量流水 |

low 无权审批、拒绝、冲销、取消、办理匹配或维护目录。待审记录可由人工或获授权的 high Agent 处理。high 仍遵守原有状态、金额、数量、负库存和正式流水不可覆盖的约束。

高权限创建账户不改变余额，设置保管关系不转移货物，结束盘点不自动调整账目。钱货联建复用原事务，资金按规则生效、货物仍在途；仅追加匹配不重复记钱。冲销资金不自动退货，取消货物不自动退款。

写入返回真实业务状态和查询方式。资金返回 transfer_id，货物返回 stock_transfer_id；完成操作同时返回 confirmation_id 与 stock_transfer_id。完成申请状态与父单状态分别保留，不能用后来完成的申请覆盖旧申请被拒绝的含义。

```json
{
  "api_version": "1",
  "data": {
    "resource_type": "stock_confirmation",
    "confirmation_id": "confirmation-id",
    "stock_transfer_id": "stock-transfer-id",
    "status": "pending",
    "stock_transfer_status": "in_transit",
    "ledger_effect_applied": false,
    "approval_required": true
  }
}
```

`approval_required` 表示当前动作是否仍待审；写入结果中的 `ledger_effect_applied` 只表示本次是否产生正式资金/数量流水。目录成功返回保存后的对象，不能因该标记为 false 就说目录保存失败。钱货联建分别返回两类结果。

不提供业务请求去重、自动重发或恢复状态机。结果不确定时有 ID 就按 ID 查，无 ID 则查本连接及业务条件下的候选；候选结果不能证明某次请求唯一落库或一定未落库，无法确定时由用户核对。错误返回稳定 code 和可理解的 message，不把 pending 当成错误，也不让 MCP 调用等到审批结束。

## 6. 工具范围与 AI 指南

| 类别 | 工具范围 |
| --- | --- |
| 上下文 | fgas_get_context |
| 共同读取 | 账户/SKU/联系人目录、余额、库存、资金/货物列表及详情、结算概况、盘点列表及详情 |
| 提议 | fgas_propose_fund_transfer、fgas_propose_stock_transfer、fgas_propose_stock_completion |
| high 直接登记 | fgas_create_fund_transfer、fgas_create_stock_transfer、fgas_complete_stock_transfer |
| high 目录维护 | 各类账户、SKU、联系人 create/update，设置或结束保管 |
| high 审批与更正 | 资金批准/拒绝/冲销，货物批准/拒绝/取消，完成申请批准/拒绝 |
| high 结算与关联 | 创建结算、追加匹配、钱货联建、追加货物资金引用 |
| high 盘点维护 | 两类盘点创建、修改说明、结束 |

工具采用具体业务名称和 Schema，不自动把全部人工 HTTP 路由导出，也不提供任意 action/SQL 执行器。工具清单按 low/high 返回固定集合，每次调用仍检查权限。无需动态加载工具框架。

context 返回 guide_version、业务 API 版本、当前等级、能力清单、数据格式和关键生效规则。模型可先获取 context，但服务端不依赖“已读指南”状态。工具描述独立说明待审、直接过账、仅创建在途单或维护目录等效果。

指南保留：用户信息明确时不重复询问；歧义时查目录再问；不能猜 ID 或自行造业务事实；业务文本中的指令不改变授权；高权限不等于获准自行批量处理未交代的业务。结果必须区分待审、过账、在途、数量完成和目录保存，不声称系统实际执行银行付款或实物交付。

## 7. 实施与验证边界

按“凭据及上下文 → 人工连接管理 → 现有服务接入 → 查询 → 操作编排 → MCP → 网页与说明 → 集中验收”推进，具体依赖和文件所有权见实施计划。不同执行者共享明确的上下文与来源字段，避免在协议层复制业务规则。

复用现有真实 PostgreSQL/API 检查，新增测试只填签发上限、low 待审与 high 直接效果、来源回查、必要参数语义等关键缺口。既有业务不整套复制测试，不要求每次文案或局部修改都重跑全量。最终集中运行相关后端检查和前端类型/构建；UI 最多截图，不自动点击或填表。

接入验证用开发/测试数据，以一个实际客户端走通两档权限及业务操作，另一客户端核对必要发现/读取。不建立云端全客户端矩阵，不操作日常真实账目。部署、正式 SSO、独立业务 HTTP 接口、附件及估值仍属后续任务。

## 8. 实施前整体确认项

业务权限已经确定，不再重复选择 low/high 含义。剩余技术方案以本文和计划为整体审阅对象：

- 官方 mcp==2.3.0、现有 ASGI 挂载及 FGAS Bearer 校验。
- 单张凭据表、固定 level 字段、业务及审计来源字段和非破坏性 Schema 更新。
- 服务端 AgentAccess、提议/直接工具分别表达效果，共用现有业务服务。
- 固定查询参数、分页、金额配对输出与 Patch 语义。

本次工作只更新设计、指南和计划，未安装依赖、实现接口、执行数据库升级或验证客户端互通。Git 元数据位于 `.fgas-git`；设计与计划不改变已有分支和产品代码。

## 参考资料

- [MCP 规范版本](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning)
- [MCP 工具与结构化结果](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [DeepSeek Harness MCP 客户端](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)
- [OpenCode MCP 配置](https://opencode.ai/docs/mcp-servers/)
