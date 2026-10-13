# 库存位置、SKU 与整笔货物转移实施计划

> 状态：2026-10-13 用户确认推荐技术方案及资金先按现有规则生效、货物随后确认方案，授权 subagent-driven 开发。开发使用 gpt-6.1-sol low，任务及最终审阅使用 gpt-6.1-sol medium。
> 实施使用 superpowers:subagent-driven-development，逐任务开发、审阅和必要修复。不得清空现有开发库、部署、发布或自动合并；新架构选择由主 agent 提交用户。

**Goal:** 创建实际及虚拟仓库、维护 SKU，以包含多个 SKU 的独立 Transfer 登记一批货物，经批准和额外手动确认后产生正式数量流水。

**Architecture:** 沿用模块化单体和中央权威账本，数量内核处理来源、去向与精确数量，warehouse 生成业务方案，应用层编排审批和实际确认，基础设施负责事务、锁及持久化。每批一条独立 Transfer，不增加父单、批次层或分批执行层；来源引用只承担追溯职责。

**Tech Stack:** 继续使用 FastAPI、Pydantic、SQLAlchemy 2、PostgreSQL、Vue、TypeScript、Vite、Naive UI，不新增重要依赖。

**Spec:** [architecture.md](../../../architecture.md) 第 3、4、7、8、9 节；[Part 1 路线图](2026-10-12-part1-roadmap.md) 第 4 节；本次用户补充见第 1 节。

## 1. 本轮明确的业务方向

- 用户可创建“仓库”，包括实际位置和虚拟位置；虚拟位置按照架构解释为组织库存的外部边界。
- 所有货物转移增加“在途 → 已完成”流程，均须人在提交后额外手动确认，不提供创建时直接完成的快捷选项。
- 管理员和受信任用户自动批准，不受信任用户人工审批，沿用三档权限原则。
- 每批货对应一条独立 Transfer，分两批就建两条；每条包含一个来源、一个去向和多个 SKU 明细。
- 不建立批次父单，不做一条 Transfer 内的部分完成、分别交出接收或分批结清。
- 接收数量不符时保留实际核对结果，另建关联原转移的盘点盈亏；不改原获准数量，不重复扣增。
- 资金关联必须以 architecture 的具体关系为依据，不从采购描述、数量或付款额推导成本和债务。

2026-10-13 用户确认后已同步 architecture 第 7 节和路线图：取消创建时直接完成、分批执行及分别交出/接收模型，新增关联盘点盈亏规则。旧版 v0.3、原始 v0.4 文档保留历史设计，不作为本轮执行依据。资金关联与成本估值边界未变。

## 2. 对照架构后的核心规则

### 仓库与库存范围

- 实际位置：仓库、宿舍、展会现场等，计入组织库存；位置可关联业务成员作为保管人，不要求保管人有登录账号。
- 虚拟位置：商家、客户、期初来源、损耗去向等，只标记外部边界，不维护其真实库存，不加入组织库存合计，不要求虚拟端点持有库存或有人确认接收。
- 不建立虚拟“在途仓库”。至少一个端点必须是实际位置；拒绝同来源去向、虚拟到虚拟。
- 当前保管人用于回答现在谁保管；保管关系保留有效时间和历史成员，实际确认人独立记录为认证用户。改保管人不改变数量，也不改历史执行人。
- 只记录组织拥有的货。实物为零与尚未估值分别表达，价值始终显示“未估值”。

### Transfer 与数量事实

| 动作 | 主状态 | 数量账变化 |
| --- | --- | --- |
| 可信用户创建 | 在途 | 无；保存自动批准依据 |
| 普通用户创建 | 待审批 | 无 |
| 可信用户批准 | 在途 | 无；保存人工批准内容和版本 |
| 人工确认实际完成并通过执行校验 | 已完成 | 整笔一次生成所有 SKU 的来源、去向变化 |

“在途”仅表示已批准、尚未确认完成，不证明已交出。本阶段不记录交出未收到的中间事实，组织账面库存等于各实际位置正式流水的汇总。不能把在途计划数量再计入总库存或称为实际未收妥数量。

批准不扣库存、不预留；确认时锁内检查来源现有数量，默认拒绝任何 SKU 导致实际位置负库存。多 SKU 中任意一行失败，整条 Transfer 不完成，不留下部分流水。

首版批准后不编辑来源、去向或明细；未完成时允许可信用户取消并说明原因，取消不产生数量变化；如有待审批完成申请，一并失效并留痕，旧申请此后不得批准执行。待审批允许可信用户拒绝。已完成记录不能取消、删除或覆盖。

