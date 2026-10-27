# Task 2 report — backend business numbering

Status: DONE

Implemented the confirmed code-only contract inside the existing layers. Internal primary/foreign keys, journal and stock accounting, authorization, approval, settlement matching and reversal semantics remain in place. No new module boundary, allocation table, global numbering service, retry, recovery or migration revision was introduced. No frontend or benchmark files were changed.

## Numbering and database

- FundAccount `FA-0001`, StockAccount `SA-0001`, Member `M-0001`.
- Transfer `FT-000001`, StockTransfer `ST-000001`, StockConfirmation `SC-000001`.
- Each model has non-null unique `code` with a PostgreSQL server default using its own native sequence. Codes are automatically available after ORM flush; seed inserts use the same defaults. User-facing create/patch schemas do not allow editing these codes. SKU retains the existing manually maintained code.
- Padding is a minimum width; the existing migration test now exercises the 9999 → 10000 boundary and verifies `FA-10000` / `FA-10001` from direct ORM insertion. Gaps are allowed.
- Only the existing `0001_baseline_schema.py` was synchronized. Sequences are explicitly `OWNED BY` their corresponding code columns, so table reset and baseline downgrade remove exactly these six sequences. Existing repeated upgrade, model comparison and downgrade → upgrade checks pass.
- Authorized `fgas_test` backup supplied by parent: `/data/sunyunbo/www/FGAS/.runtime/backups/fgas_test-20261027T081518Z-pre-business-codes.dump`. All business-database execution used only the explicit `fgas_test` URL below. Migration checks created/deleted their existing isolated temporary databases. Daily `fgas` and `fgas_benchmark` were untouched.

## Final public contract for frontend / benchmark adaptation

Paths retain their existing resource names, but business `{identifier}` values are codes, not internal IDs. Authentication user/session/credential IDs and actor/approver/executor identifiers remain technical identifiers.

| Object / operation | Final fields |
| --- | --- |
| Fund and stock account directory rows | `code`, `name`, `kind`, `member_code`, `member_name`, `tags`, `active`; HTTP/saved rows retain `avatar_url`, `stocktake`; funds retain `balance_minor` |
| Account create/patch | `member_code` replaces `member_id`; auto account code is not an input |
| Account list filters | `member_code` replaces `member_id`; existing tag/kind/q/active behavior retained |
| Stock account responsibility history | `member_code`, `member_name`, validity timestamps and technical actor/ended_by fields; no independent custody-row ID |
| Member rows | `code`, `name`, `note`; edit path identifier is M code |
| SKU directory rows | `code`, `name`, `tags`, `unit`, `active`, plus existing HTTP/saved avatar; no internal SKU ID; editing still uses existing SKU code |
| Fund transfer rows/details | `code`, `source_account_code`, `destination_account_code`, `reversal_of_code`; all existing business amounts/dates/status/version/names/audit/source fields retained |
| Fund create/preview input | `source_account_code`, `destination_account_code`, existing amount/date/description/counterparty/tags |
| Fund journal and preview journal rows | `account_code`, `debit_minor`, `credit_minor` |
| Public funds summary | account rows expose `code`; existing `total_minor` and CNY semantics unchanged |
| Stock transfer rows/details | `code`, `source_account_code`, `destination_account_code`, `related_transfer_code`; existing business fields retained |
| Stock transfer input | `source_account_code`, `destination_account_code`, optional `related_transfer_code`, `fund_transfer_codes`; lines remain `{sku_code,quantity}` |
| Stock lines | `sku_code`, `sku_name`, `unit`, `quantity`; no line ID / SKU ID |
| Stock fund references | `code` (FT), `status`, `description`, `amount_minor`, `reversal_of_code`, `source_account_code`, `destination_account_code`; MCP retains its compact existing declared projection |
| Related stock transfers | `code` (ST), `status`, `source_account_code`, `destination_account_code`, lines `{sku_code,quantity}` |
| Completion request response | parent stock transfer detail plus `confirmation_code` |
| Nested confirmations | `code` (SC), `transfer_code` (parent ST), existing actor/date/status/approval/source fields |
| Completion actions | request uses parent ST identifier; approve/reject uses SC identifier |
| Stock audit detail | completion references use `confirmation_code`; added funding reference uses `fund_transfer_code`; no independent audit-row UUID |
| Add stock fund reference input | `fund_transfer_code` |
| Inventory rows | `account_code`, `member_code`, `sku_code`; remaining names/units/quantity/planned/valuation fields retained |
| Inventory totals | `{sku_code,quantity,valuation}` for the whole filtered result |
| Inventory filters | `account_code`, `member_code`, `sku_code`, existing as_of/basis |
| Stock move rows | `stock_transfer_code`, `confirmation_code`, `sku_code`, `source_account_code`, `destination_account_code`; dates/quantities/names/technical applicant/executor remain; no move/line/SKU UUID |
| Stock move filters | `transfer_code` (ST), `source_account_code`, `destination_account_code`, existing SKU/time filters |
| Settlement allocation input/result | `item_transfer_code` replaces `item_transfer_id`; amount/effective semantics unchanged |
| Settlement outstanding | `account_code`, `transfer_code`, `source_account_code`, `destination_account_code`; existing amounts/status classifications/names remain; filter uses `account_code` |
| Settlement overview MCP | `fgas_query({resource:'settlement_overview',identifier:'FA-…'})`; no filters.account_id/account_code form; HTTP account path uses FA |
| Dashboard | funds recent / stock recent / operations use `code`; reversal uses `reversal_of_code`; stock summaries and nested SKU lines use `sku_code` |
| MCP write result references | funds/settlement `transfer_code`; stock `stock_transfer_code`; completion `confirmation_code` + `stock_transfer_code`; saved account `account_code`, member `member_code`, SKU `sku_code`; nested objects expose own `code` |

