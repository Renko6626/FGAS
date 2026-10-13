# 自由账户与 Transfer 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. 默认由主 agent 顺序实施；不自动委派。用户工作约定优先于技能中的一律 TDD、新增测试和逐任务复审要求。

**Goal:** 对齐资金与货物账户，删除固定用途及独立垫付申报模型，以普通 Transfer、双向结算匹配和薄盘点满足第一阶段业务。

**Architecture:** 沿用模块化单体和分别持久化的资金、数量账本。内核维护精确金额、数量与正式流水一致性；服务层负责授权、审批、结算、库存完成及盘点组织。自由标签不驱动账本规则，不新增通用规则引擎、关系系统或恢复机制。

**Tech Stack:** 现有 FastAPI、SQLAlchemy、PostgreSQL、Vue 3、TypeScript、Naive UI；不新增重要依赖，不引入 Alembic。

**Spec:** [以 Transfer 为中心的操作模型](../../transfer-model.md)，以“阶段性构想”及已确认的报销、代收、薄盘点章节为目标；后文“当前实现说明”作为删除旧行为的依据。

## 全局约束与授权

- 本次允许破坏性修改，开发数据可丢弃、数据库可重建；不迁移历史账目，不保留旧接口别名或旧表兼容。仅重建配置指向的 FGAS 开发库，测试仅使用 `fgas_test`；不修改其他数据库，不输出连接凭据。
- 普通启动不清库。完整改动验证通过后，停开发应用、执行显式重建、按原方式启动；本轮计划编写不执行重建。
- 账户分类固定为 `public/private/external`，创建后不可变；联系人、名称、头像、标签、启用状态可改。私账允许无联系人，成员不拥有唯一强制账户。
- 公私资金余额均为流入减流出；组织资金合计只计公账。货物公私账户都计组织库存，外部不计入。
- 标签预设与自定义同存字符串数组，仅用于筛选。说明可空，不在完成时再填依据。
- 保留现有三档身份、审批、资金冲销、货物额外整笔完成及负库存限制；禁止货物外部到外部的规则由服务层执行。账户停用阻止新单，不阻止已有单处理。
- 保留实际保管历史，联系人只是联系方式关联，不代替保管人；不在本次引入新的交接流程。
- 只保留已有简单事务锁、正式流水唯一性和必要匹配约束；不加幂等键、版本体系扩展、自动重试、预留库存或请求恢复。
- 默认只做现有相关检查和构建，UI 至多截图；不自动点击、填表，不新增端到端环境或 CI 工作流。

## 方案取舍与需要用户审阅的具体决定

以下具体决定已获用户确认，并按此实施：

1. 资金账户模型 `FundAccount` / `fund_accounts`，货物账户 `StockAccount` / `stock_accounts`。删除旧 `Account`、资金标记附表、`Location` 与 `LocationProfile`；资金 HTTP 路径保留 `/api/accounts`，货物改为 `/api/stock-accounts`，货物引用统一 `source_account_id/destination_account_id`。
2. 删除固定货物 `action_kind`，资金与货物 Transfer 都使用 `tags`。`description` 为唯一业务说明；`source_reference` 保留可选原始单据编号，空白视为未填写。货物数量内部字段改为 `quantity`，HTTP 继续使用正整数字符串，金额仍按分。
3. 成员表只存 `id/name/note`，两类账户可选 `member_id`。成员改名不改账户名。保管表改称 `StockAccountCustody`，仍保存原有保管起止与操作人，账户联系人与当前保管人分别呈现。
4. 结算服务只接受已过账的原收支和结算付款。报销为私账→外部配公账→同一私账；代收交回为外部→私账配同一私账→公账。普通收支先按现有身份规则审核，结算匹配只允许可信用户维护。不额外增加报销认可标记。
5. 不强制匹配最早支出，不新增自动抵扣。用户选择原收支和金额；支持部分、多笔匹配，匹配合计可以小于付款金额，界面明确显示未匹配金额。混合代收与支出暂分别结算；不自动做净额抵扣。
6. 任一端 Transfer 不再为 `posted` 时，该匹配保留但不计有效结算；付款冲销恢复原收支未结。原收支冲销不再要求先冲销结算付款：付款事实保留，界面显示失效匹配与付款尚未有效匹配金额，由用户核对、更正。无级联冲销或自动恢复流程。
7. 提供创建付款并匹配、以及对已有付款追加匹配两个入口，复用同一个服务校验。错误匹配本轮沿用留痕冲销、重录处理，不新增匹配删除/改写接口。

## 文件职责与删除清单