实际退货作为新 Transfer；录错的正式事实需要关联原记录的更正。复杂更正留待路线图试用阶段，本阶段无支持的更正明确拒绝，不能用普通删除或实际退货按钮掩盖历史错误。

### 收货差异与盘点调整

原 Transfer 按批准的整笔数量完成；实收不符时保存本次应收、实收及差额，另建差异记录，不能把本次实收当成全仓实盘余额。差异记录保留位置、SKU、比较时点、原因、原转移及完成引用、盘点人、批准依据和关联调整记录。

盘亏复用实际位置→外部盘亏边界的 Transfer，盘盈复用外部盘盈边界→实际位置的 Transfer；各自按批准、在途、手动确认路线生效，不引入另一套数量算法。差异依据由 `StockDifference` 保存，调整关联普通 `StockTransfer`，这是已确认的持久化实现，不能由备注替代可定位关系。

A 实际发30、B实收28：原转移入账 A减30、B加30，目标盘亏2后 B净增28、总量减2。若2仍在A，应按真实依据更正，或关联 A盘盈2、B盘亏2，总量不变。少收不自动判损失。

原转移已完成但差异未调整时，账面数与未处理差异并列显示。关联差异不允许重复调整；后续独立盘点用自己的编号和依据。原转移必须已完成才可登记关联差异；本阶段同一完成动作、转移明细及实际位置只登记一次本次转移核对差异，数据库以这三项联合唯一，正负差额不得为零。目标位置差额=本次实收−获准数量，来源位置差额=获准数量−本次实际交出；两者均以正数为盘盈、负数为盘亏。只能选择原转移的实际端点，不能替其他位置凭空调整。调整数量必须等于该笔已确认差额的绝对值，方向与盈亏一致；每笔差异最多一个有效的待审批/在途/已完成调整。被拒绝或未完成取消后可重新提交；已完成后不得再调一遍。来源盘盈和目标盘亏是两个位置的独立依据记录，不能用一个差额在两个位置重复扣减。若同一正式操作包含原转移与已获准调整，必须整体事务提交，不能靠连续两次 API 模拟原子性。完整盘点和复杂更正仍随试用补齐，收货最小差异入口纳入本阶段。

### 审批与额外确认

批准内容包括来源、去向、全部 SKU 数量、动作类型、依据及相关引用；实际确认记录内容版本、确认日期、实际确认人、操作身份、依据及时间。

可信用户点击“确认完成”可执行；不受信任用户的确认请求同样需要人工审批，不能利用已有 Transfer 的批准绕过本次事实确认权限。保留其确认申报，可信用户审阅后点击批准确认，原申报人和最终批准/执行人分别留痕，Transfer 在此期间仍为在途。

查询角色及账户启停需锁内重新加载。业务成员或保管人 ID 不充当认证身份，不要求可信操作者必须等于保管人，不要求外部客户登录。

## 3. 资金及其他记录的关联

依据 architecture 第 4 节“关联必须表达具体含义”、第 7 节外部边界、第 8 节统一提交：

1. **共同来源引用**：多批到货和多次付款可指向同一个可定位的原始事项/单据引用。这里没有父单金额、计划数量、进度或审批生命周期。
2. **已有资金事实引用**：Transfer 可关联零到多条现有资金流水，以稳定 ID 查询具体记录；垫付沿其资金流水找到 MemberClaim。关联不新建付款、不改变匹配或债务、不赋予钱到 SKU 的分摊含义。
3. **审批与交接引用**：完成动作直接关联本条 Transfer 及其 SKU 明细，正式 StockMove 直接关联完成动作和明细，不用备注代替可定位关系。

关联一笔付款的多批到货分别建立自己的引用，不能要求付款金额等于数量、不能把同一款项被引用两次当成重复付款。退款不自动反向移动货，货物退回也不自动退款。

沿用原架构：允许同入口登记钱货，也允许分别登记后关联；本轮不把“只允许关联已有资金”定成范围限制。引用已有记录不产生新资金事实。同入口新增钱货时，必须在实施方案里确定付款生效时点、两个部分的审批和事务边界；同一次正式操作整体提交或回滚。具体复合接口见第 8 节已确认方案，实施者不能临场选择，也不能仅凭两个连续请求声称原子提交。

待审批或被拒绝的资金记录不能展示成已付款；冲销后的关联仍保留并展示当前状态。引用已有业务要求服务器检查目标存在，返回业务类型、编号和当前状态，不接受前端自报“已付款”。

## 4. 实施前代码事实与已确认方案