Fund `q` now searches business code as well as existing names/description/counterparty/actor/tags. MCP fund/stock event filters expose `q`. Stock `q` includes original `source_reference`, and HTTP/MCP stock lists accept exact `source_reference` filtering. Multiple directory/list candidates remain lists.

Internal calls intentionally retain their IDs: reversal foreign keys, approval revalidation payloads, custody updates, stock-move writes, settlement indexes/joins, stocktake storage and persistence helpers. Boundary code resolution occurs in application services. The combined money/stock workflow passes the newly created FT code to the stock submission boundary.

Paused stocktakes remain paused. Their original identifiers are retained without adding numbering; dormant account creation resolves returned account code back to the existing internal account FK, and dormant endpoint projections use account codes.

## Changed files

- Application: `agent_operations.py`, `agent_queries.py`, `catalogs.py`, `dashboard.py`, `directory_views.py`, `funds.py`, `members.py`, `settlements.py`, `stock_queries.py`, `stock_workflows.py`, `stocktakes.py`, `warehouse.py`, `warehouse_catalogs.py`.
- Entrypoints: `agent_catalog.py`, `agent_schemas.py`, `http.py`, `schemas.py`.
- Infrastructure: `agent_store.py`, `dashboard_queries.py`, `models.py`, `stock_store.py`, `store.py`.
- Baseline: `backend/migrations/versions/0001_baseline_schema.py`.
- Existing tests and fixtures: `conftest.py`, funds/settlements/stock/agent/dashboard tests, and existing migration test.
- Help: `docs/ai/guide.md`, `docs/ai/overview.md`; historical client-trial records intentionally retain their historical evidence.

## Verification

Every database command used:

```bash
DATABASE_URL='postgresql+psycopg2://fgas@/fgas_test?host=/data/sunyunbo/www/FGAS/.runtime&port=55438' FGAS_TEST_DATABASE=1 AUTH_MODE=development
```

With those environment assignments:

- `.venv/bin/python -m backend.application.initialize --reset` — baseline initialization succeeded (the existing mechanism; no `--reset-db`).
- Focused existing five-file pytest pass initially found expected contract adaptations and a stock completion FK mapping mistake. Corrected; focused failed-case rerun reached 28 passed, with one remaining paused-stocktake test adaptation corrected afterward.
- `./tools/run_tests.sh` — **84 passed in 33.88s**, including dedicated test-database reset and real migration checks.
- After self-review narrowed stock funding references back to their original compact field set, `.venv/bin/python -m pytest backend/tests/test_stock_transfers.py::test_money_first_operation_and_independent_completion backend/tests/test_agent_access.py::test_high_direct_business_and_source backend/tests/test_agent_access.py::test_mcp_high_execution_uses_real_business_services -q --tb=short` — **3 passed in 2.11s**.
- `.venv/bin/python -m compileall -q backend` and `git diff --check` — both exited 0 after final cleanup.

No browser, frontend build, benchmark/model execution or production verification was performed. This deliberately changes the baseline and public contract at once; older databases are not upgraded or backfilled. Parent/frontend/benchmark work must consume the code contract before treating the integrated application as usable.
