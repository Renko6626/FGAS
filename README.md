# FGAS funds prototype

FastAPI / PostgreSQL development shell for one organization, CNY. `backend/kernel` contains pure amount and balanced-line rules; `modules/funds` builds transfer plans; `application` owns approval, transactions and posting; `infrastructure/store.py` owns transaction boundaries, PostgreSQL locking, ORM persistence and query execution; `application/identity.py` and `application/catalogs.py` own identity and directory operations; `entrypoints` exposes HTTP and delegates to application functions. Stock locations are a directory only.

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

Run `npm run build` at the root for TypeScript validation and a production frontend build. Development account selection, fund book balances, catalogs, transfer preview/submission, records/details/reversal, approval and persisted user roles are available. A failed transfer submission retains its payload and idempotency key for retry while the same account/editor is active; check records before retrying an uncertain outcome. Reloading the page or switching identity clears that in-memory draft.

## HTTP contract

All business routes require the cookie session. Public development identity routes: `GET /api/auth/users`, `POST /api/auth/login {user_id}`, `POST /api/auth/logout`; `GET /api/auth/me` returns the persisted identity. Admin-only `GET /api/users` and `PATCH /api/users/{id} {role?,active?}` manage existing users.

- `GET /api/accounts?tag=...` returns `{id,name,kind,tags,is_fund,balance_minor}`. Trusted/admin `POST /api/accounts {name,kind,tags?,is_fund?}` and `PATCH /api/accounts/{id} {name?,tags?}` maintain endpoints. Fund endpoints must be asset accounts.
- `GET /api/locations?tag=...` returns `{id,name,custodian_label,tags}`. Trusted/admin create or patch the same fields. There are no stock quantities.
- `POST /api/transfers/preview` accepts `{source_account_id,destination_account_id,amount,effective_date,description?,counterparty?}`. `amount` is a decimal yuan **string** with at most two decimals; `effective_date` is ISO date. Preview shows amount in fen and proposed journal lines.
- `POST /api/transfers` adds `idempotency_key`. Trusted/admin posts automatically; untrusted submits `pending` with no journal. Same actor/key and identical canonical payload returns the same operation; different payload returns 409.
- `GET /api/transfers?status=...`, `GET /api/transfers/{id}` return endpoint IDs/names, amount_minor, date, status, version, actor and approval identities, reversal link/reason. Detail additionally includes `journal_lines` and `audit`.
- Trusted/admin `POST /api/transfers/{id}/approve {expected_version}` or `/reject {expected_version,reason}` handles pending content; stale versions return 409.
- `POST /api/transfers/{id}/reverse {reason,idempotency_key}` creates a linked reverse transfer using the original effective date. Untrusted reversal waits for approval; original becomes `reversed` only when reversal posts. A pending/posted reversal blocks another; rejected reversal permits a new request.
- `GET /api/funds/summary` returns `{accounts,total_minor,currency}` from fund journal balances. Opening is ordinary `opening -> fund_pool` transfer. No balance editing, negative-funds restriction, journal editing or deleting exists.

Formal posting serializes through one PostgreSQL transaction advisory lock and commits journal, state and audit together. Debit-minus-credit balances normalize to the normal side for each kind; only fund accounts contribute to cash totals. There is no pagination, reconciliation, attachment, inventory, member claims, SSO or password system in this increment.

## Verification

Tests clear all application rows: use a **dedicated test database** and initialize its schema first.

```bash
export DATABASE_URL='postgresql+psycopg2://fgas@127.0.0.1:55432/fgas_test'
export AUTH_MODE=development
.venv/bin/python -m backend.application.initialize
FGAS_TEST_DATABASE=1 .venv/bin/python -m pytest backend/tests/test_funds.py -q
```

Four real PostgreSQL scenarios cover balances and reversal, pending approval and role restrictions, idempotency/precision, and rollback under an induced PostgreSQL journal trigger failure. No browser interaction tests.


## 当前服务器试用

原型已在 FGAS 根目录安装依赖，并配置忽略提交的 `.env`。PostgreSQL 使用根目录 `.runtime` 的 Unix socket，端口 55438；这只是本机开发环境。根目录运行 `npm run dev` 同时启动 FastAPI（8000）和 Vue（5173）。开发账户选择器提供管理员、受信任用户和不受信任用户。

资金初始余额为零。可以选择“期初权益”端点转入“社团资金池”，再录入收支和转账。资金账户与库存位置目录支持标签；库存位置目前不提供数量账，垫付标记与逐笔偿还匹配仍属下一增量。

本环境的 `.git` 目录只读，Git 元数据实际保存在 `.fgas-git`。在根目录查看版本可用 `git --git-dir=.fgas-git --work-tree=. status`；当前代码已合回 `main`。普通可写环境中的 Git 不需要这个额外路径。

当前验证包括四个真实 PostgreSQL 行为用例、前端类型检查与构建、开发服务健康检查。没有执行浏览器自动点击、填表或端到端交互验收；Compose 安装与正式身份认证尚未验证。

阶段交付范围、检查点及下一步见 [阶段记录](docs/prototype-status.md)。