| 文件 | 职责或处理方式 |
| --- | --- |
| `backend/infrastructure/models.py` | 两类账户、简化成员、Transfer 标签、结算匹配、保管关系及薄盘点外键 |
| `backend/infrastructure/store.py`、`stock_store.py`、`stocktake_store.py` | 按新字段读取账户、正式流水、盘点引用；删除旧垫付及 profile 查询 |
| `backend/infrastructure/settlement_store.py`（新增） | 匹配持久化、有效已结金额查询；无业务策略或独立提交 |
| `backend/application/members.py`（新增） | 从旧文件迁出必要成员目录，不自动建账户 |
| `backend/application/settlements.py`（新增） | 双向匹配校验、付款与匹配的事务编排、私账未结查询 |
| `backend/application/funds.py`、`catalogs.py`、`warehouse_catalogs.py` | 通用资金服务、账户维护、库存目录；删除垫付识别与类型推断 |
| `backend/application/warehouse.py`、`stock_queries.py`、`stock_workflows.py`、`stocktakes.py` | 自由货物转移、正式库存查询、钱货事务、薄盘点 |
| `backend/kernel/stock.py` | 整数数量与守恒；库存是否足够和外部边界准入迁到服务层 |
| `backend/entrypoints/schemas.py`、`http.py` | 新输入输出及结算入口，删除旧 claim/repayment 路由 |
| `frontend/src/api/*`、`App.vue`、现有目录/流水/库存/盘点组件 | 全部消费新契约，去掉旧垫付业务跳转和专用表单 |
| `frontend/src/components/AccountAvatar.vue`、`TagInput.vue`（新增） | 头像回退、预设和自定义标签的简单共用展示/输入 |
| `frontend/src/views/SettlementsView.vue`、`components/SettlementEditor.vue`、`api/settlements.ts`（新增） | 按私账查看支出报销、代收交回、已结与未结及付款匹配 |
| `frontend/src/views/MembersView.vue` | 收敛为成员资料与关联账户入口，不复制结算功能 |
| `backend/application/initialize.py`、开发种子、`tools/run_tests.sh`、测试夹具 | 新 schema、显式重建、简化测试入口 |

删除 `backend/application/member_claims.py`、`backend/modules/member_claims/`、`backend/infrastructure/stock_schema.py`、`frontend/src/api/memberClaims.ts`、`ClaimEditor.vue`、`RepaymentEditor.vue`。`StockAdjustmentEditor.vue` 的专用用途判断删除；保留必要原单预填并并入普通货物编辑器后删除该专用组件。

删除旧模型 `MemberClaim/Repayment/RepaymentAllocation/LocationProfile`，旧资金标记附表、`Member.account_id`、`custodian_label`、货物 `basis/action_kind/external_kind`、完成申请的 `basis`。不为被删行为新增证明删除的测试。

## 数据与接口契约

### 账户、流水与盘点

- 两类账户共用字段 `id/name/kind/member_id?/avatar_url?/tags/active`；账户 PATCH 不接受 `kind`，允许显式 `null` 清空联系人和头像。输出保留计算的资金余额、货物当前保管信息、盘点 metadata。
- `GET /api/accounts`、`GET /api/stock-accounts` 支持现有单标签过滤，并增加 `kind`、`member_id` 筛选；标签按完整字符串匹配。本轮不新增多标签 AND/OR 查询语言。
- 资金 Transfer 保留现有字段，增加 `tags`；货物 Transfer 用账户引用、`description/tags/source_reference/related_transfer_id` 和多 SKU 正整数明细。审批状态不变，完成输入只保留 `effective_date`。
- 原单关系只验存在且非自身。资金与货物都用现有专用引用字段表达关系，不建通用关联表。钱货复合输入收敛为 `{stock, money: TransferInput}`，事务内创建一条普通资金记录并关联货物；没有垫付子类型。
- 两类盘点沿用现有 API 与薄表，货物端点字段改为 `gain_account_id/loss_account_id`。所有专属账户是 `external`，标签可以预填但不决定归属。查询任一端涉及两个专属账户的全部状态记录；资金额外包括直接冲销记录。

### 双向结算

