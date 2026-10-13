# Task4 report

Implemented linked transfer differences, ordinary stock adjustments, fund references and stock queries on f9da209. All counts remain integer strings; no quantity_scale or fractional support. No service launch, browser interaction, development database reset, subagents or architecture change.

## Responsibility and implementation

- `backend/infrastructure/models.py`: new StockDifference and StockDifferenceAdjustment tables. Difference holds original completed transfer/confirmation/line, physical location/SKU, expected/observed/delta integer counts, comparison time, basis, actor, original request and recording time. Unique completion+line+location and actor+idempotency key; nonzero delta constraint. Adjustment link uniquely identifies its ordinary StockTransfer.
- `backend/infrastructure/stock_store.py`: difference/link lookups and filtered stock transfer reads.
- `backend/application/stock_differences.py`: trusted-only difference registration, adjustment creation and post-completion fund linking; read snapshots. Uses warehouse authorization/advisory transaction lock, validator, approval and audit. Caller owns transaction. No funds posting. Adjustment's persisted link, quantity, SKU, physical endpoint, external boundary and sign are validated; no client/internal verified bool exists.
- `backend/application/warehouse.py`: common validator checks persisted adjustment basis; completion uses same validator and existing stock posting kernel. Transfer views include differences, adjustment origin, fund claim metadata and snapshot time. Detail/list/move reads pin repeatable-read read-only snapshot before all component reads. Historical move executor comes from immutable completed confirmation, separate from current custody.
- `backend/application/stock_queries.py`: single PostgreSQL CTE reads physical inventory, current member/custody, completed moves, persisted differences/current adjustment states and approved pending-completion planned quantities together. Inactive physical locations and SKUs remain in owned totals. External locations excluded. Exact numeric aggregates converted to Python integers before formatting; money unchanged.
- `backend/entrypoints/schemas.py` and `http.py`: strict inputs and endpoints below. Comparison time must include timezone.
- `backend/tests/test_stock_transfers.py`: three concise real PostgreSQL scenarios, reusing existing helpers. Existing rollback detail comparison ignores only new read snapshot timestamp; all prior business-field assertions retained.

## Application interfaces

`stock_differences.register_difference(db,user,transfer_id,data) -> Difference`
`stock_differences.create_adjustment(db,user,difference_id,data) -> StockTransfer`
`stock_differences.add_fund_reference(db,user,transfer_id,data) -> StockTransfer`
`stock_differences.list_differences(db,filters) -> list[Difference]`
`stock_differences.difference_detail(db,id) -> Difference`
`stock_queries.inventory(db,filters) -> InventorySnapshot`

Warehouse public lifecycle/completion signatures unchanged. `warehouse.list_transfers(db,status=None,filters=None)` and `warehouse.list_moves(db,filters=None)` accept optional metadata filters.

## HTTP handoff

- POST `/api/stock-transfers/{id}/differences` (201): `{line_id,location_id,observed_quantity,comparison_at,basis,idempotency_key}`. Requires completed original and its physical endpoint. Destination delta=observed-approved; source delta=approved-observed. observed zero permitted; delta zero rejected. It is a transfer-specific observation, never whole-warehouse count. Replay returns same Difference; different payload/same key or duplicate completion-line-location returns409.
- GET `/api/stock-differences?transfer_id=&location_id=&sku_id=`: array. GET `/api/stock-differences/{id}`: object. Each read includes snapshot_at.
- Difference shape: `{id,stock_transfer_id,confirmation_id,transfer_line_id,location_id,location_name,sku_id,sku_name,unit,expected_quantity,observed_quantity,delta,comparison_at,basis,actor_id,payload,created_at,status,adjustments:[{id,status,action_kind}]}`. Quantities/delta are integer strings; `status` is unresolved/adjusting/resolved, derived from current linked adjustment state. Original request remains payload; same completed difference cannot be overwritten.
- POST `/api/stock-differences/{id}/adjustment` (201): `{external_location_id,effective_date,basis,idempotency_key}`. Returns full ordinary StockTransfer in_transit with difference_id; lines quantity=abs(delta). Positive uses external adjustment_gain→physical; negative physical→external adjustment_loss. Requires another manual `/completion`, which uses existing warehouse ledger kernel. Effective pending/in_transit/completed adjustment blocks a new key409; rejected/cancelled adjustment frees another action. Replay of original action returns original adjustment, including after cancellation. Same key/different request409. Ordinary `/stock-transfers` still rejects forged adjustment actions or unsupported fields.
- POST `/api/stock-transfers/{id}/fund-references` (200): `{fund_transfer_id,idempotency_key}`. Trusted-only, existing fund business ID required404. Returns full transfer; completed records may receive references. Duplicate association leaves one join row; each independently keyed action is auditable. Same-key changed content409. No funds submission/post/claim confirmation/repayment allocation occurs.
- Transfer shape adds `snapshot_at`, `difference_id` (null for ordinary transfer), `differences:[Difference]`. Existing confirmations/audit/approval_snapshot/source_reference/immutable approved lines remain. `fund_references` now `{id,business_type,status,description,amount_minor,member_id,claim_id,reversal_of,claim:{id,member_id,declared_minor,confirmed_minor,basis}|null}`. business_type member_claim/repayment/fund_transfer. Status is current actual funds status including pending/posted/reversed; does not imply payment solely from association. Approval snapshot remains historical while live refs show current status.
- GET `/api/stock-transfers` retains status and adds action_kind/source_location_id/destination_location_id/sku_id filters. Array remains compatible.
- GET `/api/inventory?sku_id=&location_id=&member_id=`: `{snapshot_at,quantities:[{location_id,location_name,member_id,member_name,sku_id,sku_name,unit,quantity,valuation,differences:[{id,stock_transfer_id,delta,adjustment_id,adjustment_status,status}],in_transit_planned_quantity}],totals:[{sku_id,quantity,valuation}]}`. in_transit_planned_quantity sums approved, uncompleted incoming/outgoing plan quantities touching each selected position, never changes quantity/totals and never claims goods actually shipped. valuation remains 未估值. Rows include zero and inactive physical inventory. Filtered totals sum selected rows.
- GET `/api/stock-moves` retains array and accepts sku_id/source_location_id/destination_location_id/transfer_id. Adds sku_name/unit/source_location_name/destination_location_name/applicant_id/executor_id/stock_transfer_id/snapshot_at to existing move fields; integer quantity string. No mutation API.