实施前 `Location` 只有名称、保管人文本和标签；没有 SKU、StockMove、历史保管关系。现有 `Transfer` 是资金记录，强制金额和科目外键；`Audit.transfer_id` 也外键指向资金表。资金 `approve` 会直接 `post`，不能直接用于货物批准。

**推荐在同一应用内新增货物专用模型和接口，复用事务、串行锁及权限原则。** 不把 SKU 强塞进资金 Transfer，不新增通用单据引擎，也不复制一套资金账本。界面共用表达和审批入口，服务端分别校验两类事实。

相比把现有资金表改成通用资金/库存单据，新表方案对资金与偿还既有行为影响较小；代价是两个业务记录模型及独立的库存审计表。跨钱货原子动作仍归应用编排，不由 warehouse 修改资金模块正式事实。

### 持久化对象（已确认并实现）

- `Sku` / `skus`：id、name、specification、unit、active；数量按整数个数保存，接口输入输出不带小数点的整数字符串；库存合计同样返回精确量值字符串，不经 JavaScript 浮点数求和。
- `LocationProfile` / `stock_location_profiles`：location_id 外键到已有 Location、kind=`physical|external`、external_kind、active；避免在现有表直接新增必填列。已有未配置位置通过显式初始化补 physical profile，不静默改变其用途。
- `LocationCustody` / `location_custodies`：location_id、member_id、valid_from、valid_to、记录操作者；当前保管关系从有效区间读取，老 custodian_label 只作为历史文本展示，不能自动按名字匹配成员。
- `StockTransfer` / `stock_transfers`：来源/去向 location_id、action_kind、effective_date、description、basis、来源引用、actor_id、status、content_version、execution_version、批准依据、原始提交快照、idempotency_key、记录时间。
- `StockTransferLine` / `stock_transfer_lines`：transfer_id、sku_id、quantity_minor，单条 Transfer 内 SKU 唯一。数量必须正值。
- `StockConfirmation` / `stock_confirmations`：transfer_id、content_version、execution_version、申请者、实际完成日期、依据、审批状态及审批/执行人、幂等键；同条 Transfer 只允许一个有效待处理完成申请和一次成功完成。
- `StockMove` / `stock_moves`：confirmation_id、transfer_line_id、sku_id、来源/去向、quantity_minor、生效日期和记录时间；以完成动作+明细唯一约束防止重复过账。
- `StockDifference` / `stock_differences`（已确认）：原转移/完成引用、位置、SKU、比较时点、本次批准数量与实收/核对数量（本轮不实现全仓盘点）、差额、原因、操作者及状态；其调整关联普通 StockTransfer，限制同一差异有效调整量，不新建盘点账本。
- `StockDifferenceAdjustment` / `stock_difference_adjustments`：关联差异和普通调整 Transfer；拒绝/取消的调整保留历史，有效调整阻止重复创建。
- `StockOperation` / `stock_operations`：操作者、外层幂等键、完整请求 JSON、stock/fund 两个引用及记录时刻，不承担审批或批次状态。
- `StockTransferFundReference`：stock_transfer_id、fund_transfer_id，联合唯一且外键指向已有资金记录；仅作追溯，不保存分摊金额。
- `StockAudit` / `stock_audit_events`：stock_transfer_id、actor_id、action、版本/依据快照、幂等键、原始请求、created_at；确认申请 ID 保存在 JSON 快照中；避免改现有资金 Audit 外键。

不存可独立修改的库存余额。转移数量必须为正整数且不超过 9,007,199,254,740,991，接口量值以十进制字符串传输，拒绝科学计数法、负数、零及小数数量，不静默舍入。一个 SKU 的计量单位在有转移引用后不允许普通编辑；已引用的位置类型不允许改为另一种库存边界。停用对象保留历史，待完成 Transfer 遇到停用需明确冲突，不能静默替换端点。

### 应用及 HTTP 接口（已确认，实际契约见执行记录）

