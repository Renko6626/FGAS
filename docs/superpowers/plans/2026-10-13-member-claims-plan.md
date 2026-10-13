# 成员垫付与偿还 Implementation Plan

> **For agentic workers:** 执行时使用 `superpowers:executing-plans`；仅在用户选择逐任务委派时使用 `superpowers:subagent-driven-development`。按下列任务和复选框推进，遵守用户关于新增测试、架构确认和 UI 验证的约定。

**Goal:** 受信任用户能代录成员垫付、确认金额、记录部分或跨多笔偿还，并追溯每笔欠款与资金变化。

**Architecture:** 垫付和偿还都是现有 Transfer 的外层标记，共用资金分录、事务、幂等和冲销。垫付去向不增加类别限制；偿还是组织资金到成员往来。成员及匹配关系由外层模块维护，`backend/kernel/accounting.py` 不加入业务用途分支。

**Tech Stack:** 沿用 FastAPI / Pydantic、SQLAlchemy 2 / PostgreSQL、Vue 3 / TypeScript / Vite / Naive UI；不新增运行依赖。

**Spec:** [已确认设计](../specs/2026-10-13-member-claims-design.md)、[architecture.md](../../../architecture.md) 第 6 节、[总路线图](2026-10-12-part1-roadmap.md) 第 3 节。用户 2026-10-13 的去向不受限要求优先于此前草案。

**状态（2026-10-13）：** 设计与计划已确认；用户选择逐任务委派，gpt-6.1-sol low 开发、medium 审阅。任务 1–4 实现及逐任务审阅完成，任务 5 文档已更新，最终集中代码审阅已完成，所提代码修复已交付并通过定向复审。独立分支 `feature/member-claims` 未合并或部署；真实数据库检查受 socket 权限阻止，产品验收未完成。

## Global Constraints

- 单社团、人民币整数分；成员私人资金不计入组织资金。API 金额输入为十进制元字符串，沿用现有精度校验。
- 垫付和偿还仅为外层标记。**不限制垫付去向类别、不建立用途白名单、不按说明推断科目、不另建账本。**
- 普通成员端点转移不自动变成垫付或偿还，不自动抵销逐笔债务。核对必须能区分其账面影响。
- 业务成员独立于登录用户；不绑定账号。管理员、受信任用户办理本增量写操作，可确认自己代录的记录；原普通资金权限保持。
- 原始申报与确认金额分开保留。正式分录只追加与冲销；借款、备用金、代收款专门追踪、库存及正式认证不进入本增量。
- 原始事实、标记、匹配、状态和审计原子提交。继续使用现有数据库事务咨询锁，不引入后台过账。
- 开发 Schema 直接建表；本方案主要增加表，不自动清空开发库。任何必要的开发库清空另行说明并获授权。
- 保留已有有效断言；新增永久测试只填补本增量的行为缺口。UI 仅类型检查、构建及必要截图，不自动点击、填表或执行交互验收。
- 本机 Git 元数据在 `.fgas-git`，命令用 `git --git-dir=.fgas-git --work-tree=.`；执行前按 worktree 技能确认隔离位置，勿移动数据库、`.env` 或依赖目录。
- 每个任务在其相关检查通过后保存一次提交，仅包含该任务文件，提交信息说明可观察行为；遇到共享工作区修改时不得替他人暂存或撤销。

## Review Focus

- 把“费用样例”写成限制或硬编码“垫付不影响资金池”：任务 2 用成员转入资金池的真实分录覆盖。
- 申报部分认可后重试旧请求，恢复旧金额或重复记账：任务 2 核对原始请求、当前确认值和唯一转移。
- 预览后别的操作改变可偿还余额，重复扣款或无声改配：任务 3 在锁内验证版本与匹配，覆盖过期预览和竞争偿还。
- 普通批准／冲销跳过标记规则，或再次冲销冲销记录：任务 2、3 在已有入口执行或拒绝关联操作。
- 成员端点的普通转移或其他成员的垫付被误算成偿还：任务 3、4 对逐笔未结与全部往来分开核对。

