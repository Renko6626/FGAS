-- LEGACY / ADOPTION ONLY after the Alembic baseline.
-- Use only to adopt a pre-baseline database that cannot be discarded: back up,
-- run the legacy scripts, verify the schema, then `alembic stamp 0001`.
-- New installs and normal upgrades use `alembic upgrade head`.
-- Adds the ledger posting timestamp used by as-of balance queries, backfills
-- existing posted/reversed transfers from their 'posted' audit event, and adds
-- the indexes used by as-of reads. Pending/rejected transfers keep posted_at NULL.
-- Back up the database and confirm the target database before running:
--   psql -v ON_ERROR_STOP=1 -f scripts/upgrade-posted-at.sql
-- Do not run automatically at startup. Deploy this script before code that
-- selects transfers.posted_at.
BEGIN;

ALTER TABLE transfers
    ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP WITH TIME ZONE;

UPDATE transfers t
SET posted_at = a.created_at
FROM (
    SELECT transfer_id, MIN(created_at) AS created_at
    FROM audit_events
    WHERE action = 'posted'
    GROUP BY transfer_id
) a
WHERE t.id = a.transfer_id
  AND t.posted_at IS NULL;

-- Fallback for historical rows whose posting audit event is missing.
UPDATE transfers t
SET posted_at = t.created_at
WHERE t.posted_at IS NULL
  AND EXISTS (SELECT 1 FROM journal_lines j WHERE j.transfer_id = t.id);

CREATE INDEX IF NOT EXISTS transfers_posted_at_key ON transfers (posted_at);
CREATE INDEX IF NOT EXISTS transfers_effective_date_key ON transfers (effective_date);
CREATE INDEX IF NOT EXISTS journal_lines_account_id_key ON journal_lines (account_id);
CREATE INDEX IF NOT EXISTS journal_lines_transfer_id_key ON journal_lines (transfer_id);
CREATE INDEX IF NOT EXISTS stock_moves_created_at_key ON stock_moves (created_at);

COMMIT;
