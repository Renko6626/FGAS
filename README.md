# FGAS funds and stock prototype

## 最顶层产品原则：Transfer 是第一公民

使用者始终围绕一个心智模型记录业务：**我的钱从哪里去了哪里，我的货从哪里去了哪里，多少，何时发生，依据什么。** 系统让每个人能看清发生了什么、记录为什么会产生这样的结果，降低理解和操作的负担。这个原则优先指导业务入口、页面表达、数据模型和后续功能设计。

采购、销售、赠送、垫付、偿还和盘点都围绕具体 Transfer 展开。快捷入口可以预填来源与去向、提供必要的业务标记和校验，但提交前必须让用户看清并确认实际端点、金额或数量以及账面影响。上层业务不能用打包流程隐藏这些变化，也不能为同一事实另建独立业务实体或另一套账本。

资金和货物允许按实际发生时间分别记录，再建立必要关系。垫付标记、偿还匹配和薄盘点记录服务于 Transfer 的解释、约束和组织。页面应说明端点性质及生效时点，让用户理解费用科目、虚拟盈亏端点和真实位置的含义，以及批准与实际完成的区别。

日常操作说明见 [以 Transfer 为中心的操作模型](docs/transfer-model.md)，详细设计见 [架构文档](architecture.md)。

FastAPI / PostgreSQL development shell for one organization, CNY. `backend/kernel` contains pure amount and balanced-line rules; `modules/funds` builds transfer plans; `application` owns approval, transactions and posting; `infrastructure/store.py` owns transaction boundaries, PostgreSQL locking, ORM persistence and query execution; `application/identity.py` and `application/catalogs.py` own identity and directory operations; `entrypoints` exposes HTTP and delegates to application functions. `kernel/stock` validates integer quantities; `modules/warehouse` builds whole-transfer moves; warehouse application services own stock approval, manual completion, differences and queries. `stock_workflows` combines new money and stock in one creation transaction while retaining their independent lifecycles.

## Local development

```bash
python -m venv --system-site-packages .venv
.venv/bin/pip install -r backend/requirements.txt
scripts/local-db.sh
scripts/run-backend.sh
```

The local script creates an isolated `.runtime/postgres` cluster with trust authentication bound to loopback port 55432. Never use that cluster as a public database. API runs at http://127.0.0.1:8000; OpenAPI is `/docs`. Vite should proxy `/api` to that address so the HTTP-only SameSite cookie remains same-origin. Set `DATABASE_URL` to use another PostgreSQL instance. Initialization seeds three identities (`admin`, `trusted`, `untrusted`), default endpoints (`fund_pool` 社团资金池, `income` 其它收入, `expense` 其它费用, `opening` 期初权益) and a location; balances start at zero. `INITIAL_ADMIN_ID` / `INITIAL_ADMIN_NAME` configure the initial administrator. Existing roles and records are preserved on restart. Schema tables are created directly from the persistence models during development; formal deployment migrations are postponed.

社团资金池表示组织拥有的资金，与银行、支付平台或经手人无关，不包含成员私人资金。“其它收入”和“其它费用”是兜底分类；需要更明确的分类或资金端点时，由用户创建。

`AUTH_MODE=development` must be explicit for application startup and initialization. This prototype has no production authentication adapter; other modes fail startup. Development login chooses a persisted active identity, with roles resolved from the database. It is intended for isolated development only. `deploy/compose.yaml` provides a clean development installation (`POSTGRES_PASSWORD` required); it does not turn this identity adapter into production authentication.

The DB script accepts `FGAS_PG_PORT`, `FGAS_PG_SOCKET` (absolute path), and `FGAS_PG_HOST`; empty `FGAS_PG_HOST` disables TCP. Set `DATABASE_URL` consistently for backend startup. Only one process namespace should own cluster start/stop. If a sandbox permits Unix sockets but denies TCP, start PostgreSQL with `pg_ctl -D .runtime/postgres -o '-h "" -k ABSOLUTE_SOCKET_DIRECTORY -p 55438' start` and use `postgresql+psycopg2://fgas@/fgas?host=ABSOLUTE_SOCKET_DIRECTORY&port=55438`. Both server and client need socket permission.

## Frontend development

Use Node.js 22 or newer. Install the approved Vue 3 / TypeScript / Vite / Naive UI shell and start both processes from the repository root:

```bash
cd frontend
npm install
cd ..
npm run dev
```

Prepare PostgreSQL separately before starting. The root launcher loads an existing `.env`, forwards `DATABASE_URL`, `AUTH_MODE` and `API_PORT`, and terminates its backend/frontend process groups on interruption. It does not manage PostgreSQL. Frontend: http://localhost:5173; API defaults to http://127.0.0.1:8000. Set `VITE_API_PROXY_TARGET` if the API uses another address. The browser calls same-origin `/api` through Vite, including the session cookie. `scripts/run-frontend.sh` starts only Vite; export the proxy setting when using this separate command.

To discard local development data, stop the app and run `npm run dev -- --reset-db` with `AUTH_MODE=development` in `.env`. It drops only configured FGAS application tables, recreates them and seeds defaults, then exits without starting the servers. Normal `npm run dev` does not reset data. This command does not manage PostgreSQL or remove other databases.

Run `npm run build` at the root for TypeScript validation and a production frontend build. Development account selection, fund book balances, member claims/repayments, catalogues, stock transfers, manual completion, linked differences, inventory queries and approval queues are available on this feature branch. Fund transfer, claim declaration/confirmation, repayment and reversal editors use only in-flight busy flags and ordinary error messages. They do not retain failed requests or keys for replay and do not freeze forms after failure. Check saved records after an uncertain failure; repayment submission requires a new preview after any failure. Duplicate records may be rejected before approval or corrected by a reversal after posting.

## HTTP contract

All business routes require the cookie session. Public development identity routes: `GET /api/auth/users`, `POST /api/auth/login {user_id}`, `POST /api/auth/logout`; `GET /api/auth/me` returns the persisted identity. Admin-only `GET /api/users` and `PATCH /api/users/{id} {role?,active?}` manage existing users.

- `GET /api/accounts?tag=...` returns `{id,name,kind,tags,is_fund,balance_minor}`. Trusted/admin `POST /api/accounts {name,kind,tags?,is_fund?}` and `PATCH /api/accounts/{id} {name?,tags?}` maintain endpoints. Fund endpoints must be asset accounts.
- `GET /api/locations?tag=...` returns directory fields plus `kind`, `external_kind`, `active` and current member custody. Trusted/admin create or patch locations; `POST /api/locations/{id}/custody {member_id}` changes current custody (null clears it), retaining previous intervals. `kind` is `physical|external`; external kinds are `supplier`, `customer`, `opening`, `loss`, `adjustment_gain`, `adjustment_loss`. Legacy custody text does not automatically match a Member.
- `POST /api/transfers/preview` accepts `{source_account_id,destination_account_id,amount,effective_date,description?,counterparty?}`. `amount` is a decimal yuan **string** with at most two decimals; `effective_date` is ISO date. Preview shows amount in fen and proposed journal lines.
- `POST /api/transfers` accepts the same fields as preview. Trusted/admin posts automatically; untrusted submits `pending` with no journal. Each successful submission creates an independent record; there is no request-key deduplication or replay.
- `GET /api/transfers?status=...`, `GET /api/transfers/{id}` return endpoint IDs/names, amount_minor, date, status, version, actor and approval identities, reversal link/reason. Detail additionally includes `journal_lines` and `audit`.
- Trusted/admin `POST /api/transfers/{id}/approve {expected_version}` or `/reject {expected_version,reason}` handles pending content; stale versions return 409.
- `POST /api/transfers/{id}/reverse {reason}` creates a linked reverse transfer using the original effective date. Untrusted reversal waits for approval; original becomes `reversed` only when reversal posts. A pending/posted reversal blocks another; rejected reversal permits a new request.
- `GET /api/funds/summary` returns `{accounts,total_minor,currency}` from fund journal balances. Opening is ordinary `opening -> fund_pool` transfer. No balance editing, negative-funds restriction, journal editing or deleting exists.

Formal posting serializes through one PostgreSQL transaction advisory lock and commits journal, state and audit together. Debit-minus-credit balances normalize to the normal side for each kind; only fund accounts contribute to cash totals. There is no pagination, attachment upload, production SSO or password system. Member claims, repayment matching and the inventory quantity ledger are implemented; full reconciliation and complex historical corrections remain outside this increment.

## Member claims and repayments