## 文件与职责

| 文件 | 工作 |
| --- | --- |
| `backend/infrastructure/models.py` / `store.py` | 成员、标记、匹配映射及查询、写入；复用现有事务 |
| `backend/modules/member_claims/__init__.py` / `rules.py` | 本增量纯金额与匹配规则，不访问 ORM 或 HTTP |
| `backend/application/member_claims.py` | 成员和业务入口编排、预览及查询，调用已有资金提交路径 |
| `backend/application/funds.py` | 统一提交、批准、过账和冲销的标记校验及协调；不复制第二套 post |
| `backend/entrypoints/schemas.py` / `http.py` | 新输入模型及薄 HTTP 路由 |
| `frontend/src/api/memberClaims.ts` | 本增量类型和客户端调用 |
| `frontend/src/views/MembersView.vue` | 成员列表、未结总览与逐笔明细 |
| `frontend/src/components/ClaimEditor.vue` / `RepaymentEditor.vue` | 代录确认、偿还预览与提交；沿用已有组件风格 |
| `frontend/src/App.vue` / `views/TransfersView.vue` / `api/funds.ts` | 导航、标记明细关联和审批分流 |
| `backend/tests/conftest.py` / `test_member_claims.py` | 复用现有真实数据库夹具及新增关键行为场景 |
| `tools/run_tests.sh`、`README.md`、阶段记录与路线图 | 纳入回归及交付说明 |

应用依赖保持单向：`application/member_claims.py → application/funds.py → modules/member_claims/rules.py + infrastructure/store.py`；资金应用模块不反向导入成员应用模块。纯规则只接收明确数据，store 不作权限或业务决定。

## 数据及接口约定

新增 `Member(id, name, note, account_id)`，`account_id` 唯一，指向非资金负债科目。新增 `MemberClaim(transfer_id, member_id, declared_minor, confirmed_minor?, basis, confirmation_reason?, confirmed_at?)`、`Repayment(transfer_id, member_id, basis, allocation_mode)`、`RepaymentAllocation(repayment_id, claim_id, amount_minor)`。两个业务标记以 `transfer_id` 为主键，公开业务 ID 即资金转移 ID；分配对 `(repayment_id, claim_id)` 唯一且金额为正。状态和版本读取 Transfer，避免平行状态机。

申报额不可修改；确认额为空或 `0 < confirmed_minor <= declared_minor`。待确认记录无正式分录。偿还有效性以付款转移仍为 `posted` 判断，冲销不删除原标记和分配。每次有效偿还或偿还冲销后，递增涉及垫付的 Transfer.version 并记录关联审计，用于识别过期预览，不改其已确认金额。

通用资金原始 `payload` 保存完整请求及业务标记快照；确认后的当前金额存在转移和确认字段中，原始快照保持不变。同一操作者的幂等键跨普通转移、垫付、偿还共用已有唯一约束。

| 方法与路径 | 输入／输出关键约定 |
| --- | --- |
| `GET/POST /api/members` | 列表；创建 `{name,note?}`，返回成员及 `account_id` |
| `PATCH /api/members/{id}` | `{name?,note?}`；不修改关联科目身份，不提供删除 |
| `GET /api/members/{id}` | 成员、总览及按日期排序的垫付、偿还和其他往来引用 |
| `GET /api/member-claims?member_id=&status=` | 返回标记、原始申报、确认额、有效偿还、剩余、转移状态与版本 |
| `POST /api/member-claims` | `{member_id,destination_account_id,amount,effective_date,description?,basis,confirm_now,idempotency_key,confirmed_amount?,confirmation_reason?}`；`confirm_now=false` 时禁止携带确认内容，直接确认默认全额 |
| `POST /api/member-claims/{id}/confirm` | `{expected_version,confirmed_amount,confirmation_reason?}`；金额不一致须填原因 |
| `POST /api/member-claims/{id}/reject` | `{expected_version,reason}`；复用已有拒绝路径 |
| `POST /api/repayments/preview` | `{member_id,source_account_id,amount,effective_date,description?,basis,allocation_mode:'oldest_first'|'manual',allocations?}`；手动项为 `{claim_id,amount}` |
| `POST /api/repayments` | 上述付款内容、`idempotency_key` 和预览返回的明确 `allocations:[{claim_id,amount,expected_version}]` |
| `GET /api/repayments?member_id=`、`GET /api/repayments/{id}` | 付款、匹配、关联转移及冲销关系 |
| 现有 `GET /api/transfers/{id}` | 增加可空 `business:{kind:'member_claim'|'repayment',id,member_id}`，冲销记录还显示所关联的原业务 |
| 现有 `POST /api/transfers/{id}/reverse` | 复用原请求形状，增加关联标记校验与原子处理 |

