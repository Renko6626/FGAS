# Agent 待审批查询与逐笔预览 Implementation Plan

> **已取消，不执行。** 用户决定沿用现有查询，由模型完成简单加减，不新增待审聚合或预览能力。以下任务仅为历史方案；不得依据其中的复选框开始实施或委派。已完成的权限和接入文档澄清保留。

**Goal:** low/high 均可查全当前待审事项，并只预览单个事项获批时受影响端点的即时账面变化。

**Architecture:** 保留现有 MCP 四工具，在 fgas_query 增加 pending_approvals、approval_preview。应用层负责业务解释，基础设施负责当前 pending 记录的统一分页；复用只读快照、账面查询及资金/货物的实际方案，不新增持久化机制。

**Tech Stack:** Python 3.13、FastAPI、SQLAlchemy、PostgreSQL、官方 MCP SDK；无新增依赖。

**Spec:** `docs/superpowers/specs/2026-10-27-agent-approval-preview-design.md`（具体字段和口径待用户审阅）。

## Global Constraints

- 只在 fgas_test 运行数据库测试，不修改日常数据库；本计划阶段不执行测试、不清库。
- 保留工作区已有 MCP 指南、公开接入文档和版本更新，不改用户的 `.qoder/`。
- 默认使用 low；low/high 可读范围一致，预览不取得或绕过审批权。
- 只列受影响端点；货物外部端点无库存数字，资金外部端点返回的是账本余额。
- 只算当前事项获批的即时变化；货物主单批准仅在途，完成批准才写库存；关联付款不重复记账。
- 不新增数据库表、字段、迁移、角色、顶层工具、人工 HTTP 路由、依赖、请求恢复或自动重试。
- 复用已有业务校验，不通过先写后回滚实现预览，不加入未经批准的可靠性机制。
- 不新增页面或浏览器自动交互，不提交密钥、个人配置或数据库连接信息。

## Review Focus

- 超过30天的 pending 仍能列出；完成申请使用自己的 ID、申请人、业务日期和连接来源（Task 1）。
- 清单跨三类统一分页；本连接过滤按所选事项本身，不误用父单来源（Task 1）。
- 预览只包含相关账户、组织端点及 SKU；库存方向和两端在途口径与实际服务一致（Task 2）。
- 当前来源库存不足会阻塞完成；主单批准不提前扣库存；旧单停用规则及资金负余额沿用原业务（Task 2）。
- low 实际 MCP 能查询，预览不产生分录、数量流水、申请、审计或状态修改（Task 3）。

## 文件职责

| 文件 | 本次责任 |
| --- | --- |
| 新建 backend/application/approval_queries.py | 组织清单和逐笔影响，执行只读业务校验，返回领域字段；不依赖入口 Schema |
| 新建 backend/infrastructure/approval_queries.py | 三种 pending 的统一选择、来源筛选、排序与数据库分页；不解释金额和审批效果 |
| backend/application/warehouse.py | 小范围收敛已有完成前读取校验和 move 计划，实际完成与预览共用 |
| backend/application/agent_queries.py | 新增两个具名查询适配，使用现有金额格式和 api_version 包装 |
| backend/entrypoints/agent_schemas.py | 两个输入契约、清单/预览输出及 INPUT/OUTPUT 映射 |
| backend/entrypoints/agent_catalog.py | 注册两个 query resource、短说明和示例，保持工具数不变 |
| backend/tests/test_agent_access.py | 复用 issue/fund_data/stock_data/client 和既有 MCP 生命周期，补业务及协议覆盖 |
| docs/ai/overview.md、docs/ai/guide.md、backend/entrypoints/mcp.py | 指南、权限/阶段说明、指南版本一致 |
| README.md、architecture.md、docs/prototype-status.md | 记录最终能力、职责、实际验证和未验收项 |

不改 HTTP 路由、模型、迁移、前端组件或测试启动脚本。已有 `money()` 递归转换资金的 *_minor 字段；库存格式继续使用 quantity_string。

## 验证命令

执行时先在进程环境准备 `FGAS_TEST_DATABASE_URL`，其值必须指向 fgas_test，不回显或写入仓库。以下命令的变量缺失保护会在未设置时停止；现有测试设施仍会核对真实库名。