- `SettlementMatch` / `settlement_matches`：`settlement_transfer_id`、`item_transfer_id`、`amount_minor`；两 ID 联合主键，金额为正，均引用资金 Transfer。无单独状态、类型、成员或已结金额字段。
- `settlements.overview(db, account_id: str) -> dict`：返回 `{account, expenses, receipts, settlements}`。原收支行含 `transfer/settled_minor/outstanding_minor`；结算付款行含 `transfer/matched_minor/unmatched_minor/matches`，每个匹配含 `item_transfer_id/amount_minor/effective`。只针对私账，不由联系人推断归属。
- `GET /api/accounts/{id}/settlement-overview`：查询该私账的上述概览；普通有效登录用户可读。
- `POST /api/settlements`：输入 `{transfer: TransferInput, allocations:[{item_transfer_id,amount}]}`；可信用户调用，创建并正式过账普通付款，与匹配写入同一 HTTP 事务。返回付款详情及匹配；不存新的结算单。
- `POST /api/transfers/{id}/settlement-matches`：相同 `allocations`，向已过账付款追加匹配；至少一项、不重复既有配对、验证当前原收支和付款剩余额。记录一次服务层审计，不改正式流水。
- `settlements.create(db,user,data:dict) -> dict`、`settlements.add_matches(db,user,transfer_id:str,allocations:list[dict]) -> dict` 共享 `validate_matches(db, settlement, allocations)`，沿用传入事务和现有简单写锁。不新增预览版本、通用回调或业务类型注册器。
- 任一金额校验失败整体回滚；相关冲销影响有效匹配查询，匹配记录本身保留。普通 `funds.post` 不再查询匹配或垫付标记，不按业务限制冲销。

## 实施任务

### 任务 1：账户结构、成员与通用资金账本

**文件：** 模型、store、catalogs、members、funds、schemas、http、initialize；现有资金测试。

- [x] 建立两张账户表的共同字段与不可变类型，删除附表/profile 及旧垫付模型，避免留下指向退役表的外键；成员目录迁为 `members.py`，去掉自动建账和名称联动。同步移除旧 claim/repayment 路由及模块导入，任务 3 再清理其废弃源文件并提供新结算入口。
- [x] 资金余额统一借方减贷方，公账合计不包含私账或外部，也不因停用抹掉历史余额。
- [x] 删除资金提交、过账、冲销中的 claim/repayment 检查，保留通用权限、审批、版本、平衡分录与一次正式记账。
- [x] 账户创建验证联系人存在、名称非空；PATCH 明确可改字段与可清空字段。停用在新建时判断，处理已有转移不再拒绝。
- [x] 调整现有资金用例和公共夹具，覆盖私账 -300 经付款 +200 后为 -100、公账合计、类型改动拒绝、私账不绑成员、清空联系人。仅填补新行为覆盖缺口，不复制到多层。

**交付：** `/api/accounts` 和 `/api/stock-accounts` 的统一基础字段；普通资金收付、审批与冲销不依赖垫付系统。

### 任务 2：自由货物转移、保管与薄盘点

**文件：** warehouse、stock 查询/store、stock_workflows、stocktakes、kernel/stock、API；现有库存测试。

- [x] 改名账户引用和整数数量字段，删除用途枚举、匹配表及重复依据；Transfer 使用标签与可选说明，审批/执行快照同步新字段。
- [x] 关联仅检查原单存在与非自身；不限制原单状态、SKU、地点或用途。详情将 `adjustments` 改为中性 `related_transfers`。
- [x] 服务层保留库存不足、外部到外部禁止、权限和生命周期检查；数量内核仅验证数量事实。完成时不因账户/SKU 已停用拒绝旧单。
- [x] 保管历史改用货物账户外键，库存按公私账户查询；联系人筛选与保管人筛选分别命名，避免混用。
- [x] 钱货入口只创建普通资金 Transfer，保留原子提交和独立生命周期。
- [x] 盘点创建两外部账户，去掉动作预填；查询双方任意方向及所有状态，保留结束后可补录、默认隐藏和关联固定。
- [x] 调整现有库存用例：不同标签均可到货/出库；关联不同 SKU 或待批原单可用；审批不扣库存、完成只记一次；不足拒绝；停用后旧单可完成；盘点反向更正展示。删除旧用途/profile/claim 专有用例，保留有效权限和事务断言。

**交付：** 普通多 SKU Transfer 自由表达用途；库存、公私范围、保管历史和薄盘点仍可用。

### 任务 3：双向结算匹配

**文件：** settlement_store、settlements、models、schemas、http；`backend/tests/test_settlements.py` 替换旧 `test_member_claims.py`。

- [x] 实现契约中的匹配表、有效匹配求和、私账概览及两个写入口，不添加独立报销对象或认可标记。
- [x] 服务层按双方方向和具体私账判断报销/交回，检查已过账、金额、重复及两端剩余额。待审核收支不进入可结算范围。
- [x] 冲销后查询将对应匹配显示为失效；付款冲销恢复原收支未结，原收支冲销使有效付款显示未匹配金额，不自动冲销付款。
- [x] 复用现有 API 测试框架，集中覆盖两个真实闭环：支出 300/80/120，付款 400 匹配 300/80/20，再付 100；代收 200/300，交回 400 匹配 200/200，再交回 100。分别断言账户余额、每笔未结、匹配及付款只记一次。
- [x] 增补必要独立失败风险：未批/跨私账/超额匹配拒绝且事务不留下付款；相关冲销不重复计已结。复用夹具，不机械穷举组合。
- [x] 清理任务 1 已退役的旧垫付规则、源文件、接口和查询残留，修改测试入口，不为删除另建测试。