成员总览金额字段固定为 `pending_minor`、`confirmed_minor`、`repaid_minor`、`outstanding_minor`、`ledger_balance_minor`、`other_movements_minor`。前四项只汇总本成员有效业务，`ledger_balance_minor = outstanding_minor + other_movements_minor`。其他往来由不属于该成员垫付／偿还（含对应反向转移）的正式分录汇总，不能把计算差额伪称为已定位的其他往来。总览金额使用单条 SQL 读取同一快照；详情逐笔数据如需拆查询，使用查询入口的只读一致快照，不改全局写事务隔离级别。

## Task 1：成员目录与统一提交的标记扩展

**Files:** `models.py`、`store.py`、`application/member_claims.py`、`application/funds.py`、`schemas.py`、`http.py`，均为上述完整路径。

**Interfaces:**
- `member_claims.create_member(db, user, data: dict) -> dict`、`update_member(db, user, identifier: str, data: dict) -> dict`、`list_members(db) -> list[dict]`。
- `funds.submit(db, user, data, reversal_of=None, reason=None, *, business: dict | None=None, defer_post: bool=False) -> Transfer`：保留原调用兼容；新参数仅由后端应用构造，普通 HTTP 输入不接受内部控制字段。
- `store.create_claim(db, values: dict) -> MemberClaim`、`create_repayment(db, values: dict, allocations: list[dict]) -> Repayment`、`get_claim(db, transfer_id: str)`、`get_repayment(db, transfer_id: str)`；读写都使用传入事务，不独立提交。

- [x] 新增四张表及真实外键、唯一和正金额约束；创建成员时在同一事务建立成员和非资金负债科目。无需改动现有表即可表达本增量。
- [x] 实现成员创建、修改和列表接口；写操作锁内刷新角色及 active，成员姓名和科目显示名称同步修改但 ID 不变。
- [x] 扩展唯一资金提交路径：锁内校验身份 → 完整原始快照去重 → 构造 Transfer → 保存外层标记及匹配 → 按权限和 `defer_post` 进入现有 post。重复请求必须先返回旧结果，不能先重建业务标记。
- [x] 新增内部参数不能让普通调用绕过权限；有 `business` 时仅允许可信角色，标记类型、成员与来源／去向关联在应用层核验，不信任前端构造。
- [ ] 运行现有 `./tools/run_tests.sh`，四个原用例应继续通过。该任务不为 CRUD 单独新增永久测试；后续业务用例通过真实成员创建入口覆盖它。

**实现目标（数据库行为待验）：** 已有资金行为保持；新标记能在正式分录写入前纳入同一事务，尚不对外宣称垫付闭环完成。

## Task 2：垫付申报、金额确认与未偿还冲销

**Files:** 新建 `modules/member_claims/rules.py`，修改成员和资金应用、持久化及 HTTP；新增 `tests/test_member_claims.py`，将现有 `client` 夹具原样移至 `tests/conftest.py` 供两文件共用，不复制测试设施。

