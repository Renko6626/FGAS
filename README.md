# FGAS funds and stock prototype

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

Run `npm run build` at the root for TypeScript validation and a production frontend build. Development account selection, fund book balances, member claims/repayments, catalogues, stock transfers, manual completion, linked differences, inventory queries and approval queues are available on this feature branch. A failed transfer submission retains its payload and idempotency key for retry while the same account/editor is active; check records before retrying an uncertain outcome. Reloading the page or switching identity clears that in-memory draft.

## HTTP contract

All business routes require the cookie session. Public development identity routes: `GET /api/auth/users`, `POST /api/auth/login {user_id}`, `POST /api/auth/logout`; `GET /api/auth/me` returns the persisted identity. Admin-only `GET /api/users` and `PATCH /api/users/{id} {role?,active?}` manage existing users.

- `GET /api/accounts?tag=...` returns `{id,name,kind,tags,is_fund,balance_minor}`. Trusted/admin `POST /api/accounts {name,kind,tags?,is_fund?}` and `PATCH /api/accounts/{id} {name?,tags?}` maintain endpoints. Fund endpoints must be asset accounts.
- `GET /api/locations?tag=...` returns directory fields plus `kind`, `external_kind`, `active` and current member custody. Trusted/admin create or patch locations; `POST /api/locations/{id}/custody {member_id}` changes current custody (null clears it), retaining previous intervals. `kind` is `physical|external`; external kinds are `supplier`, `customer`, `opening`, `loss`, `adjustment_gain`, `adjustment_loss`. Legacy custody text does not automatically match a Member.
- `POST /api/transfers/preview` accepts `{source_account_id,destination_account_id,amount,effective_date,description?,counterparty?}`. `amount` is a decimal yuan **string** with at most two decimals; `effective_date` is ISO date. Preview shows amount in fen and proposed journal lines.
- `POST /api/transfers` adds `idempotency_key`. Trusted/admin posts automatically; untrusted submits `pending` with no journal. Same actor/key and identical canonical payload returns the same operation; different payload returns 409.
- `GET /api/transfers?status=...`, `GET /api/transfers/{id}` return endpoint IDs/names, amount_minor, date, status, version, actor and approval identities, reversal link/reason. Detail additionally includes `journal_lines` and `audit`.
- Trusted/admin `POST /api/transfers/{id}/approve {expected_version}` or `/reject {expected_version,reason}` handles pending content; stale versions return 409.
- `POST /api/transfers/{id}/reverse {reason,idempotency_key}` creates a linked reverse transfer using the original effective date. Untrusted reversal waits for approval; original becomes `reversed` only when reversal posts. A pending/posted reversal blocks another; rejected reversal permits a new request.
- `GET /api/funds/summary` returns `{accounts,total_minor,currency}` from fund journal balances. Opening is ordinary `opening -> fund_pool` transfer. No balance editing, negative-funds restriction, journal editing or deleting exists.

Formal posting serializes through one PostgreSQL transaction advisory lock and commits journal, state and audit together. Debit-minus-credit balances normalize to the normal side for each kind; only fund accounts contribute to cash totals. There is no pagination, attachment upload, production SSO or password system. Member claims, repayment matching and the inventory quantity ledger are implemented; full reconciliation and complex historical corrections remain outside this increment.

## Member claims and repayments

All authenticated active identities may read members and their histories. Only trusted/admin identities create or edit members, declare/confirm/reject claims, preview/submit repayments, or reverse marked operations. A business member is independent of a login user and has a stable non-fund liability account. Basis is text or a document number; files are not uploaded.

- `GET/POST /api/members` lists or creates `{name,note?}`; `PATCH /api/members/{id}` accepts `{name?,note?}` without changing its account identity.
- `GET /api/members/{id}` returns `member`, `pending_minor`, `confirmed_minor`, `repaid_minor`, `outstanding_minor`, `ledger_balance_minor`, `other_movements_minor`, `claims`, `repayments`, and actual `other_transfers` references from one consistent read snapshot.
- `GET /api/member-claims?member_id=&status=` and `GET /api/member-claims/{id}` return declared/confirmed amounts, basis/reason, status/version, effective repayments, outstanding and the linked transfer.
- `POST /api/member-claims` accepts `{member_id,destination_account_id,amount,effective_date,description?,basis,confirm_now,idempotency_key,confirmed_amount?,confirmation_reason?}`. Amounts are yuan strings. Pending declarations have no journal; `confirm_now=false` forbids confirmation fields. Immediate confirmation defaults to full amount. Partial recognition requires a reason and cannot exceed the declaration.
- `POST /api/member-claims/{id}/confirm` accepts `{expected_version,confirmed_amount,confirmation_reason?}`; `/reject` accepts `{expected_version,reason}`. Ordinary transfer approval cannot confirm an unconfirmed claim. The original declaration and request remain immutable after confirmation.
- `POST /api/repayments/preview` accepts `{member_id,source_account_id,amount,effective_date,description?,basis,allocation_mode,allocations?}`. The source must be an organization fund account; destination is derived from the member. `oldest_first` orders by confirmation time then ID; `manual` uses `{claim_id,amount}` items. Preview saves nothing and returns visible `{claim_id,amount,expected_version}` allocations plus journal lines.
- `POST /api/repayments` sends the original payment input, `idempotency_key`, and the exact preview allocations including versions. A stale or changed match returns 409 and requires a new preview; it never silently reallocates. `GET /api/repayments?member_id=` and `GET /api/repayments/{id}` return matches, effective status and linked transfer/reversal history.
- Transfer detail includes nullable `business:{kind:'member_claim'|'repayment',id,member_id}`; a reversing transfer references the original business. Existing `/reverse {reason,idempotency_key}` remains the entrypoint. Effective repayments and pending linked repayment reversals block claim reversal. Reverse repayments first to restore outstanding; allocations remain historical. Reversing a marked reversal itself is rejected.