## Real evidence and commands

New-table initialization only: explicit Unix-socket DATABASE_URL points at `fgas_test`, AUTH_MODE=development, FGAS_TEST_DATABASE=1, `.venv/bin/python -m backend.application.initialize` exit0. No existing schema alteration/rebuild. Full runner subsequently checks and prints current_database==fgas_test before initialization/test execution.

Targeted new scenarios:
`AUTH_MODE=development DATABASE_URL="postgresql+psycopg2://fgas@/fgas_test?host=$PWD/.runtime&port=55438" FGAS_TEST_DATABASE=1 .venv/bin/python -m pytest backend/tests/test_stock_transfers.py -k 'difference or under_shipped or fund_references' -q`
```
3 passed, 6 deselected in 2.86s
```

Full suite once:
`./tools/run_tests.sh`
```
Test database: fgas_test
...................                                                      [100%]
19 passed in 9.31s
```

After small metadata/filter/DB snapshot timestamp refinements, stock-only relevant suite:
`AUTH_MODE=development DATABASE_URL="postgresql+psycopg2://fgas@/fgas_test?host=$PWD/.runtime&port=55438" FGAS_TEST_DATABASE=1 .venv/bin/python -m pytest backend/tests/test_stock_transfers.py -q`
```
9 passed in 5.74s
```

Final `git diff --check` exit0, no output. `.venv/bin/python -m compileall -q backend/application/warehouse.py backend/application/stock_differences.py backend/application/stock_queries.py backend/infrastructure/models.py backend/infrastructure/stock_store.py backend/entrypoints/http.py backend/entrypoints/schemas.py backend/tests/test_stock_transfers.py` exit0, no output.

Behavior evidence: approved30 completed then destination -2 adjustment gives A70/B28/total98. Independent source+2/destination-2 gives A72/B28/total100. Registration before completion, foreign/external endpoint and duplicate difference reject. Wrong external adjustment kind rejects with no effective adjustment; untrusted writes403. Cancelled adjustment can retry new action; active/completed cannot duplicate; completion replay only one posting. Current custody changes from old to new member with B28 moving between filtered member summaries; historical executor stays trusted. Confirmed1000 claim with actual100 repayment linked to two completed receipts keeps funds summary, full member debt/claims view, individual claim detail and repayment matching exactly unchanged; duplicate refs one association, unknown refs404; repayment then claim reversal preserve refs showing reversed, inventory20 unchanged. Existing cancellation invalidation, completion refusal/reapplication, insufficient multiSKU and induced second-move rollback/concurrency scenarios remain passing and exercise reused posting path.

## Self-review and limits

Reviewed trusted identity refresh before all writes, replay before lifecycle restrictions, persisted adjustment validation, sign/direction/quantity, original observation vs immutable approval, one effective adjustment under shared lock, public input forgery rejection, transaction rollback, integer aggregates, no money calls, inactive physical inclusion and consistency snapshot boundaries. No new valuation, partial transfer, virtual warehouse, balance storage or complex corrections.

No UI/browser verification (backend scope). No production/development migration performed. New tables created through existing initialize/create_all; deployments must initialize them before new APIs. Adjustment-active uniqueness across relationship/status tables uses the existing global transaction lock plus persisted link (not a new cross-table DB trigger); all supported adjustment writes acquire that lock. Inventory currently shows combined incoming/outgoing planned quantity per physical position; UI must label it as plan, never add to owned totals. Full suite was run once; final metadata refinements were then covered by the complete stock test file, not another unrelated funds/member suite.
