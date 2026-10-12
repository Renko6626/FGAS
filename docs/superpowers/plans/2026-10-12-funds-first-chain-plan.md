# 第一条资金链 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or, only when explicitly selected, superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **状态：已获实施授权。** 按用户最新要求先搭建本机原型：占位账户取代本增量 Casdoor 接入，资金账户与库存位置支持标签及端点过滤。gpt-6.1-sol low 开发，gpt-6.1-sol medium 阶段审阅；优先壳子与真实路径，不增加大量测试。

**Goal:** 建立统一资金转移记录，完成资金期初、收付、账户转账、三档审批、余额查询及最薄操作界面。

**Architecture:** 资金内核只记录明确来源、去向及金额，并保存平衡分录。外层办理身份、批准、实际确认和审计，统一协调事务；垫付、偿还使用同一资金模式，逐笔标记及匹配在下一增量增加。

**Tech Stack:** 沿用 FastAPI / Pydantic、Vue 3 / TypeScript / Vite / Naive UI、SQLAlchemy 2 / Alembic / PostgreSQL。复用 Casdoor SSO，本系统管理权限。具体认证客户端、版本与部署配置在执行对应任务前落实。

**Spec:** [architecture.md](../../../architecture.md)，v0.4 / Part 1；[总路线图](2026-10-12-part1-roadmap.md)。

## Global Constraints

- 单实例、单社团、人民币；不建多组织、多币种或汇率模型。
- 当前服务器仅开发测试，正式服务器空库初始化，不迁移测试账目。
- 首个管理员由部署配置绑定受认证的身份，日常启动不覆盖既有权限。
- 用户明确选择来源和去向；说明与预设不推断科目，修改预设不改历史。
- 内核不理解垫付、报销、采购用途或成本；统一记录及确定性分录规则供外层复用。
- 普通管理员及受信任用户操作自动批准，不受信任用户由管理员或受信任用户人工批准。
- 管理员专属：权限与访问启停、关键记账规则修改、正式恢复与数据替换。
- 正式记录只追加及更正，不能普通覆盖、删除或直接改余额。
- 不做成本、库存、MCP、自动 POS 导入、复杂规则编辑器或通用工作流。
- 只运行相关检查并覆盖关键行为，不机械 TDD、不穷举 corner case；界面只做构建与必要截图。

## Review Focus

以下是本增量最值得检查的风险，随所属任务覆盖，不扩成大量异常矩阵：

- 金额被浮点数改变：任务 1 以精确值确认元与分的转换。
- 用户以提交角色或姓名绕过登录身份：任务 2 从认证主体取得本系统权限。
- 重试或提交失败产生重复、部分正式记录：任务 3 用真实 PostgreSQL 验证幂等及整体回滚。
- 批准之后变更来源、去向或金额：任务 3 / 4 绑定内容版本，拒绝过期批准。
- 将收入、费用或往来科目的余额计入组织现金：任务 5 只合计被定义为组织资金的账户。

## 推荐的第一笔记录形状

第一版采用一笔转移一个来源、一个去向、一个金额。分次付款分别记录，不先建设一笔多来源、多去向的分摊结构。

| 字段 | 用途 |
| --- | --- |
| `source_account_id` / `destination_account_id` | 明确选择两个记账对象，不根据说明生成 |
| `amount_minor` | 正式金额，整数人民币分；界面输入元，按十进制精确转换 |
| `effective_date` | 实际业务生效日期 |
| `counterparty_id`（可选） | 业务参与方，不等于记账端点 |
| `description` | 自由说明，预设只预填 |
| `operation_id` / `idempotency_key` | 实际动作与提交重试的标识 |
| `reversal_of`（更正时） | 原正式记录引用 |

发起人来自认证上下文，记录时间来自服务器；角色、批准人和执行人不作为可自行填写的可信字段。

内核不要求两个端点都是银行账户。`LedgerAccount` 表示可记账端点，`FundAccount` 标识哪些端点代表组织实际资金；一项组织资金账户绑定其记账科目。账户性质用于正确解释余额，交易对手另行关联。

第一条链开放组织资金、明确收支分类及期初对应项。内核的账户模型允许后续加入成员往来；逐笔债务录入随下一增量的标记和匹配能力开放，避免未结明细与往来账失去对应。

现金流箭头是记账关系，不表示所有类别的来源余额都减少。首次展示普通资金账户转移；往来端点的余额影响在后续入口明确展示，不以成员私人现金余额代替组织债务。

## 文件职责

采用 architecture.md 的分层，只建立本增量实际使用的文件，不预建未来空模块。