The same actor/key with the same original request returns the saved operation even after confirmation, payment or reversal changes current state; changed input conflicts. An uncertain UI submission retains its exact payload/key for retry: check saved records first. Claim 400/422 rejection permits correction with a new attempt; uncertain results retain the attempt unless explicitly confirmed unsaved. Repayment matching conflicts require repreview. Identity changes clear in-memory drafts.

For example, create member A, then submit `{"member_id":"<A>","destination_account_id":"expense","amount":"1000.00","effective_date":"2026-10-13","basis":"采购单 001","confirm_now":true,"idempotency_key":"claim-expense-001"}`. This debits expense and credits A's liability; the organization's pool is unchanged. With opening funds of 2,000 yuan, repayment preview for A from `fund_pool` of `"400.00"`, basis `"偿还单 001"`, mode `"oldest_first"`, followed by submit with its exact allocations/key leaves funds 1,600 and that claim outstanding 600 yuan. These are expected behaviors implemented in code, not executed acceptance results here.

The same claim input with destination `"fund_pool"` and a new key increases organization funds by 1,000 yuan and creates A's outstanding claim of 1,000. Any distinct legal account may be a destination, including another member; non-fund balances follow their account's debit/credit convention. There is no expense whitelist. A subsequent ordinary unmarked `fund_pool -> A.account_id` transfer of 100 changes A's ledger balance to 900 but leaves claim outstanding 1,000, with other movements -100. `ledger_balance_minor = outstanding_minor + other_movements_minor`; other movements are independently read from real journal references. A marked A-to-B claim belongs to A; B sees its debit as other movement, with no automatic B claim or repayment. Generic member transfers never auto-match.

## Verification

Tests clear application rows and require the dedicated `fgas_test` database. The runner checks `SELECT current_database()` before initialization and executes the funds, member-claim and stock cases:

```bash
./tools/run_tests.sh
```

Final inventory consolidation on 2026-10-13: `./tools/run_tests.sh` verified `fgas_test`, exit 0, **23 passed in 11.76s**. Frontend compilation evidence from Task 6 (`037cc98`): `npm run build` in `frontend`, vue-tsc and Vite passed, 2,691 modules, 5.73s. Documentation changes do not repeat that unchanged build. These checks are not browser acceptance; no screenshots, interactive flows, services or deployment were performed for the stock increment.


## 当前服务器试用

原型已在 FGAS 根目录安装依赖，并配置忽略提交的 `.env`。PostgreSQL 使用根目录 `.runtime` 的 Unix socket，端口 55438；这只是本机开发环境。根目录运行 `npm run dev` 同时启动 FastAPI（8000）和 Vue（5173）。开发账户选择器提供管理员、受信任用户和不受信任用户。

资金初始余额为零。可以选择“期初权益”端点转入“社团资金池”，再录入收支和转账。资金账户与库存位置目录支持标签；根目录当前运行的旧资金原型尚未接入此隔离分支的数量账；库存实现位于 `feature/stock-transfers`，未合并、部署或改动根目录开发数据库。成员垫付与逐笔偿还匹配已实现，相关真实 PostgreSQL 测试通过。