```bash
# Task 1：预期先因新查询缺失而失败，完成后通过。
DATABASE_URL="${FGAS_TEST_DATABASE_URL:?set the dedicated fgas_test URL}" FGAS_TEST_DATABASE=1 AUTH_MODE=development .venv/bin/python -m pytest backend/tests/test_agent_access.py -k pending_approvals -q

# Task 2：目标预览行为通过，既有货物完成行为继续通过。
DATABASE_URL="${FGAS_TEST_DATABASE_URL:?set the dedicated fgas_test URL}" FGAS_TEST_DATABASE=1 AUTH_MODE=development .venv/bin/python -m pytest backend/tests/test_agent_access.py -k 'approval_preview or internal_stock_preview' -q
DATABASE_URL="${FGAS_TEST_DATABASE_URL:?set the dedicated fgas_test URL}" FGAS_TEST_DATABASE=1 AUTH_MODE=development .venv/bin/python -m pytest backend/tests/test_stock_transfers.py -q

# Task 3：集中回归，脚本仅允许 fgas_test；预期退出0且无失败。
DATABASE_URL="${FGAS_TEST_DATABASE_URL:?set the dedicated fgas_test URL}" ./tools/run_tests.sh
git diff --check
```

### Task 1: 完整待审清单

**Interfaces**

- `infrastructure.approval_queries.pending_page(db, *, kind=None, credential_id=None, page=1, limit=20) -> list[dict]`：返回最多 limit+1 个标识行（kind、id、parent_transfer_id、created_at），三类 UNION ALL 后分页。credential_id=None 表示不限定连接；否则限定事项本身的 submitted_credential_id。
- `application.approval_queries.list_pending(db, access, filters: dict) -> dict`：返回未加 api_version 包装的分页数据，使用一个 read_snapshot 选行并补齐设计中的清单字段。
- `application.agent_queries.list_pending_approvals(db, access, filters: dict) -> dict`：现有 MCP 查询适配，调用前者后通过 _result 包装。
- 新输入 `PendingApprovalFilters(PageFilters)`：kind 可空，submitted_by_current_connection 默认 false。输出沿用 PageData，清单行字段以设计文档为准。

- [ ] 在现有测试文件补 `test_pending_approvals_include_old_records_and_completion_identity`：用真实 HTTP/服务准备资金 pending、货物 pending、在途父单的 pending 完成申请及已处理记录；将一笔 pending 的 created_at 设为45天前；断言三类准确出现，处理过的排除，完成申请不拿父单 ID/申请人替代，原事件列表的30天行为保持原样。
- [ ] 补 `test_pending_approvals_pagination_and_connection_filter`：人工/两个连接准备有区分的事项，含父单和完成申请来源不同；limit=2 翻全三类，断言顺序、has_more、无重复；限定 kind 和本连接后只出现预期事项。预期 ID 从真实建单响应取得。
- [ ] 使用显式 fgas_test 环境运行上述目标用例确认缺失能力导致失败；不在日常库运行。
- [ ] 实现基础设施统一分页和应用层补齐身份/端点/明细；不加载所有历史再 Python 分页，不为每行计算余额、库存或预览。
- [ ] 在 agent_queries、schemas、catalog 注册 `pending_approvals`；不经过 _event_filters、不套30天窗口、不改变旧列表默认行为。
- [ ] 重跑这两个目标用例；结果正确后进入下一任务。

### Task 2: 受影响端点的逐笔预览

**Interfaces**

- `application.approval_queries.preview_approval(db, access, *, kind: str, identifier: str) -> dict`：返回设计规定的预览数据，不包装 api_version。记录、账面和计划在一个现有 read_snapshot 中读取。
- `application.agent_queries.get_approval_preview(db, access, filters: dict) -> dict`：从 filters.kind/id 取值调用预览，再 _result 包装。
- 输入 `ApprovalPreviewFilters(Input)`：kind 为三类枚举，id 为非空字符串。不命名为 identifier，避免触发当前 MCP 适配层按详情签名分派；不修改原有分派行为。
- `warehouse.plan_completion(db, item) -> list[dict]`：收敛现有 validate(existing=True)、组织来源库存检查和 build_moves；无写入、无授权策略、无状态修改。`post_completion` 仍首先执行原有身份和状态检查，再调用该函数并写正式流水；预览在自己的身份/状态范围内调用同一只读计划。

