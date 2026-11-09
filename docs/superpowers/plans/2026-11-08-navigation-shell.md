# Navigation Shell Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this small UI change in the current session. User has already authorized implementation; no additional handoff approval is needed.

**Goal:** Reduce sidebar density with business navigation in a compact header.

**Architecture:** Keep the existing App.vue hash navigation, permission filtering and views. Derive the current sidebar from the active page's group and use existing Naive UI dropdowns for utilities and identity.

**Tech Stack:** Existing Vue 3, TypeScript, Naive UI and CSS.

**Spec:** `docs/superpowers/specs/2026-11-08-navigation-shell-design.md`

## Global Constraints

- Preserve existing hashes, query parameters, role gates and disabled stocktake entry.
- No new dependencies, browser clicks or form automation. Navigation itself requires no backend changes or permanent tests; the separately approved export preview adds one read-only endpoint and focused coverage in the existing export tests.

## Review Focus

- Direct page hashes must select the corresponding business area.
- Utility pages must remain reachable without becoming business tabs.
- Admin entries must remain role gated, including after permission changes.
- Header, mobile drawer and content must use matching offsets.
- Long user names and narrow screens must not crowd out navigation.

### Task 1: Navigation and responsive shell

**Files:** Modify `frontend/src/App.vue`, `frontend/src/style.css`; adjust the guide intro heading if necessary to retain one page h1.

- [x] Add group keys and utility groups; retain a flat allowed-page list for existing authorization and hash navigation.
- [x] Render business tabs, current-group sidebar, help/tools/account menus and content title.
- [x] Replace old header and sidebar dimensions/styles with compact desktop and mobile layouts.
- [x] Run `npm run build` (TypeScript and production build) and `git diff --check`.
- [x] Inspect desktop and mobile screenshots only; review the final diff against the constraints above.

### Task 2: Export controls and real preview (user approved)

**Files:** Modify `frontend/src/views/ExportsView.vue`, `backend/application/exports.py`, `backend/entrypoints/http.py`, `backend/tests/test_exports.py`.

- [x] Cover preview versus actual CSV rows/counts, 10-row limit and authentication in existing export tests; run on `fgas_test` before implementing the endpoint.
- [x] Extract the existing CSV preparation into one shared function. Add read-only `/api/exports/preview` with existing mode/time validation and no-store response.
- [x] Build compact export options, Chinese date/time pickers, shortcuts, precision inputs and a file-tabbed preview table with loading/error/empty feedback.
- [x] Run relevant export tests, `npm run build`, `git diff --check`, and desktop/mobile screenshots without automated interactions.

## Validation results

- `npm run build`: passed TypeScript checking and production build; existing large-main-chunk warning remains.
- Dedicated `fgas_test`: `.venv/bin/python -m pytest backend/tests/test_exports.py -q --tb=short` → 4 passed. The added preview cases failed before the endpoint existed and passed after implementation.
- `node temp/navigation-shell-20261108/capture.cjs`: desktop 1440px and mobile 390px screenshots, no page errors or horizontal overflow; screenshot-only, no automated clicks/forms.
- Independent static review: no actionable findings.
- `git diff --check`: passed. No production deployment.