- `backend/kernel/stock.py`：`quantity_to_minor(value: str, allow_zero: bool = False) -> int`、`validate_move(source_kind: str, destination_kind: str, quantity_minor: int, available_minor: int | None) -> None`，整数数量、端点和负库存纯校验。
- `backend/modules/warehouse/plans.py`：`build_moves(source_id: str, destination_id: str, lines: list[dict]) -> list[dict]`，为整个完成动作生成通用数量方案，不访问数据库。
- `backend/application/warehouse_catalogs.py`（新增）：`create_sku(db, user, data: dict) -> dict`、`update_sku(db, user, id: str, data: dict) -> dict`、`set_custody(db, user, location_id: str, member_id: str | None) -> dict`；目录写入锁内刷新身份，保管变更以服务器时刻生效，本阶段不提供回溯/未来区间编辑。
- `backend/application/warehouse.py`：`submit_transfer(db, user, data: dict) -> dict`、`decide_transfer(db, user, identifier: str, data: dict, rejection: bool = False) -> dict`、`request_completion(db, user, id: str, data: dict) -> dict`、`decide_completion(db, user, identifier: str, data: dict, rejection: bool = False) -> dict`、`cancel_transfer(db, user, id: str, data: dict) -> dict`、`transfer_detail(db, id: str) -> dict`、`inventory(db, filters: dict) -> dict`。
- `backend/infrastructure/stock_store.py`：库存对象、幂等检索、流水及一致快照查询；复用 `store.lock(db)` 和 HTTP 已有事务依赖，不自行 commit。
- `/api/skus` GET/POST、`/api/skus/{id}` PATCH；目录写入只允许可信角色，沿用现有目录授权。
- `/api/locations` 保留并扩展响应为 kind、external_kind、active 和当前成员保管关系；`/api/locations/{id}/custody` POST 保存保管变更，禁止覆盖旧历史。
- `/api/stock-transfers` GET/POST、`/{id}` GET、`/{id}/approve` POST、`/{id}/reject` POST、`/{id}/cancel` POST、`/{id}/completion` POST。
- `/api/stock-confirmations/{id}/approve` POST、`/{id}/reject` POST；普通用户提交 completion 后无库存变化，可信用户主动提交 completion 则自动批准该事实并在本次手动操作中完成。
- `/api/stock-transfers/{id}/fund-references` POST：`{fund_transfer_id,idempotency_key}`；可信角色可后补追溯关联，锁内校验目标存在及联合唯一，完整保存操作者和审计。不修改任何已批准数量、资金状态或 SKU 成本，不提供覆盖删除引用。原单已完成也可补关联，现有资金冲销后关联仍保留。
- `/api/stock-transfers/{id}/differences` POST：`{line_id,location_id,observed_quantity,comparison_at,basis,idempotency_key}`；本次转移核对的 observed_quantity 是本次实收/核对量，不是全仓余额。服务端从原明细生成应收基准并保存原始输入及整数差额；先只允许可信角色，普通用户实际核对记录随完成申请保留并由可信用户审阅登记。
- `/api/stock-differences` GET、`/{id}` GET、`/{id}/adjustment` POST：`{external_location_id,effective_date,basis,idempotency_key}`，根据差额生成普通盈亏 Transfer，不接受任意调整数量或位置。可信角色办理；生成后仍须手动完成调整，不自动扣增。
- `/api/inventory` GET：按 SKU、实际位置、成员过滤；返回 snapshot_at、数量、单位与未估值说明；`/api/stock-moves` GET 提供正式历史查询。

`StockTransferInput`：source_location_id、destination_location_id、action_kind、effective_date、description、basis、source_reference（可定位的编号/链接）、fund_transfer_ids、lines=[{sku_id,quantity}]、idempotency_key。动作类型覆盖 opening、arrival、sale、gift、loss、return、internal、adjustment_gain、adjustment_loss，并校验其端点方向；盈亏类型必须关联服务端核验过的差异，不允许普通提交伪造该类型。实际退回分外部退回和内部退回，保留类型与实际方向。

`CompletionInput`：expected_content_version、expected_execution_version、effective_date、basis、idempotency_key；确认范围就是已批准的全部明细；存在差异时另传实际核对依据供建立差异记录，不能通过实收字段改变原获准数量或实现部分完成。核对输入采用 observations=[{line_id,observed_quantity,basis}]，每条明细至多一个观察值，未填表示没有本次数量核对记录，不表示实际为零；有记录时保留于完成申请/执行快照，差异记录由可信用户另行登记。单据创建日期与实际完成生效日期分别保留，不伪造系统记录时间。

提交和确认分别使用“操作者+动作类型+幂等键”去重，相同键不同原始内容返回 409。同一完成申请审批重试按动作键返回既有结果，成功过账必须另有业务唯一约束。批准、确认、库存检查、关联校验和正式写入均在锁内刷新状态；重试查找既有结果先于完成状态拒绝。

### 锁、版本、拒绝与查询的一致性

Transfer 使用 content_version 标记冻结的批准内容，execution_version 在批准/拒绝、申请完成、拒绝完成、完成及取消后推进。完成申请绑定两个版本；取消先按幂等键找旧结果，然后使有效申请失效。拒绝完成申请只结束本次申请，原 Transfer 仍为在途，可重新核对并申请；旧申请不可复用。StockConfirmation 的成功状态与原 Transfer 已完成及全部 StockMove 在同一事务写入。

