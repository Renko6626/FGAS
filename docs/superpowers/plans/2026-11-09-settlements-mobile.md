# Settlements and Mobile Reading Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for inline execution. Preserve existing uncommitted work; track actual outcomes below.

**Goal:** Make settlements and mobile workspace records readable without horizontal hunting for key fields.

**Architecture:** Existing views keep data, permissions, request and business handlers. A shared opt-in stylesheet supplies mobile record geometry; no new table framework or API.

**Tech Stack:** Existing Vue 3, TypeScript, Naive UI, Vite, CSS.

**Spec:** `docs/superpowers/specs/2026-11-09-settlements-mobile-design.md`

## Global Constraints

- Preserve prior navigation/export/ERP work and current branch; no schema, dependency, API or deployment changes.
- Net private balances do not represent per-item settlement completion. Preserve zero-balance accounts, disabled historic accounts and original matching history.
- Preserve role guards, hash links, original actions and drawer/editor handlers.
- Screenshot-only browser work; no automated clicks/forms/business writes. UI work adds no permanent tests.

## Review Focus

- Positive, negative and zero private net balances have correct direction and no false settled claim.
- Existing settlement requests, matching amounts, validity and role restrictions remain intact.
- Mobile tables retain all fields/actions; role, unit and status are readable before secondary metadata.
- Mobile long names wrap and account arrows remain fixed; desktop geometry remains usable.
- Warehouse list uses existing scope and actions; graph remains available and can remeasure after becoming visible.

## Tasks

- [x] Update `views/SettlementsView.vue`: existing-account entry, search, selected-account navigation; reorder both tables without changing handler code. Add compact scoped settlement styling.
- [x] Add shared `styles/responsive-tables.css`, import from existing style entry; mark original cells in SKU, member, user, Agent and settlement tables with labels/priority. Keep one DOM and original action conditions.
- [x] Adjust `styles/ledger-records.css` so mobile account names wrap across the subject/value width.
- [x] Adjust `components/inventory/InventoryWarehouses.vue` with mobile-only readable nodes/routes and optional existing graph; preserve graph and warehouse handlers. Shrink `FloatingWebAgent.vue` mobile launcher with accessible label.
- [x] Run `npm run build`, `git diff --check`, capture relevant desktop/mobile initial states, review presentation-only diff and record actual results in prototype status. No deployment.


## Outcome

Completed locally on 2026-11-09; no deployment or integration commit. Existing branch work preserved. Private account list uses existing balances, keeps zero/disabled accounts and clearly distinguishes net direction from item-level outstanding. Both settlement tables retain matching history and original service/editor handlers. A single opt-in stylesheet owns the mobile geometry for settlement/SKU/member/user/Agent tables; no duplicated mobile business renderer.

`npm run build` passed after all changes (TypeScript and Vite; original >500 kB chunk warning remains). `git diff --check` passed. Captured 24 main desktop/mobile fixture scenes plus 8 affected/empty/ordinary-role/expanded-layout scenes. No page/API errors or document overflow; all opted-in mobile table wrappers are 338px client/scroll width at 390px viewport; launcher width is 42px. Expanded warehouse screenshot applies the initial layout class, not a button workflow; existing ResizeObserver remeasures the newly visible graph.

Fresh read-only review found narrow desktop settlement fixed columns could overflow. Reproduced at 900px with ordinary ¥10000.00 content, then applied a 920px desktop minimum width, while shared mobile rules retain min-width:0. Final build and 900px/mobile screenshots confirmed readable cells; a narrow desktop table may scroll internally, without expanding the document.

No automated clicks/forms, business writes, real login/production data or new permanent tests. Tab switching, account selection/search, original matching/editor actions and actual graph-toggle interaction were not exercised in-browser; source reviewed and existing handlers preserved. Fixtures/screenshots/task diff: `temp/settlements-mobile-20261109/`.
