# Frontend Phase B report

Implemented approved Vue3 + TypeScript + Vite + Naive UI functional shell, with ordinary Chinese admin styling. Modules separate typed HTTP API, selector/editor components and catalogs/transfers/users views. No backend or spec changes.

## Delivered

- Visible development identity, persisted cookie login/logout, role-gated tabs and actions.
- Actual fund book-balance summary; account kind/fund marker/tags/balances and name/tag editing; location custodian/tag directory editing.
- Transfer source/destination selectors independently filter by kind and tags without silently changing selected endpoints. Explicit names/IDs, text amount, date, description/counterparty, backend preview and proposed journal lines.
- Submit maintains an idempotency key and locks the payload for retry after error. Pending/posted notices, records/detail, journal/audit/reversal references, reversal reason and retry key, actual expected_version approval/rejection.
- Admin existing user role/active editor with backend authority and refreshed current identity.
- Root npm run dev loads existing .env and launches backend/Vite in owned process groups, terminating both on interruption; no process-manager dependency or PostgreSQL management. Frontend-only script remains available.

## Verification

- Worker initial npm --prefix frontend install and exact npm install sessions produced no output under restricted network and were interrupted; no unrelated dependency workaround used.
- Worker npm run build initially failed `vue-tsc: not found` because dependencies were absent.
- Controller exact `npm install` in frontend: passed, 66 packages installed in 5 seconds; package-lock included. npm warned about esbuild install-script approval, but actual build worked.
- Controller `npm run build`: passed, vue-tsc and Vite 7.3.7, 2671 modules, approximately 417 kB JS.
- Worker `node --check scripts/dev.mjs`: passed.
- No permanent UI tests, automated browser clicks/forms or PostgreSQL start/stop. Controller owns runtime launch and desktop/mobile screenshots.

Expected frontend URL: http://localhost:5173; same-origin /api proxy defaults to http://127.0.0.1:8000. UI end-to-end acceptance and browser interactions are unverified. Retry keys are in-memory; reload or identity switch clears drafts, so uncertain outcomes should be checked in records before starting another submission. The prototype uses number-valued integer fen from current backend JSON, with formatting via BigInt; amounts beyond JavaScript safe-integer precision remain an existing JSON contract limit.

## Medium review Important correction

Captured a copied transfer payload and its serialized stamp before awaiting preview. An arriving response is accepted only while the current form matches that request; edits therefore leave submission unavailable until their own valid preview. Busy guards prevent overlapping previews/submissions, and confirmation is disabled while any request is outstanding. Existing failed-submit payload locking and idempotency keys remain intact. Expanded the changed state-changing functions for readability; the review's broader Minor source-formatting observation remains non-blocking.

Worker `npm run build`: passed, vue-tsc and Vite 7.3.7, 2671 modules, 417.29 kB JS; no browser interactions or extra permanent tests. Preview response/request ordering was inspected in the changed production functions; deferred-request UI interaction was not executed.