| 路径 | 职责 |
| --- | --- |
| `backend/kernel/types/money.py` | 精确金额表达及输入转换 |
| `backend/kernel/accounting/models.py` | 账户、资金转移、凭证和分录的领域类型 |
| `backend/kernel/accounting/ledger.py` | 统一分录表达与平衡约束，不处理垫付标签 |
| `backend/kernel/posting/service.py` | 正式流水写入规则，与事务实现协作 |
| `backend/modules/funds/service.py` | 端点选择、预览及资金业务方案 |
| `backend/application/workflows/funds.py` | 自动或人工批准、内容版本、执行与冲销编排 |
| `backend/application/queries/funds.py` | 余额、列表和交易追溯 |
| `backend/infrastructure/persistence/models.py` / `database.py` | SQLAlchemy 映射、事务和锁 |
| `backend/infrastructure/auth/casdoor.py` | 认证适配，具体客户端待确定 |
| `backend/entrypoints/http/funds.py` / `auth.py` / `users.py` | HTTP 适配，不实现独立账务逻辑 |
| `backend/migrations/` | 实际使用的 Schema 迁移 |
| `frontend/src/api/funds.ts` | 资金接口类型与调用 |
| `frontend/src/views/FundsView.vue` / `ApprovalsView.vue` | 账户、录入、流水、审批和追溯 |

文件拆分属于建议，不要求每个简单函数单独建文件。不为每张表创建 DAO 和 Service。

## Task 1：金额、账户与统一转移模型

**Files:** `money.py`、`accounting/models.py`、`accounting/ledger.py`、持久化模型及迁移。

**Interfaces:** 推荐 `parse_cny(text: str) -> int`；`MoneyTransfer` 使用上表字段；`build_entry(transfer: MoneyTransfer) -> JournalEntry` 不接收业务说明来选择账户。

- [ ] 确认人民币按分存储、一源一去一金额及账户绑定关系，再写迁移。
- [ ] 实现精确金额转换、账户引用及通用分录表示，确保每笔借贷平衡。
- [ ] 建立账户、转移、凭证和分录的持久化及唯一来源关系，不保存可手改余额；外层批准内容与版本用独立记录保存，供后续过账读取。
- [ ] 用 `12.34` 元等于 `1234` 分、资金账户间转移 `10000` 分生成平衡记录的行为用例验证；不测试每个字段组合。

**完成标志：** 不含业务标签的转移可以被准确记录，账户与正式分录可追溯。

## Task 2：开发占位账户、三档权限与管理员初始化

**Files:** 认证适配、应用身份与权限服务、HTTP 认证入口及用户管理入口。

**Interfaces:** `Actor(user_id: UUID, role: Role)` 来自后端认证；`Role` 固定三档。外部身份映射和会话机制在此任务实施前确认。

- [ ] 本机使用明确标识的开发账户选择与后端会话，占位认证通过开发配置启用；认证适配保留未来接入 Casdoor 的边界。
- [ ] 关联本系统用户，在初始化时按部署配置指定首个管理员。
- [ ] 管理员可管理用户访问和三档权限；受信任用户可办理及批准普通业务。
- [ ] 验证角色调整在后端生效，客户端提交身份参数不能提升权限；重复启动不覆盖已管理的角色。

**完成标志：** 三档占位用户可以跑通不同业务权限；开发账户只在开发模式提供，正式认证尚未实现须明确说明。

## Task 3：事务、幂等与最小冲销

**Files:** `kernel/posting/service.py`、数据库事务适配、资金工作流。

**Interfaces:** 推荐 `post_transfer(actor: Actor, approved_operation: ApprovedOperation) -> PostingResult`；`reverse_transfer(actor: Actor, transaction_id: UUID, reason: str, idempotency_key: str) -> PostingResult`。

- [ ] 在事务和锁内校验身份、持久化批准内容及当前账户，写入转移、分录、状态和审计；不能仅信任调用方传来的 ApprovedOperation 对象。
- [ ] 相同标识和相同内容返回已有结果，不同内容拒绝；单实例采用简单串行正式过账方式，具体数据库锁实现保持局部。
- [ ] 实现关联原记录的反向转移，防止同一原记录重复冲销；不提供直接编辑正式金额的接口。
- [ ] 在真实 PostgreSQL 上验证同一转移重试不重复变化，以及中途写入失败没有留下正式流水或已完成状态。
- [ ] 验证冲销后余额恢复，原记录和反向记录都仍能查询。

**完成标志：** 重试、更正和失败都不会让账本出现不明余额。

## Task 4：资金转移预览与外层批准

