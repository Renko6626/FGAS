# ERP Workspace Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the approved implementation. Implementation completed locally on 2026-11-09; not deployed.

**Goal:** Apply the approved compact ERP prototype with one consistent transfer-record view and prominent pending approvals.

**Architecture:** Keep Vue 3, Naive UI, existing hashes, composables and business components. Extract only the shared record presentation into a small view model and a presentation component; funding, stock, authorization and processing remain in their existing owners.

**Tech Stack:** Existing Vue 3, TypeScript, Vite, Naive UI and CSS. No dependencies or backend changes.

**Spec:** `docs/superpowers/specs/2026-11-09-erp-workspace-design.md`

## Global Constraints

- Preserve current uncommitted navigation/export work and use the existing `codex/navigation-shell` branch.
- Preserve business data, permissions, hash locations, approval/completion/reversal behavior and existing empty-state actions.
- Reuse existing formatting and data; no schema-driven table framework, new statistics, settings persistence or request recovery.
- Screenshot-only browser validation; no automated clicks, form filling or business flows.
- UI changes do not require new permanent tests. Complete the existing frontend build once after all tasks, plus affected rechecks only if something fails or changes.
- No deployment in this phase.

## Review Focus

- Fund rows, stock rows and mixed recent rows must preserve kind/code and open the correct existing record.
- Amount/quantity precedes the fixed source/arrow/destination tracks on desktop; mobile preserves direction, value and status.
- Pending, selected and keyboard-focused records must remain distinguishable; pending completion reports retain existing notes/actions.
- Long names and multiple SKUs remain readable without adding quantities across different units.
- Desktop sidebar collapse must not interfere with the mobile drawer, header offsets or keyboard access.

## Task 1: Shared transfer records

**Files and responsibility**

- Create `frontend/src/presentation/records.ts`: the minimal display-row type and projections from existing Transfer, StockTransfer and DashboardOperation data.
- Create `frontend/src/components/TransferRecordList.vue`: shared table and row rendering; no business API calls.
- Modify `frontend/src/components/TransferRecords.vue`, `frontend/src/components/StockTransferRecords.vue`: use projections and the shared list, preserving detail components, events and action conditions.
- Modify `frontend/src/styles/ledger-records.css`: the single record geometry, mobile layout, selection/focus and pending styling, owned by the shared component.

**Interfaces**

- Consumes existing API types and existing `money`, `statuses`, `stockStatuses` helpers.
- Produces `TransferRecordRow` display data containing kind/code, subject/goods, secondary metadata, values, account names and status text; `TransferRecordList` consumes `rows`, optional `selectedCode` and existing loading state, and emits `open(row)`.
- A narrow action/secondary-content slot carries already-existing stock completion hints/buttons. The parent decides availability and handles the click through its current `open` function.

- [x] Read the selected prototype and both record wrappers, including completion-report conditions.
- [x] Add the display type/projections and shared renderer. Keep quantities as strings and monetary values formatted by the existing helper.
- [x] Move common markup/styles to the new owner; render desktop columns as subject, value, source, fixed arrow, destination, status.
- [x] Add the pending pale warm background and 3px accent; preserve existing selected/focus and completion-report behavior.
- [x] Replace the two wrapper templates without moving their business handlers or changing props/events consumed by parent views.

## Task 2: Compact shell and common visual tokens

**Files:** `frontend/src/App.vue`, `frontend/src/style.css`, `frontend/src/theme.ts`.

- [x] Use the existing top business navigation with approximately 54px desktop height and a compact title/action row; retain the original logo and all accessible utility/account entries.
- [x] Add a desktop-only sidebar collapsed ref and visible toggle. Keep the current mobile open/close behavior separate, with responsive CSS deciding the active layout.
- [x] Apply the approved white/gray palette, clear text, subtle borders, small radii and consistent Naive UI controls. Replace conflicting old rules instead of growing another layer of overrides.
- [x] Let existing catalog/settings/export tables follow the common base styling without reconstructing their business layouts.

## Task 3: Homepage and detail presentation

**Files:** `frontend/src/views/DashboardView.vue`, `frontend/src/styles/dashboard.css`, `frontend/src/components/TransferDetail.vue`, `frontend/src/components/StockTransferDetail.vue`, `frontend/src/styles/transfer-drawer.css`.

- [x] Arrange existing homepage content as compact to-do entry points, funds/stock summaries, member balances and recent transfers; preserve the role-dependent entry conditions and existing real statistics.
- [x] Replace the separate recent-transfer table with `TransferRecordList` and the dashboard projection. Preserve the current latest-10 data, kind filters, empty state, actor/date information and full-list links.
- [x] Retain goods names in the primary reading area, keep individual SKU quantities/units aligned, and retain all existing data in the detail view.
- [x] Restyle/reorganize the two existing drawers into clear document information and processing-history sections; retain attachments, accounting/related records, Agent attribution, error feedback and every action condition/handler.

## Task 4: Concentrated verification and handoff

- [x] Run `npm run build`; expected TypeScript success and production bundle (existing bundle-size warning may remain).
- [x] Run `git diff --check`; expected no errors.
- [x] Capture desktop/mobile screenshots with approved local fixtures: fund/stock lists, mixed recent records, pending rows, long account names, multiple SKUs, empty data, and open/closed sidebar initial states. Do not automate interactions.
- [x] Review the diff against the five Review Focus items and verify no accidental backend/data/authorization changes.
- [x] Record actual results in `docs/prototype-status.md`; describe unverified interactive behavior accurately and retain production deployment as a separate task.

## Preparation outcome

2026-11-09: inspected current shell, both record wrappers, shared ledger CSS, homepage and both drawer owners. Current record wrappers already share some CSS but duplicate table markup; the homepage uses a third independent table. Existing pending styling should be retained and centralized, not implemented as another business state. The prototype will show the pending accent before the production UI changes begin.


## Implementation outcome

2026-11-09: completed all four tasks on `codex/navigation-shell`, preserving prior navigation and CSV preview changes. A single record renderer now owns fund/stock/home geometry; its first two table columns share a per-SKU grid so wrapped names and their quantities stay paired. Detail sections use local information/history tabs, with existing completion prompts and footer actions preserved. Export colors and table spacing follow the same neutral theme.

Verification: `npm run build` passed (TypeScript and Vite; existing >500 kB chunk warning remains), `git diff --check` passed. `node temp/erp-implementation-20261109/capture.cjs` captured 11 desktop/mobile fixture scenes, with no page errors or document horizontal overflow. Desktop row-arrow x coordinates were identical within each list (998px with sidebar, 935px collapsed). Fixtures include mixed recent records, pending/completed, multiple SKUs, long account names, deep-linked details, empty records and exports. Collapsed screenshot applies the initial layout class only; it does not test the toggle interaction.

A read-only code review found per-SKU name/quantity misalignment; the shared per-item grid fixed it, followed by a successful localized review, fresh build and screenshots. No automated clicks/forms, business write operations or new permanent tests. Interactive approval/completion/reversal and mobile drawer toggling were not exercised. No backend/API/schema/dependency changes in this redesign; prior CSV backend changes remain outside this delta. No production deployment.

Screenshots and fixture harness: `temp/erp-implementation-20261109/` (ignored local artifacts).