All authenticated active identities may read members and their histories. Only trusted/admin identities create or edit members, declare/confirm/reject claims, preview/submit repayments, or reverse marked operations. A business member is independent of a login user and has a stable non-fund liability account. Basis is text or a document number; files are not uploaded.

- `GET/POST /api/members` lists or creates `{name,note?}`; `PATCH /api/members/{id}` accepts `{name?,note?}` without changing its account identity.
- `GET /api/members/{id}` returns `member`, `pending_minor`, `confirmed_minor`, `repaid_minor`, `outstanding_minor`, `ledger_balance_minor`, `other_movements_minor`, `claims`, `repayments`, and actual `other_transfers` references from one consistent read snapshot.
- `GET /api/member-claims?member_id=&status=` and `GET /api/member-claims/{id}` return declared/confirmed amounts, basis/reason, status/version, effective repayments, outstanding and the linked transfer.
- `POST /api/member-claims` accepts `{member_id,destination_account_id,amount,effective_date,description?,basis,confirm_now,confirmed_amount?,confirmation_reason?}`. Amounts are yuan strings. Pending declarations have no journal; `confirm_now=false` forbids confirmation fields. Immediate confirmation defaults to full amount. Partial recognition requires a reason and cannot exceed the declaration.
- `POST /api/member-claims/{id}/confirm` accepts `{expected_version,confirmed_amount,confirmation_reason?}`; `/reject` accepts `{expected_version,reason}`. Ordinary transfer approval cannot confirm an unconfirmed claim. The original declared amount remains recorded after confirmation; complete request payloads are not stored.
- `POST /api/repayments/preview` accepts `{member_id,source_account_id,amount,effective_date,description?,basis,allocation_mode,allocations?}`. The source must be an organization fund account; destination is derived from the member. `oldest_first` orders by confirmation time then ID; `manual` uses `{claim_id,amount}` items. Preview saves nothing and returns visible `{claim_id,amount,expected_version}` allocations plus journal lines.
- `POST /api/repayments` sends the payment input and the exact preview allocations including versions. A stale or changed match returns 409 and requires a new preview; it never silently reallocates. `GET /api/repayments?member_id=` and `GET /api/repayments/{id}` return matches, effective status and linked transfer/reversal history.
- Transfer detail includes nullable `business:{kind:'member_claim'|'repayment',id,member_id}`; a reversing transfer references the original business. Existing `/reverse {reason}` remains the entrypoint. Effective repayments block claim reversal. Reverse repayments first to restore outstanding; allocations remain historical. Reversing a marked reversal itself is rejected.

Requests are not cached or replayed. A failed repayment submission leaves the form editable and requires a new preview. Claim declaration, confirmation and reversal failures also leave forms editable; query saved records before submitting again when the outcome is uncertain. Backend version, status and amount checks remain, and all writes for one HTTP request commit or roll back together. Repayment creation checks the exact preview before saving; posting validates actual saved allocations against current outstanding claims. Independent duplicate entries can be rejected before approval or corrected through the existing reversal flow. New schemas omit the retired request-key and payload columns. This early-development change does not provide a funds schema migration or reset existing databases.

For example, create member A, then submit `{"member_id":"<A>","destination_account_id":"expense","amount":"1000.00","effective_date":"2026-10-13","basis":"采购单 001","confirm_now":true}`. This debits expense and credits A's liability; the organization's pool is unchanged. With opening funds of 2,000 yuan, repayment preview for A from `fund_pool` of `"400.00"`, basis `"偿还单 001"`, mode `"oldest_first"`, followed by submit with its exact allocations leaves funds 1,600 and that claim outstanding 600 yuan. These are expected behaviors implemented in code, not executed acceptance results here.

The same claim input with destination `"fund_pool"` increases organization funds by 1,000 yuan and creates A's outstanding claim of 1,000. Any distinct legal account may be a destination, including another member; non-fund balances follow their account's debit/credit convention. There is no expense whitelist. A subsequent ordinary unmarked `fund_pool -> A.account_id` transfer of 100 changes A's ledger balance to 900 but leaves claim outstanding 1,000, with other movements -100. `ledger_balance_minor = outstanding_minor + other_movements_minor`; other movements are independently read from real journal references. A marked A-to-B claim belongs to A; B sees its debit as other movement, with no automatic B claim or repayment. Generic member transfers never auto-match.