**Files:** `modules/funds/service.py`、`application/workflows/funds.py`、HTTP 资金入口。

**Interfaces:** 推荐 `preview_transfer(actor: Actor, input: TransferInput) -> TransferPreview`；`submit_transfer(...) -> OperationResult`；`approve_transfer(actor: Actor, transaction_id: UUID, version: int) -> OperationResult`。

- [ ] 预览明确选定端点的金额变化和实际分录，不从说明推断分类。
- [ ] 普通管理员、受信任用户提交已确认事实时自动批准并执行；不受信任用户只创建待审批内容。
- [ ] 人工批准绑定具体内容版本；修改正式影响的参数不能沿用旧批准。
- [ ] 验证同一笔 `10000` 分转移：不受信任用户提交前后余额不变，受信任用户批准后才产生一次变化；陈旧批准不能提交修改后的内容。

**完成标志：** 业务批准和转移数据分开，待审批记录不混入正式资金余额。

## Task 5：期初、余额与交易追溯

**Files:** 资金业务服务、查询服务、HTTP 查询入口。

**Interfaces:** 推荐 `get_fund_balances(actor: Actor) -> list[FundBalance]`；`list_transactions(actor: Actor, filter: TransactionFilter) -> TransactionPage`；`get_transaction(actor: Actor, id: UUID) -> TransactionDetail`。

- [ ] 按统一转移机制登记期初，保留确认人、日期和依据，不设置独立余额。
- [ ] 只从正式分录计算余额，组织资金合计仅包含 FundAccount 端点；未核对时标为账面余额。
- [ ] 展示来源、去向、金额、业务日期、发起人、批准依据及冲销关系。
- [ ] 共用一个具体样例核对：期初银行 `200000` 分；银行转现金 `30000` 分；现金支付 `5000` 分后，银行 `170000`、现金 `25000`、组织资金 `195000` 分。支出分类余额不再加进组织资金。

**完成标志：** 用户能回答有多少钱、有哪些变化，以及每次变化的批准来源。

## Task 6：最薄 Vue 操作界面与增量交付

**Files:** `api/funds.ts`、`FundsView.vue`、`ApprovalsView.vue`、认证导航与必要用户权限入口。

**Interfaces:** 只调用任务 2–5 的 HTTP 接口；后端负责可信权限和正式分录，不在前端重复记账算法。

- [ ] 资金页面提供分类与标签过滤的端点选择、来源 → 去向、金额和自由说明；预设可修改。
- [ ] 资金账户和库存位置目录显示标签列，可创建、编辑简单标签；库存位置仅目录，不实现完整数量账本。
- [ ] 显示预览、账户余额、交易历史及详情；审批页展示待审批的同一笔转移。
- [ ] 管理员提供最小权限管理入口；页面可见性随角色变化，权限仍由后端执行。
- [ ] 运行相关后端检查和前端构建，必要时截图查看；不新增常规 UI 永久测试，不自动点击或填表验收。
- [ ] 记录启动、迁移、SSO 配置及共同样例使用方法，不声称仅构建成功就完成业务验收。

**完成标志：** 基础资金录入与追溯可用；本增量的关键行为有实际数据库证据，界面可构建。

## 验证命令安排

执行时建立项目实际脚本，以下是推荐入口，不表示当前已存在或已运行：

- 后端：`python -m pytest backend/tests/test_funds.py`，集中验证金额、批准、幂等、回滚、冲销和余额；复用真实数据库夹具，不跨层重复整个场景。
- 数据库：`alembic upgrade head`，在隔离测试数据库验证实际迁移。
- 前端：在 `frontend/` 运行 `npm run build`，验证类型和构建。

不添加大规模压力、随机状态化或全部异常组合测试。必要测试随所属任务写入，普通项目配置、页面文案和布局不因改变而新增测试。

## 本次待审阅的具体方案

- 每笔转移先采用一源、一去、一个金额；分次动作分开记录。
- 正式金额整数分，界面人民币元精确转换，不静默舍入输入。
- 保留 LedgerAccount 与 FundAccount 的职责区分，普通转移共用分录机制。
- 按上述 6 个任务先交付资金链；下一增量增加垫付标记与逐笔偿还匹配，不另造内核。
- Casdoor 具体协议、客户端和配置尚未决定，在任务 2 前提出方案确认。

## 自检

架构中本增量涉及的资金记录、身份、三档批准、期初、追溯和最小更正均有任务归属。库存、逐笔垫付、成本、恢复及外部集成留在总路线图的对应增量，不宣称已经完成 Part 1。账户形状和接口仍标为推荐，未安装依赖、搭建项目或编写产品代码。