库存汇总、成员保管归属与未处理差异使用同一 SQL 语句/CTE 快照；详情跨多次查询时采用明确的一致读取方式，不能仅记录应用时间后声称数据来自同一快照。只读查询不取正式写入锁，不修改业务状态。

## 5. 已确认的技术方案

| 决策 | 推荐 | 主要取舍 |
| --- | --- | --- |
| 数量表示 | 所有 SKU 统一整数计数，无 quantity_scale 或小数精度配置 | 支持本、件等计数单位标签；小数拒绝，不静默舍入 |
| 库存执行 | 不预留，整笔完成时拒绝负库存 | 简单且符合当前架构建议；批准不保证之后一定能执行 |
| 模型和接口 | 第 4 节库存专用模型、接口，复用事务锁和三档权限 | 保持资金与库存职责清楚，避免较大资金表重构 |
| 保管关系 | 使用已有业务成员及有效时间，不自动匹配旧文本 | 可查当前成员库存并保留历史，无需引入登录绑定 |
| 资金关联接口 | 保留原架构同入口或后续关联两种方式，先明确新增钱货的生效和事务边界 | 不擅自收窄范围，也不把引用误作资金过账 |
| 差异持久化 | 差异依据独立保存，调整关联普通 Transfer | 已确认业务路线；按第 4 节明确的独立依据与普通 Transfer 实施 |
| 普通用户的完成确认 | 保存确认申请，可信用户审阅并执行 | 保持全部写操作审批，额外申请只有必要的审批状态，不增加批次层 |

本阶段允许记录生效日期和真实记录时间，库存充分性按当前正式流水检查；不承诺历史时点重算或允许历史负库存。复杂历史补录及更正仍待试用阶段明确。

## 6. 任务顺序

第 5 节方案已确认，按以下七个任务顺序实施。每任务开发完成后由独立 medium 审阅，通过后进入下一任务。

### Task 1：SKU、仓库类型与历史保管关系

**Files:** `backend/infrastructure/models.py`、新增 `backend/infrastructure/stock_store.py`、新增 `backend/application/warehouse_catalogs.py`、`backend/application/catalogs.py`、`backend/entrypoints/schemas.py`、`backend/entrypoints/http.py`、`frontend/src/api/funds.ts`。

- [x] 建立 SKU、位置 profile 和保管关系；目录校验和响应落实第 4 节约定。
- [x] 保留现有位置与文本，不靠普通启动执行清空或自动匹配成员。初始化补 profile 的脚本/入口需显式执行并记录结果。
- [x] 保管变更串行关闭旧区间并建立新区间；有效时间区间不重叠，保留操作者。
- [x] 已有真实数据库测试检查兼容性；目录操作不另搭永久测试框架。

### Task 2：多 SKU Transfer 与批准流程

**Files:** `backend/infrastructure/models.py`、`backend/infrastructure/stock_store.py`、新增 `backend/application/warehouse.py`、schemas、http、新增 `backend/tests/test_stock_transfers.py`、`tools/run_tests.sh`。

- [x] 实现整条提交、自动批准、人工批准/拒绝、未完成取消和详情；普通用户不产生正式数量。
- [x] 验证多个 SKU、来源去向、动作类型、引用目标；内容批准后保持不变，分批通过新 Transfer 表达。
- [x] 增加一个真实行为场景：可信提交与普通用户提交/批准后的数量都保持零，版本不符或停用身份不得批准；提交重试返回原单，同键不同内容冲突。
- [x] 将库存用例纳入 `./tools/run_tests.sh`，复用 `backend/tests/conftest.py` 独立 PostgreSQL 夹具。

### Task 3：手动整笔确认与正式数量流水

**Files:** 新增 `backend/kernel/stock.py`、`backend/modules/warehouse/__init__.py`、`backend/modules/warehouse/plans.py`；models、stock_store、warehouse、schemas、http、库存测试文件。

- [x] 实现精确数量、整笔方案及完成申请；批准状态变化与正式库存执行分开。
- [x] 共用现有数据库事务和咨询锁，锁内重新加载角色、单据、SKU、位置和来源数量；一次写所有 SKU 的流水、完成状态及审计。
- [x] 真实主例：期初/到货确认 100 本到 A，批准 A→B 的 30 本后 A 仍为 100、B 为 0；手动完成后 A 为 70、B 为 30，总量 100。两批各一条 Transfer，另一个 SKU 同单转移也全部完成。
- [x] 在同一测试文件覆盖：普通用户完成申请在审批前无变化；批准后一次生效；虚拟端点不计库存；小数数量拒绝；一行库存不足不完成其余行。
- [x] 复用真实数据库失败注入与短屏障做代表性验证：流水写入失败整体回滚，重试不重复，两个 Transfer 竞争同一剩余库存仅可执行足额的一条。不扩为压力或组合矩阵。