## Verification

Tests clear application rows and require the dedicated `fgas_test` database. The runner checks `SELECT current_database()` before initialization and executes the funds, member-claim and stock cases:

```bash
./tools/run_tests.sh
```

Final inventory consolidation on 2026-10-13: `./tools/run_tests.sh` verified `fgas_test`, exit 0, **23 passed in 11.76s**. Frontend compilation evidence from Task 6 (`037cc98`): `npm run build` in `frontend`, vue-tsc and Vite passed, 2,691 modules, 5.73s. Documentation changes do not repeat that unchanged build. These checks are not browser acceptance; no screenshots, interactive flows, services or deployment were performed for the stock increment.


## 早期服务器试用记录（2026-10-12）

原型已在 FGAS 根目录安装依赖，并配置忽略提交的 `.env`。PostgreSQL 使用根目录 `.runtime` 的 Unix socket，端口 55438；这只是本机开发环境。根目录运行 `npm run dev` 同时启动 FastAPI（8000）和 Vue（5173）。开发账户选择器提供管理员、受信任用户和不受信任用户。

资金初始余额为零。可以选择“期初权益”端点转入“社团资金池”，再录入收支和转账。资金账户与库存位置目录支持标签；根目录当前运行的旧资金原型尚未接入此隔离分支的数量账；库存实现位于 `feature/stock-transfers`，未合并、部署或改动根目录开发数据库。成员垫付与逐笔偿还匹配已实现，相关真实 PostgreSQL 测试通过。