**交付：** 支出报销和代收交回共用金额匹配，未结与净余额均可追溯。

### 任务 4：前端按新模型收敛

**文件：** 前端 API、App、目录/成员/资金/货物/库存/盘点视图；新增头像、标签、结算组件，删除旧专用垫付组件。

- [x] 全部类型和请求切换新契约，不保留旧接口的兼容映射。目录与选择器按公账/私账/外部呈现，联系人可选、头像可改、编辑类型只读。
- [x] `TagInput` 提供固定常用项加可新增输入，去空白和重复；账户目录/选择器、Transfer 列表支持单标签筛选。`AccountAvatar` 图片失败或为空时取名称首字，使用现有 UI 样式，不做全站重设计。
- [x] 成员页只维护联系人资料和关联账户；增加按私账的结算页，两组原收支列表分别处理报销、交回，明确净余额、逐笔未结、付款未匹配金额和失效匹配。
- [x] 结算编辑器手动选择原记录与金额，提供新建付款或关联已有付款；不自动分配、不强制预览、不新增状态恢复逻辑。
- [x] 普通货物表单删用途下拉和依据，保留标签、一个说明及原单引用；完成只填日期。原单更正复用普通表单预填，不再有专用盈亏校验。
- [x] 盘点页与编辑器使用普通外部账户及标签预填，显示正反向记录；资金和货物查询仍标明账面及未估值。
- [x] 运行 `npm run build`；修复受改动影响的类型/构建问题。按需仅截图，不新增 UI 永久测试或自动交互。

**交付：** 旧“垫付申报/确认/偿还”入口消失，账户、普通转移和结算入口可表达已确认的业务。

### 任务 5：清理、集中验证与开发库重建

**文件：** initialize、store 重建入口、测试脚本/夹具、README、architecture、transfer-model、prototype-status。

- [x] 删除 `--initialize-stock-profiles`、`--simplify-stock-schema`、旧 schema 修补脚本及夹具的旧表逐条清理；初始化不迁移旧数据。
- [x] 显式 reset 用 SQLAlchemy 反射清除新旧 FGAS 应用表再按新 metadata 建表；包含已退役表，不能只 `drop_all` 新模型。限定项目表，不清理无关表，不增加长期迁移版本或兼容层。
- [x] 种子只初始化开发用户、公账资金池、普通外部账户和公账货物存放处；不自动创建成员私账或新业务流水。
- [x] 测试脚本先确认数据库名为 `fgas_test` 再重建测试应用表，集中运行保留/替换后的资金、结算、库存测试。修改完整后执行 `./tools/run_tests.sh` 与 `npm run build`，通过后不重复全量验证。
- [x] 搜索运行代码残留，核对旧字段、旧接口、旧模型无调用；检查 scope 未引入新恢复机制、规则引擎或清点明细。历史文档可保留旧名，但明确历史状态。
- [x] 更新 README 与架构中被新方案替代的当前说明；记录实际命令、结果、未验证项，不把历史测试结果当本轮验收。
- [x] 完成验证后停止开发应用，读取并确认配置目标是本项目开发库（不输出密钥），执行 `npm run dev -- --reset-db`；重建后用原启动方式运行并只做 `/api/health` 读检查。不请求重复重建授权，用户本轮已明确允许。

**交付：** 新旧废弃结构均清理，开发库为空账本并按新结构启动；不包含部署、正式 SSO、附件或备份恢复新增工作。

## 验证范围与计划自检

重点检查账户类型不可变、联系人可空、私账符号与公账合计、标签不影响准入、审批前不形成余额、结算不重复记钱、冲销后匹配失效、盘点反向记录，以及旧表被显式清理。行为验证优先集中在现有真实数据库/API 测试层，内核数学约束复用已有覆盖；不为同一故障重复搭层。

计划已对照构想检查：账户/标签/头像在任务 1 与 4，货物/关联/盘点在任务 2，双向结算在任务 3，数据重建和删除在任务 5。上述接口、字段和状态名称在各任务中一致。结算混合净额抵扣、匹配编辑、上传系统和正式部署均不属于本轮。

用户已确认并授权完整执行，任务已完成，验证与运行状态见 `docs/prototype-status.md`。实际 Git 目录为 `.fgas-git`，改动保存在 `feature/flexible-transfer-core`，保留了此前文档编辑，不重新初始化仓库。