### Task 4：关联盘点盈亏、资金引用与库存查询

**Files:** stock_store、warehouse、http、schemas、库存测试文件；资金应用仅按实际查询复用需要调整，不改变资金提交行为。

- [x] 实现收货差异依据及关联盘盈/盘亏入口，调整沿用普通 Transfer；完成记录保留实际核对结果，不改获准明细。
- [x] 真实核对30本转移+目标盘亏2本后 A70/B28/总量98；独立少发场景核对来源盘盈与目标盘亏后 A72/B28/总量100。调整重试不重复，无权请求不生效，失败不留下部分正式流水。
- [x] 按第 3 节保存明确引用；详情返回资金及垫付关联、状态、来源依据、审批和正式数量历史。
- [x] 实现按位置、成员和 SKU 的库存快照；虚拟端点排除，历史执行人不随保管变更改变，在途只显示计划待完成数量。
- [x] 核对一笔已确认垫付 1,000 元关联两条到货，完成货物后资金余额、逐笔未结和偿还匹配不变；被冲销资金引用保留且显示真实状态。
- [x] 以保管关系变更前后的真实查询核对当前成员汇总及历史追溯，复用前述库存用例数据。
- [x] 后补资金引用使用新增接口；在同一既有资金关联场景里验证已完成转移补引用成功、重复添加无新记录、引用本身不改资金或库存。
- [x] 补取消与待批完成申请行为：取消后旧申请批准冲突且零库存变化；拒绝一次完成申请后重新申请可以成功，最终仅一组正式流水。

### Task 5：同入口钱货组合及完整幂等

**Files:** 新增 `backend/application/stock_workflows.py`，修改 `backend/infrastructure/models.py`、`backend/infrastructure/stock_store.py`、`backend/entrypoints/schemas.py`、`backend/entrypoints/http.py`、`backend/tests/test_stock_transfers.py`；仅按必要内部接口复用修改 funds/member_claims。

**Interfaces:** `submit_stock_with_money(db, user, data: dict) -> dict` 和 `/api/stock-operations` POST，输入和响应见第 8 节已确认方案。另需 `StockOperation` 保存原始完整请求和最终两个业务记录引用，操作者+动作键联合唯一，状态不承担父单或交接进度职责，仅是复合请求的幂等执行记录。

- [x] 同事务保存整条请求快照、调用现有资金/垫付提交、创建在途或待审批货物并建立关系；锁内重新验证角色；内部子键从操作 ID 派生，并使用固定内部命名空间，避免与用户已有资金键冲突。
- [x] 普通资金依旧自动/人工审批后生效；垫付权限和金额确认复用现有规则。货物完成不再次提交钱；钱货取消、拒绝及冲销彼此不自动操作。
- [x] 相同完整请求重试返回同一对记录，相同动作键不同内容409；任一部分写入失败整体回滚。拒绝同时传已有资金引用与新建资金动作，避免不明确重复登记。
- [x] 真实数据库核对资金2000→采购付款1000后资金1000、货仍零；货完成100本后钱保持1000，复合重试与完成重试各无新付款。以同一夹具补垫付组合及普通角色审批边界；失败注入验证不留下半个请求。

### Task 6：页面接入与统一待办入口

**Files:** 新增 `frontend/src/api/warehouse.ts`、`frontend/src/views/InventoryView.vue`、`frontend/src/views/StockTransfersView.vue`、`frontend/src/components/StockTransferEditor.vue`；修改 `frontend/src/views/CatalogView.vue`、`frontend/src/App.vue`，新增 `frontend/src/views/SkusView.vue`、`frontend/src/components/StockCompletionEditor.vue`、`frontend/src/components/StockDifferenceEditor.vue`。

- [x] 仓库目录可创建实际及虚拟端点、维护成员保管；SKU 目录包含计数单位，不提供小数精度配置。
- [x] Transfer 编辑器选择来源、去向、多个 SKU、数量、依据及可选关联记录；可选同入口新增普通资金或垫付，资金端点及成员金额确认沿用已有组件/API语义，展示钱货各自的生效时点；不出现父单、批次父层或部分完成字段。
- [x] 列表显示待审批、在途、已完成；详情独立提供“确认完成”，展示整条数量影响；普通用户确认申报进入审批待办，可信用户明确审阅实际事实。
- [x] 库存页按成员/位置/SKU 查询并显示“未估值”及未调整差异，完成详情提供“记录数量差异”并追溯调整；审批入口同时汇集资金和货物待办，分派至对应接口，不套用资金 approve。
- [x] 身份切换清除编辑状态，提交失败保留内容和幂等键，409 提示刷新当前状态；结果不确定时查询既有动作后重试，避免引导再次实际交货。
- [x] 运行 `npm run build`；按需截图，不自动点击或填表，不新增样式/布局永久测试。