**Interfaces:**
- `rules.validate_confirmation(declared_minor: int, confirmed_minor: int, reason: str) -> None`。
- `member_claims.submit_claim(db, user, data: dict) -> dict`、`confirm_claim(db, user, identifier: str, expected_version: int, confirmed_amount: str, reason: str='') -> dict`、`reject_claim(db, user, identifier: str, expected_version: int, reason: str) -> dict`。
- `member_claims.get_claim(db, identifier: str) -> dict`、`list_claims(db, member_id: str | None=None, status: str | None=None) -> list[dict]`。
- 新增 `funds.validate_business_post(db, item, user) -> None`，由唯一 `post` 调用，读取持久化标记并调用纯规则；不得以客户端提供的“已验证”布尔值替代。

- [x] 实现成员关联科目作为来源、用户选择任意合法端点作为去向的申报。先保存待确认转移和标记，再按 `confirm_now` 设置确认快照并调用统一 post；不在端点筛选或后端校验加入费用类型条件。
- [x] 待确认时申报额可查询且无分录；确认时锁内刷新角色和记录，校验版本、状态与金额，写确认额、原因、服务器确认时间及审计，更新当前转移金额并 post；原始请求快照不变。
- [x] 原普通 approve 遇到待确认垫付返回明确 409，指向垫付确认入口；拒绝可复用现有路径。详情返回业务关联，保证前端可正确分流。
- [x] 未偿还垫付冲销复用原 reverse → submit → post；先识别原记录及冲销链、校验可信角色和有效偿还，再原子记反向分录。拒绝再次冲销本业务的冲销记录。冲销请求重试先做原幂等判断，不因原状态已 reversed 错误拒绝同一请求。
- [x] 添加 `test_claim_confirmation_retry_and_reversal`：申报 1,000 待确认，确认 800、原因保存，费用去向下资金池不变、债务为 80,000 分；原提交重试返回同一记录且仍是确认 800；旧版本确认 409；普通 approve 不过账；冲销恢复零债务；对关联冲销再次冲销被拒绝。用同一场景检查不受信任写入 403。
- [x] 添加 `test_claim_destination_and_unmarked_member_transfer`：成员向资金池垫付 1,000 后资金池确实增加 100,000 分；再以普通转移从资金池向成员付 100，成员账面余额变为 90,000 分，原垫付未结仍为 100,000 分，无偿还匹配。另以合法非费用、非资金端点记录一笔转移，验证没有类别白名单。
- [x] 调整 `tools/run_tests.sh` 纳入两个测试文件。
- [ ] 执行数据库检查并确认通过：当前初始化阶段受 sandbox socket 权限拒绝，尚未执行。

**实现目标（数据库行为待验）：** 待确认与正式债务可区分，部分认可及重试可追溯；非费用去向和普通成员转移遵循统一记账原则。

## Task 3：偿还预览、逐笔匹配与关联冲销

**Files:** `rules.py`、成员／资金应用、models/store、schemas/http、`test_member_claims.py`。

**Interfaces:**
- 在 rules 定义只读输入 `OpenClaim(id: str, member_id: str, confirmed_at: datetime, version: int, outstanding_minor: int)`。
- `rules.allocate_oldest(claims: list[OpenClaim], amount_minor: int) -> list[tuple[str,int]]` 按确认时间、ID 排序。
- `rules.validate_allocations(claims: list[OpenClaim], member_id: str, amount_minor: int, allocations: list[tuple[str,int]]) -> None` 校验成员、重复项、正金额、合计和可偿还额。
- `member_claims.preview_repayment(db, user, data: dict) -> dict`、`submit_repayment(db, user, data: dict) -> dict`、`get_repayment(db, identifier: str) -> dict`、`list_repayments(db, member_id: str | None=None) -> list[dict]`。
- 预览输出 `{amount_minor,source_account_id,destination_account_id,allocation_mode,allocations:[{claim_id,amount,expected_version}],journal_lines}`，金额字符串用于原样提交、分用于展示。

