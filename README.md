# FGAS funds prototype

FastAPI / PostgreSQL development shell for one organization, CNY. `backend/kernel` contains pure amount and balanced-line rules; `modules/funds` builds transfer plans; `application` owns approval, transactions and posting; `infrastructure` owns SQLAlchemy persistence; `entrypoints` exposes HTTP. Stock locations are a directory only.

## Local development

```bash
python -m venv --system-site-packages .venv
.venv/bin/pip install -r backend/requirements.txt
scripts/local-db.sh
scripts/run-backend.sh
```

The local script creates an isolated `.runtime/postgres` cluster with trust authentication bound to loopback port 55432. Never use that cluster as a public database. API runs at http://127.0.0.1:8000; OpenAPI is `/docs`. Vite should proxy `/api` to that address so the HTTP-only SameSite cookie remains same-origin. Set `DATABASE_URL` to use another PostgreSQL instance. Initialization seeds three identities (`admin`, `trusted`, `untrusted`), sample endpoints (`opening`, `bank`, `cash`, `income`, `expense`) and a location; balances start at zero. `INITIAL_ADMIN_ID` / `INITIAL_ADMIN_NAME` configure the initial administrator. Existing roles are preserved on restart.

`AUTH_MODE=development` must be explicit for application startup and initialization. This prototype has no production authentication adapter; other modes fail startup. Development login chooses a persisted active identity, with roles resolved from the database. It is intended for isolated development only. `deploy/compose.yaml` provides a clean development installation (`POSTGRES_PASSWORD` required); it does not turn this identity adapter into production authentication.

If a sandbox permits Unix sockets but denies TCP, start PostgreSQL with `pg_ctl -D .runtime/postgres -o '-h "" -k ABSOLUTE_SOCKET_DIRECTORY -p 55438' start` and use `postgresql+psycopg2://fgas@/fgas?host=ABSOLUTE_SOCKET_DIRECTORY&port=55438`. Both server and client need socket permission.

## HTTP contract

All business routes require the cookie session. Public development identity routes: `GET /api/auth/users`, `POST /api/auth/login {user_id}`, `POST /api/auth/logout`; `GET /api/auth/me` returns the persisted identity. Admin-only `GET /api/users` and `PATCH /api/users/{id} {role?,active?}` manage existing users.

- `GET /api/accounts?tag=...` returns `{id,name,kind,tags,is_fund,balance_minor}`. Trusted/admin `POST /api/accounts {name,kind,tags?,is_fund?}` and `PATCH /api/accounts/{id} {name?,tags?}` maintain endpoints. Fund endpoints must be asset accounts.
- `GET /api/locations?tag=...` returns `{id,name,custodian_label,tags}`. Trusted/admin create or patch the same fields. There are no stock quantities.
- `POST /api/transfers/preview` accepts `{source_account_id,destination_account_id,amount,effective_date,description?,counterparty?}`. `amount` is a decimal yuan **string** with at most two decimals; `effective_date` is ISO date. Preview shows amount in fen and proposed journal lines.
- `POST /api/transfers` adds `idempotency_key`. Trusted/admin posts automatically; untrusted submits `pending` with no journal. Same actor/key and identical canonical payload returns the same operation; different payload returns 409.
- `GET /api/transfers?status=...`, `GET /api/transfers/{id}` return endpoint IDs/names, amount_minor, date, status, version, actor and approval identities, reversal link/reason. Detail additionally includes `journal_lines` and `audit`.
- Trusted/admin `POST /api/transfers/{id}/approve {expected_version}` or `/reject {expected_version,reason}` handles pending content; stale versions return 409.
- `POST /api/transfers/{id}/reverse {reason,idempotency_key}` creates a linked reverse transfer using the original effective date. Untrusted reversal waits for approval; original becomes `reversed` only when reversal posts. A pending/posted reversal blocks another; rejected reversal permits a new request.
- `GET /api/funds/summary` returns `{accounts,total_minor,currency}` from fund journal balances. Opening is ordinary `opening -> bank/cash` transfer. No balance editing, negative-funds restriction, journal editing or deleting exists.

Formal posting serializes through one PostgreSQL transaction advisory lock and commits journal, state and audit together. Debit-minus-credit balances normalize to the normal side for each kind; only fund accounts contribute to cash totals. There is no pagination, reconciliation, attachment, inventory, member claims, SSO or password system in this increment.

## Verification

Tests clear all application rows: use a **dedicated test database** and migrate it first.

```bash
export DATABASE_URL='postgresql+psycopg2://fgas@127.0.0.1:55432/fgas_test'
export AUTH_MODE=development
.venv/bin/python -m alembic upgrade head
FGAS_TEST_DATABASE=1 .venv/bin/python -m pytest backend/tests/test_funds.py -q
```

Four real PostgreSQL scenarios cover balances and reversal, pending approval and role restrictions, idempotency/precision, and rollback under an induced PostgreSQL journal trigger failure. No browser interaction tests.
