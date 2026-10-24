# Structure cleanup implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development and dispatching-parallel-agents. The user explicitly requested concurrent subagents; disjoint file ownership takes precedence over serial implementation. Work in the existing clean checkout; no branch integration or publication is requested.

**Goal:** Implement all seven structural improvements accepted in the preceding review without changing product behavior.

**Architecture:** Keep the existing modular monolith and Vue application. Move misplaced responsibilities to existing layers, extract focused Vue components/composables, and share existing simple logic only.

**Tech Stack:** Existing FastAPI / SQLAlchemy / PostgreSQL and Vue 3 / TypeScript / Naive UI.

**Spec:** The seven findings and recommended directions in the preceding project review, explicitly accepted by the user on 2026-10-24.

## Global Constraints

- Preserve HTTP/MCP contracts, authorization semantics, accounting and stock invariants, interface appearance and user flows.
- No dependencies, database changes, retries, queues, recovery mechanisms, new permission framework, or deployment changes.
- User AGENTS.md testing rules supersede blanket TDD: reuse existing tests for behavior-preserving refactors; add permanent tests only for a concrete uncovered behavior.
- Tests only use fgas_test. Root alone runs database tests after integration; workers must not concurrently reset the shared test database.
- Frontend validation is TypeScript + production build; no browser clicks/forms.
- Workers are not alone in the checkout: preserve others' edits, stay within ownership, do not commit or spawn agents, report new architectural decisions instead of implementing them.

## Review Focus

- Login/logout/session expiry must preserve clearing and identity epoch semantics.
- Standalone paged transfer lists and embedded stocktake lists must preserve filters, details, and action refresh behavior.
- Trusted/admin/ordinary user and Agent low/high checks must remain equivalent.
- Directory assembly must preserve intentional HTTP/MCP field differences and patch/null behavior.
- Inventory filters, historical basis, pagination and totals must remain unchanged.

### Task 1: Backend responsibilities

**Ownership:** backend/application and backend/infrastructure; no entrypoint/test edits without coordination.

- [x] Centralize existing trusted-user write authorization without creating a policy framework; eliminate duplicated directory checks and business-module dependencies for generic authorization.
- [x] Move inventory SQL/execution to infrastructure; retain application formatting/condition semantics.
- [x] Reuse directory base assembly for human and Agent readers, explicitly preserving their existing output fields.
- [x] Review changed callers and Python syntax; report changed files and evidence. Root runs the existing backend suite.

### Task 2: Frontend API and app responsibilities

**Ownership:** frontend/src/api, frontend/src/App.vue, new app/session/workspace composables; do not edit existing components or views.

- [x] Format and separate funds.ts responsibilities into domain API/type modules; keep temporary backwards-compatible exports until root migrates all remaining imports.
- [x] Extract session handling, common state clearing and workspace data loading from App.vue; keep navigation/local modal state in the shell as appropriate.
- [x] Preserve current import consumers, contract types, identity epochs and refresh semantics; no new state library.
- [x] Report new preferred imports, changed files and validation. Root runs the integrated frontend build.

### Task 3: Frontend record components and repeated logic

**Ownership:** frontend/src/components, frontend/src/views/TransfersView.vue, StockTransfersView.vue, StocktakesView.vue, new record/search/filter composables. Do not edit App.vue or api modules.

- [x] Separate reusable transfer record rendering/details/actions from standalone list fetching. Stocktakes should reuse record components instead of whole page views; eliminate local/remote dual mode from page views.
- [x] Keep ordinary list and approval filters/pagination and stocktake embedded behavior equivalent; preserve all detail/action capabilities.
- [x] Share duplicated fund-transfer option search/cache/debounce between stock editor and stock record detail; keep single/multiple selection rendering appropriate to each consumer.
- [x] Share existing account filtering where genuinely identical between TransferEditor and EndpointSelector without changing their UIs.
- [x] Report files and integration interfaces; root runs integrated build.

### Task 4: Integration and verification (root)

- [x] Review all task diffs against the seven findings, migrate remaining imports to correct frontend domains and remove obsolete compatibility exports where possible.
- [x] Update architecture navigation to reflect actual changed responsibilities.
- [x] Run ./tools/run_tests.sh against fgas_test, npm run build and git diff --check once the integrated changes are ready.
- [x] Obtain independent review of the resulting changes; fix concrete regressions and run only affected checks after fixes.
- [x] Report actual outcomes and any unverified items; leave changes reviewable in the workspace.

## Execution evidence

- Task 1 independently reviewed: spec and quality PASS; no concrete findings. Report: `/tmp/fgas-backend-review.md`.
- `./tools/run_tests.sh`: confirmed `fgas_test`, 64 passed in 30.23s (2026-10-24). No backend changes after this run.
- Task 2 implementation, import integration and independent review completed.
- Task 2 independently reviewed: spec and quality PASS; no concrete findings.
- Frontend final integration review found one P3 stale detail-error banner. Both record components now clear it when new items arrive; scoped independent re-review PASS, no remaining findings.
- First integrated `npm run build`: TypeScript and Vite PASS; Vite reports a >500 kB bundle warning.
- Final affected `npm run build` after the banner fix: TypeScript and Vite PASS (5.80s Vite build); >500 kB bundle warning remains informational.
- Final `git diff --check`, new-file whitespace check and static lower-layer reverse-import check: PASS.
- No dependencies, schema changes, deployment, browser interactions or permanent tests added. Changes remain in the current workspace for review.