### Task 7：集中核对与文档交付

**Files:** 本计划、`architecture.md`、Part 1 路线图、`docs/prototype-status.md`、`README.md`。

- [x] 核对外部边界、数量、批准和完成的独立性、资金引用不重复记账及真实数据库回滚证据。
- [x] 根据用户已确认的简化更新架构和路线图：每批独立 Transfer、额外手动确认、关联盘点盈亏、取消分批执行；保留原钱货关联原则，技术接口未确认项如实记录。
- [x] 运行完整 `./tools/run_tests.sh`；`npm run build` 沿用 Task 6 最终源码构建证据，文档变更不重复构建。相关检查通过后停止追加验证；仅实际新改动/失败再重跑对应检查。
- [x] 报告实际命令结果及未验证项，不把构建当成交互验收，不自动启动、重置、部署或发布。

## 7. Review Focus 与自检

- 普通确认接口、旧会话及审批按钮不能绕过锁内权限或已批准版本（Task 2–3）。
- 多 SKU 的部分失败不能留下部分库存或“已完成”；不同单据的竞争不能造成负库存（Task 3）。
- “在途”无实际交出依据，不伪称实际未收妥数量；虚拟端点和在途计划不重复进入总量（Task 3–4）。
- 同一垫付关联多批到货不产生第二份资金/债务，不暗含 SKU 成本分配（Task 4）。
- 更换保管人、修改目录显示或停用端点，不改历史事实、数量单位和审批对象（Task 1、4）。

计划覆盖路线图第 4 节的目录、数量、确认、外部边界、保管查询与资金关联，以及已修订第 5 节的最小收货差异入口；钱货复合接口按第 8 节推荐方案实施，未延期或删除。本计划未引入成本、估值、订单、通用流程引擎、登录绑定或新技术栈。

本计划的初始审查只涉及文档和源码。2026-10-13 用户确认推荐方案，开始实现；实际测试及各任务证据随后记录，不能把计划审查当成产品验收。


## 8. 本轮计划审查结论与钱货方案（已确认）

**审查依据：** 当前 architecture.md、路线图、models.py、funds.py、member_claims.py、HTTP 事务依赖及现有测试夹具。工作树只存在架构/路线图/本计划文档变更，未新增产品代码。本轮自行审查，未调用子 agent。

已补缺口：后补资金引用接口；收货差异及调整接口；盈亏动作类型与依据绑定；差额方向、有效调整唯一性和取消后重提；取消与待审批完成申请联动；目录写入身份刷新；精确数量边界；查询一致快照；实际核对输入与全仓盘点的区别。对应 Task 1–6 已有归属，验证复用现有真实数据库夹具，不新增验证工程。

**用户已明确确认具体模型/接口推荐方案及推荐的钱货生效方式，随后指定 subagent-driven 与开发/审阅模型，授权开始实施。**

### 推荐：资金按原规则生效，货物后来确认

同入口录入是同一应用命令，在同一数据库事务内建立资金动作、货物 Transfer 和关联；金额按既有 funds/member_claims 规则办理，货物仅批准至在途，不写 StockMove。之后手动完成只写数量事实，不再次调用资金提交。

例如采购已付 1,000、货未到：提交后钱已记，货仍在途。货物取消不自动退钱，资金冲销不自动取消货；界面同时展示两边真实状态。普通资金由不受信任用户录入仍待审批，货物也待审批，两边批准独立，互不借权。垫付仍仅可信角色办理并遵循已有金额确认，不能通过钱货入口绕过。

优点：保持已确认的资金批准后过账和货物额外确认语义，支持付款与到货时间不同。代价：同事项两部分可处于不同状态，界面需要分别展示。

拟新增 `backend/application/stock_workflows.py` 的 `submit_stock_with_money(db, user, data: dict) -> dict`，在应用层组合 warehouse 和既有 funds/member_claims，不由库存模块操作资金正式表，不引入父单或通用工作流引擎。HTTP 为 `/api/stock-operations` POST，输入 `{stock: StockTransferInput, money: {kind: 'fund_transfer'|'member_claim', data: Submit|ClaimSubmit}, idempotency_key}`，响应 `{stock_transfer,fund_transfer,claim?}`。该命令幂等快照覆盖两个部分，子动作内部键由该操作键确定生成且采用独立命名范围；相同完整请求返回同一对记录，任一创建/过账失败整体回滚。已有引用仍使用普通 stock-transfers 输入，不能混入新建钱货命令两次支付。