本环境的 `.git` 目录只读，Git 元数据实际保存在 `.fgas-git`。在根目录查看版本可用 `git --git-dir=.fgas-git --work-tree=. status`。公开仓库为 [Renko6626/FGAS](https://github.com/Renko6626/FGAS)，成员增量通过 PR 交付；尚未部署。普通可写环境中的 Git 不需要这个额外路径。

2026-10-12 检查点验证包括四个真实 PostgreSQL 行为用例、前端类型检查与构建、开发服务健康检查；这些是旧检查点证据，不代表成员增量验收。没有执行浏览器自动点击、填表或端到端交互验收；Compose 安装与正式身份认证尚未验证。

阶段交付范围、检查点及下一步见 [阶段记录](docs/prototype-status.md)。

## Stock transfers and quantity inventory

All stock quantities are positive ASCII integer strings up to `9007199254740991`. Decimals, signs, scientific notation and `quantity_scale` are rejected. Money retains the existing yuan/fen rules. Each batch is an independent multi-SKU Transfer; there is no parent batch, partial execution, reservation or valuation.

Trusted/admin creation or approval only reaches `in_transit`. Every transfer needs separate manual completion before it affects inventory. Untrusted completion requests still require trusted approval. Cancellation has no stock effect and invalidates pending completion requests; completed facts remain recorded. A failed multi-line write rolls back the whole HTTP transaction. Current state, permissions and quantities are checked under the existing simple serial write lock. One transfer line can produce only one formal StockMove.

Current API:

- `GET/POST /api/skus`, `PATCH /api/skus/{id}` manage SKU metadata. Referenced units cannot be changed.
- `GET/POST /api/locations`, `PATCH /api/locations/{id}` manage physical or external locations; `POST /api/locations/{id}/custody {member_id}` retains current member custody/history.
- `POST /api/stock-transfers` accepts `{source_location_id,destination_location_id,action_kind,effective_date,description?,basis,source_reference?,related_transfer_id?,fund_transfer_ids?,lines:[{sku_id,quantity}]}`. There is no stock idempotency key or content/execution version.
- `GET /api/stock-transfers` and `GET /api/stock-transfers/{id}` expose ordinary status, lines, confirmations, fund references, audit and directly related adjustment transfers. `related_transfer_id` identifies the original completed transfer.
- `POST /api/stock-transfers/{id}/approve {}`; reject/cancel use `{reason}`. Completed records cannot be cancelled.
- `POST /api/stock-transfers/{id}/completion {effective_date,basis}`; `POST /api/stock-confirmations/{id}/approve {}` or reject `{reason}`. A rejected confirmation permits a new application.
- Gain/loss is a normal `POST /api/stock-transfers`, using `adjustment_gain` (gain boundary to physical location) or `adjustment_loss` (physical location to loss boundary), positive quantity, reason and optional original-transfer relation. When related, the physical location and SKU belong to that original completed transfer. It needs its own approval/manual completion. No separate difference registration, adjustment-generation or difference-resolution API remains.
- `POST /api/stock-transfers/{id}/fund-references {fund_transfer_id}` links existing money without another payment, claim or cost allocation. Repeated associations remain one link.
- `GET /api/inventory?sku_id=&location_id=&member_id=` returns physical quantities, custody, planned uncompleted involvement and filtered SKU totals. Planned quantity never adds to stock. `GET /api/stock-moves` exposes formal movements and their completion/transfer references.
- `POST /api/stock-operations {stock,money}` creates money and stock in the same HTTP transaction, returning `{stock_transfer,fund_transfer,claim?}`. Money is `{kind:"fund_transfer",data:<existing Submit>}` or `{kind:"member_claim",data:<existing ClaimSubmit>}`; money uses the same key-free input as its standalone endpoint. There is no outer operation key, replay table, generated child-key allocation or extra savepoint. Each successful composite submission creates new money and stock records; it does not deduplicate repeated input. Existing fund references cannot accompany new money. Money follows its amount, permission and posting rules; stock stays pending/in transit, and later cancellation/reversal affects each side independently.

For databases created before this simplification, configure the intended database and explicitly run:

```bash
AUTH_MODE=development .venv/bin/python -m backend.application.initialize --simplify-stock-schema
```

This compatibility step adds the original-transfer relation, backfills old adjustment links and makes retired request/version fields optional. Existing historical values and retired difference/replay tables remain; active code no longer reads or writes them. Fresh schemas do not create the retired models. This is not a database reset and is not automatic at startup.

Old directory locations still need explicit physical profile bootstrap if they lack one:

```bash
AUTH_MODE=development .venv/bin/python -m backend.application.initialize --initialize-stock-profiles
```

The command creates missing schema/development defaults and adds missing physical profiles while preserving custody text. Ordinary initialization does not assign profiles or match members. Neither compatibility nor profile bootstrap was run against the development database during this change.

UI writes retain only a busy flag, an error message and normal refresh. There is no frozen request, retry cache, conflict acknowledgement or cross-form recovery lock. After a network error, query saved records first. Independently duplicated stock entries can be corrected with a new transfer or a linked gain/loss entry with a reason; automatic detection/compensation is not provided. A complete historical correction or full-warehouse count workflow remains outside this delivery. Runtime UI behavior has not been browser-tested. See [stage status](docs/prototype-status.md), [deletion record](docs/stock-operation-simplification.md) and [current plan](docs/superpowers/plans/2026-10-13-stock-minimal-plan.md).


## 阶段盘点

资金与货物盘点实现提交 `1ba8bf0` 已阶段性合并到 `main`，尚未部署。实际薄表为 `fund_stocktakes` 和 `stock_stocktakes`；盘点只保存名称、说明、状态、创建信息及专属盈亏端点，不改变账面金额或数量。盘点页复用原 Transfer 列表与编辑器，正式变化仍经原审批、过账或手动完成流程。

active 登录用户可读，受信任用户和管理员可创建、修改说明及结束。`/api/fund-stocktakes` 和 `/api/stock-stocktakes` 各提供 GET 列表（可选 `status`）、POST 创建、GET `/{id}` 详情、PATCH `/{id}` 说明和 POST `/{id}/end`。详情返回 `{stocktake,transfers}`；资金查询包含原记录的冲销，结束后新记录仍可查。

账户和位置目录保留全部端点，附加可空 `stocktake:{id,name,status}`。结束只让选择器默认隐藏专属端点，可打开“显示已结束盘点端点”，已有选择保留；不关闭普通 Transfer 业务。名称和端点关联固定，不提供删除、重开或重新绑定。

新增两表沿用现有初始化的 SQLAlchemy metadata 建表，无需重置数据；本轮没有对日常数据库执行初始化或兼容命令。2026-10-14 在隔离工作树运行 `./tools/run_tests.sh`：确认 `Test database: fgas_test`，退出 0，25 passed in 11.65s；根目录 `npm run build` 退出 0，vue-tsc 与 Vite 成功（2,696 modules，5.52s）。未进行截图、浏览器交互、服务启动或部署验收。