- [x] 实现预览：显式选择组织资金账户作为来源、成员关联科目作为去向，按默认或手动规则给出可见分配；预览不保存付款、匹配或余额。
- [x] 实现提交：完整快照幂等检查后，锁内重新加载当前状态、版本和可偿还金额。默认模式与当前排序计算结果比较，不一致返回 409；手动模式核验所选项目及版本。不静默替换预览结果。
- [x] 通过任务 1 的共同 submit 保存付款和匹配，统一 post 再校验成员、金额及相关状态；自动批准只产生一份付款分录。提交成功后原子递增相关垫付版本，记录偿还引用。
- [x] 扩展 reverse：偿还冲销保留原匹配历史，取消其有效性，恢复对应垫付未结并递增版本；原冲销金额与原付款一致。有有效偿还或尚未完成的关联冲销时拒绝垫付冲销；不自动连带冲销其他记录。
- [x] 添加 `test_repayment_allocation_and_reversal`：期初 2,000、垫付 1,000、偿还 400，断言资金 160,000 分、未结与对应负债均 60,000 分；付款重试不重复。再加入一笔 300，偿还 700 默认分配 600 + 100，剩余 200；对未结笔作一次明确手动分配。检查跨成员、合计不符及超额拒绝；逐次冲销偿还后未结恢复，随后允许冲销垫付。
- [x] 添加 `test_stale_and_competing_repayments`：先预览，再完成另一笔偿还，旧版本提交 409；两独立数据库事务同时尝试清偿相同剩余金额，仅一份成功，另一份冲突，查询付款与未结总额证明未重复清偿。使用真实数据库连接及短屏障，不用 sleep 猜时序、不扩成压力测试。
- [x] 添加 `test_repayment_write_failure_rolls_back`：复用现有 PostgreSQL trigger 失败注入方式，在独立数据库中令 journal 写入失败，核对付款转移、偿还标记、匹配、审计及垫付版本均未部分提交；已有垫付保持。测试清理 trigger，不搭建通用故障框架。
- [ ] 执行 `./tools/run_tests.sh`，与改动相关的全部数据库用例通过后停止该轮验证。

**实现目标（数据库行为待验）：** 主例及跨多笔偿还成立；重试、过期预览、竞争和失败不会形成重复或部分付款；冲销能恢复对应未结。

## Task 4：成员总览与现有页面接入

**Files:** 成员应用及 store 的查询、HTTP，新增 `api/memberClaims.ts`、`views/MembersView.vue`、`components/ClaimEditor.vue`、`components/RepaymentEditor.vue`；修改 App、TransfersView、api/funds。

**Interfaces:**
- `member_claims.member_detail(db, identifier: str) -> dict` 返回成员、上文总览字段、claims、repayments、other_transfers。
- TypeScript 定义 `Member`、`Claim`、`Repayment`、`RepaymentPreview`、`MemberDetail` 与 HTTP 表一致；`membersApi` 方法与后端公开业务函数一一对应，复用 `api/client.ts` 的 request。
- 新编辑组件接收 `show`、`member`、`accounts`，发出 `close`、`saved`；偿还组件保存完整预览及重试键，成员、付款或分配改变后旧预览失效。

- [x] 实现成员列表和详情的稳定快照查询；逐笔状态由正式确认和有效匹配计算，未确认申报额单列，拒绝／冲销保留历史但不加入有效未结。
- [x] 将任务 2 的普通往来用例扩展到总览：资金池转入后的垫付未结 100,000、普通付款后其他往来 -10,000、全部余额 90,000 分；增加成员 A 向 B 的带标记转移，A 增加垫付未结，B 只增加其他往来影响。不能以净额替代逐笔欠款，也不能按今天的余额重算旧匹配。
- [x] 成员入口提供代录、待确认列表及确认金额、偿还预览、逐笔历史和关联资金详情。端点选择复用现有 EndpointSelector，垫付去向保留完整合法对象，不另做用途分类；成员来源由当前成员明确展示。
- [x] 现有审批列表中的带标记记录进入相应业务详情；普通批准不能绕过金额确认。现有冲销按钮复用服务端保护，页面解释需先处理关联偿还的拒绝原因。
- [x] UI 按角色隐藏本增量写入口，后端仍负责权限。切换登录身份清除编辑状态；失败保留完整载荷和幂等键；结果不确定时提示查询已存记录再重试，409 匹配冲突须重新预览。
- [x] 金额影响按实际端点显示，成员转入资金池时明确增加资金；不出现“任何垫付均不影响组织资金”的固定说明。全部往来余额与垫付未结并列命名，其他往来可追溯。
- [x] 根目录 `npm run build` 在任务 4 修复后通过；未截图或执行交互验收，未新增 UI 永久测试。
- [ ] 执行 `./tools/run_tests.sh`（含本任务新增核对断言）并确认通过；当前受 socket 权限阻止。