此方案已确认，对应 Task 5：组合服务、完整幂等及失败回滚检查、普通角色审批边界、同入口 UI 和真实钱货状态展示。至少以现有 funds/member_claims 真实入口核对钱先记、货后记，货确认重试不重复付款；两个子动作之一失败不留下另一部分的新记录。后续审批仍由各自已确认接口执行，不对已付款记录二次批准。

### 备选：钱货等完成后一起生效

同入口先保存未正式过账的钱货方案，额外完成确认时资金分录与 StockMove 一次提交。优点是该复合动作正式事实同进退；代价是资金批准后立即过账的既有语义出现特例，付款先于到货时仍须另行登记，还需改变已有资金/垫付批准入口的业务保护。选择此方案须补资金延期依据、禁止普通 approve 提前过账和跨模块完成接口，不可直接复用现有资金批准操作。

用户已选择推荐的第一种方案。第二种仅留作取舍说明，本次不实施。

## 执行中用户修订：整数 SKU

用户在 Task3 审阅期间明确要求 SKU 统一按整数计数。取消 quantity_scale 及小数支持，数量、实收观察、盘点差额和合计都使用精确整数；数量接口仍传整数字符串，资金金额语义不变。Task1–2 的历史报告保留当时精度设计，新修订覆盖其精度描述。Task3 修复同时规范 PostgreSQL SUM(bigint) 的 Decimal 返回值为 Python int，保留真实整数库存查询回归，不新增已取消的小数支持用例。


## 9. 执行记录与实际契约（2026-10-13）

Task 1–6 及修复已实现并完成逐任务审阅；Task 7 整理文档和集中检查。上方勾选表示本轮实现及指定检查，不表示浏览器产品验收或整分支最终审阅完成；控制器仍须完成最终整分支审阅。

第 4 节应用签名是设计时说明，当前生产入口分为 `warehouse`、`stock_differences`、`stock_queries` 与 `stock_workflows`；实际 HTTP 和请求字段以 [README](../../../README.md#stock-transfers-and-quantity-inventory) 和 `backend/entrypoints/schemas.py` 为准。Completion 保存可选 observations，不自动登记差异。完成请求创建推进 execution_version；后续审批使用创建后返回的当前版本。差异登记要求原 Transfer 已完成且位置为其物理端点；目标差额为 observed-approved，来源为 approved-observed。盈亏数量由服务器生成，可信用户创建调整至在途后仍须手动完成。没有全仓盘点或完成与调整同时执行的复合命令。

`StockOperation` 保存操作者、外层键、完整请求及两个业务引用，不是批次父单或工作流状态。服务端按操作 ID 派生并检查独立子键；外层重试保留原请求，子动作不采用客户端嵌套键执行。`POST /api/stock-operations` 请求仍需完整 stock 和 money 的嵌套键及外层键。钱货创建共享事务/保存点，普通金额按原规则生效，货物以后单独完成；资金引用与新建钱货互斥，已有资金/垫付不重复过账。

SKU 整数要求覆盖所有现行接口、模型、前端和数量汇总；旧任务报告里的小数精度描述被 Task 3 的整数修复取代，不是待部署的现行方案。根目录旧资金开发原型未改动，库存只存在隔离分支/测试数据库；没有当前生产分数量迁移承诺。

旧位置 profile 使用显式、幂等、非重置的 `AUTH_MODE=development .venv/bin/python -m backend.application.initialize --initialize-stock-profiles`；确认目标数据库后执行，保留记录及原文本、不自动匹配成员。该入口本轮没有在开发库执行。只使用独立 `fgas_test` 运行集中检查。

当前 UI 精确请求缓存覆盖同身份会话内重试、关闭/重开及同记录详情刷新，包括响应丢失后完成状态已变化的情形；页面完全重载丢失缓存，身份切换清除缓存。该路径完成源码审阅与构建，未运行浏览器交互验收。全仓盘点、复杂历史更正、成本估值、正式认证、附件、备份恢复和部署均未交付。

集中检查结果和验证限制见 [阶段记录](../../prototype-status.md)。本计划初始审查、历史任务结果和当前实现记录各有日期；初始文档审查不替代产品验收。最终整分支审阅：**待控制器执行**。