本环境的 `.git` 目录只读，Git 元数据实际保存在 `.fgas-git`。在根目录查看版本可用 `git --git-dir=.fgas-git --work-tree=. status`。公开仓库为 [Renko6626/FGAS](https://github.com/Renko6626/FGAS)，成员增量通过 PR 交付；尚未部署。普通可写环境中的 Git 不需要这个额外路径。

2026-10-12 检查点验证包括四个真实 PostgreSQL 行为用例、前端类型检查与构建、开发服务健康检查；这些是旧检查点证据，不代表成员增量验收。没有执行浏览器自动点击、填表或端到端交互验收；Compose 安装与正式身份认证尚未验证。

阶段交付范围、检查点及下一步见 [阶段记录](docs/prototype-status.md)。

## Stock transfers and quantity inventory

All stock quantities are ASCII integer strings: positive line quantities up to `9007199254740991`, nonnegative observations including `"0"`; decimals (`"1.0"` included), scientific notation, signs and `quantity_scale` are rejected. Unit names are display labels; money retains yuan strings and integer fen. Each batch is an independent multi-SKU Transfer. There is no parent batch, partial execution, reservation or valuation.

Trusted/admin submissions enter `in_transit`; untrusted submissions enter `pending`. Approval changes no inventory. Every transfer requires a separate whole-transfer completion: trusted/admin completes explicitly, untrusted creates a completion request for trusted/admin approval. Physical source sufficiency is checked under the transaction lock for all lines; moves, completion and audit commit together. `in_transit` means approved and not completed, without proving physical dispatch. External endpoints do not enter organizational quantity totals.

- `GET/POST /api/skus`, `PATCH /api/skus/{id}` maintain name, specification, unit and active state. A referenced unit or location boundary cannot be reinterpreted through catalogue edits; inactive objects remain in history.
- `POST /api/stock-transfers` accepts `{source_location_id,destination_location_id,action_kind,effective_date,description?,basis,source_reference?,fund_transfer_ids?,lines:[{sku_id,quantity}],idempotency_key}`. Actions are `opening`, `arrival`, `sale`, `gift`, `loss`, `return`, `internal`; endpoints must match the action direction. Adjustment actions are server-created through differences. Duplicate SKU lines reject.
- `GET /api/stock-transfers?status=&action_kind=&source_location_id=&destination_location_id=&sku_id=` and `GET /api/stock-transfers/{id}` show current status, approved snapshot, confirmations, differences, funds references and audit.
- `POST /api/stock-transfers/{id}/approve|reject|cancel` uses expected content/execution versions and an optional idempotency key; reject/cancel also require a reason. Completed records cannot be cancelled.
- `POST /api/stock-transfers/{id}/completion` accepts `{expected_content_version,expected_execution_version,effective_date,basis,idempotency_key,observations?:[{line_id,observed_quantity,basis}]}`. Missing observations differ from zero; they never replace approved quantities or automatically create adjustments. `POST /api/stock-confirmations/{id}/approve|reject` uses current transfer versions returned after the request was created and an optional idempotency key. Reject requires a reason. Cancellation invalidates pending confirmations; rejected confirmation permits a new request.
- Trusted/admin `POST /api/stock-transfers/{id}/differences` accepts `{line_id,location_id,observed_quantity,comparison_at,basis,idempotency_key}` for a completed transfer's physical endpoint; comparison time requires a timezone. This compares one transfer line, not the whole warehouse. Destination delta is observed minus approved; source delta is approved minus observed. Nonzero differences are immutable and readable via `GET /api/stock-differences?transfer_id=&location_id=&sku_id=` and `GET /api/stock-differences/{id}`.
- Trusted/admin `POST /api/stock-differences/{id}/adjustment {external_location_id,effective_date,basis,idempotency_key}` creates an ordinary in-transit Transfer for the absolute delta. Gain uses external-to-physical, loss physical-to-external. It needs its own manual completion. An effective adjustment blocks another; rejected/cancelled adjustments permit a new keyed action, while old-key replay returns the original action.
- Trusted/admin `POST /api/stock-transfers/{id}/fund-references {fund_transfer_id,idempotency_key}` links an existing funds record even after completion, without another payment, claim or cost allocation. Multiple batches may reference the same payment or claim; current money status is displayed independently.
- `GET /api/inventory?sku_id=&location_id=&member_id=` returns `snapshot_at`, physical-location quantities/current member custody/known differences, planned uncompleted involvement and filtered SKU totals. Planned involvement never adds to stock. `GET /api/stock-moves?sku_id=&source_location_id=&destination_location_id=&transfer_id=` returns immutable moves and original applicant/executor. Coherent read snapshots preserve quantity/custody/status consistency; no balance-edit or move-delete API exists.

`POST /api/stock-operations` creates new money and stock together: `{stock:StockTransferInput,money:{kind:'fund_transfer'|'member_claim',data:Submit|ClaimSubmit},idempotency_key}` returns `{stock_transfer,fund_transfer,claim?}`. Both nested request keys remain required, alongside the outer key. Existing `fund_transfer_ids` cannot accompany new money. The whole request snapshot is idempotent; a failed money or stock write rolls everything back. Money follows existing funds/claims permissions and posting rules; stock remains pending or in transit until manual completion. Untrusted ordinary money and stock approvals remain independent; claims stay trusted-only. Stock cancellation does not refund money, and funds reversal does not cancel stock.

For old directory locations, explicitly bootstrap profiles using the intended configured development database, preserving existing records and custody text:

```bash
AUTH_MODE=development .venv/bin/python -m backend.application.initialize --initialize-stock-profiles
```

This non-reset command adds missing physical profiles and reports affected IDs; ordinary initialization does not assign profiles or match members. Verify `DATABASE_URL` before running it. No development bootstrap or reset was executed during this stock delivery.

Uncertain UI requests retain their exact payload, path, versions and keys in the active identity's in-memory session; query saved records and replay the same request. Full page reload loses that cache; identity switch clears it. There is no stock-operation lookup endpoint, automatic compensation, full-warehouse count workflow or complex historical correction interface. Real returns use a new Transfer; recorded differences use linked adjustments, never direct balance edits. Runtime UI behavior remains unverified. See [stage status](docs/prototype-status.md) and [implementation plan](docs/superpowers/plans/2026-10-13-stock-transfers-plan.md).