**完成证据：** 代录、确认、偿还、未结查询和资金追溯具备页面入口；构建通过只证明类型和打包，不声称交互验收完成。

## Task 5：集中审阅、文档与阶段交付

**Files:** 已改动文件、`README.md`、`docs/prototype-status.md`、`docs/superpowers/plans/2026-10-12-part1-roadmap.md` 和本计划。

- [x] 对照五项 Review Focus 完成集中审阅；锁后刷新 Transfer 的代码修复及旧会话批准／拒绝回归已交付，修复复审已通过，数据库验收仍未完成。
- [x] 更新状态、HTTP 契约及样例：同时说明费用去向主例和成员转入资金池样例；移除前端“债务跟踪尚未实现”等过期文案。
- [x] 标记真正完成的路线图项目；备用金、代收款、库存、正式认证、附件上传与恢复仍保持未完成。依据先使用文本或单据编号，不新建附件存储系统。
- [x] 汇总最后一次真实 `./tools/run_tests.sh`、`npm run build` 的命令和结果；仅有后续修改才重跑受影响检查。必要的健康检查单独记录，不与业务验收混为一谈。
- [x] 保存代码和文档检查点，报告未验证项；不包含 `.env`、开发数据库、运行会话和依赖，不自动部署或重置现有数据。

## 计划自检

- 已将用户的去向开放要求落实到 API、端点选择、分录影响及真实行为用例；未把费用样例变成规则。
- 成员与标记存储归任务 1，申报／确认／垫付冲销归任务 2，偿还／匹配／偿还冲销归任务 3，查询及 UI 归任务 4，文档与审阅归任务 5。
- 原有四个真实数据库用例保留；新增场景集中在同一测试文件，共用夹具，不跨层复制完整用例。
- 原始载荷和确认值分离，幂等先于当前状态拒绝；默认匹配在提交时核验，失败不默默改变付款意义。
- 所有新公开函数、端点及字段在上文定义；纯规则、应用及存储依赖方向固定。任务内的函数体、查询写法和 UI 排布由实施者沿用现有风格完成。
- 实现步骤完成不等于产品验收；数据库与 UI 行为尚未验证，最终集中代码审阅及所提修复已交付，修复复审已通过。

## 实施证据与剩余验收（2026-10-13）

任务 2 最近真实 `./tools/run_tests.sh` 退出 1，在初始化连接 PostgreSQL Unix socket 时 `Operation not permitted`；尚未执行测试，提权被自动拒绝。任务 4 `--collect-only` 收集 10 个测试（0.07s），compileall 成功；任务 4 修复后的最新 `npm run build` 成功（2678 modules，4.22s）。没有重复运行不变检查，没有截图或浏览器交互验收；历史 2026-10-12 四个通过用例不代表当前分支。实际数据库验收复选框继续保留未完成。

费用去向、成员转入资金池、普通往来与逐笔未结的区别、冲销约束、权限和重试说明见 [README](../../../README.md#member-claims-and-repayments)；交付状态见 [阶段记录](../../prototype-status.md)。备用金、代收款、库存、正式认证、附件上传和恢复继续不在本次交付内。