- [ ] 补 `test_fund_approval_preview_matches_posting_and_is_read_only`：公账1000元、支出端点0元，待审付款120元；只返回两端1000/-120/880和0/+120/120，不返回第三账户。预览前后无正式分录或状态变化；通过真实审批后实际值等于独立期望；再次预览已处理 ID 返回 state_conflict。负余额不额外构成 blocker。
- [ ] 补 `test_stock_approval_preview_distinguishes_plan_and_completion`：对外部→组织的多 SKU 单据，逐阶段核对主单批准的 on_hand delta=0、planned delta=+2/+3，完成批准的 on_hand delta=+2/+3、planned delta=-2/-3；外部库存行和无关 SKU 不出现。通过实际批准/完成后的库存查询核对独立期望。
- [ ] 补 `test_internal_stock_preview_and_insufficient_source`：组织调拨2件，来源3→1、去向1→3，两端各减少2件在途计划；库存不足时预览带现有阻塞原因、实际完成被拒绝且库存不变。将已建单涉及的账户或 SKU 停用，仍遵守现有旧单可处理规则，不自行加阻止条件。
- [ ] 在三个测试中仅断言本任务核心的只读效果与独立数值，复用现有准备工具，不复制生产计算算法、不穷举账户组合。
- [ ] 运行目标用例确认缺失行为失败，再实现只读预览和小范围计划复用。资金使用原 balanced_transfer 方案与当前分录余额，pending 冲销沿用原单必须仍 posted 的校验。
- [ ] 注册 `approval_preview` 输入/输出和 help 示例，响应字段严格按设计文档；使用金额整数分及 quantity_string，不以 float 运算。
- [ ] 重跑受影响用例和既有货物完成测试，确认实际写路径未改变；不过早扩大为全量回归。

### Task 3: 原生 MCP 集成、文档与集中验证

**Interfaces**

- query 新 resource 为 pending_approvals、approval_preview；low 仍只有 help/query/propose，high 额外 execute。
- 两个 resource 均复用查询的 structured_content、同内容文本、按需输入/输出 Schema、现有错误编码和 Bearer 校验。

- [ ] 在现有 `test_mcp_auth_discovery_and_structured_results` 中用已创建的 low 连接、待审资金单增加两次真实原生 MCP 查询：清单含该项、预览给出预期两端；include_output_schema=true 返回的输出契约可校验两种实际结果。继续保留原测试的 low 执行拒绝和凭据停用断言。
- [ ] 在上述协议检查前后核对 JournalLine、StockMove、完成申请、审计数量和被预览事项状态未变化；资金/货物实际数值在 Task 2 已覆盖，不机械复制。
- [ ] 更新 overview/guide：默认 low 下“查询待审→按需逐笔预览→向用户解释→等待人工审批”；明确快照、无合计、两类货物阶段、外部货物无库存数字、本连接筛选及预览不执行。替换上一轮指南中“没有统一待审清单/预览”的现状说明，保持指南版本同步。
- [ ] README/architecture 同步两个查询及新增文件职责；阶段记录只记录实际命令、结果和未验证项，不把 mock 或单元结果说成模型体验验收。
- [ ] 集中运行显式 fgas_test 的 `./tools/run_tests.sh` 和 `git diff --check`。测试脚本会重建专用测试库；先结束当前引用该库的试用写入，上一轮虚拟业务的脱敏证据保留在 `/tmp/fgas-luna-trial-20261027/`，不触碰日常库，不使用 npm dev --reset-db。
- [ ] 本次无前端源码变化；已有公开接入指南已在上一轮 build 通过，不因每次后端局部修改重复构建。若实施期间另改静态公开指南，再集中运行一次 npm run build。
- [ ] 检查实际差异与设计一致，特别检查无写入模拟、无新表/字段、无额外重试/状态机制；完成后报告检查结果和未做的真实模型验证。

## 当前进度与执行边界

本计划已由用户取消；尚未创建新查询模块、修改业务行为或运行数据库测试。不新增 pending_approvals、approval_preview，也不继续补 attention 筛选或其他替代接口。若未来出现现有资料不足以完成的具体任务，再据实讨论，不自动恢复本计划。
