-- LEGACY / ADOPTION ONLY after the Alembic baseline.
-- Use only to adopt a pre-baseline database that cannot be discarded: back up,
-- run the legacy scripts, verify the schema, then `alembic stamp 0001`.
-- New installs and normal upgrades use `alembic upgrade head`.
-- Explicit PostgreSQL upgrade. Confirm the target database and stop related
-- services before running. Existing records remain unchanged; source stays NULL.
-- Run with psql -v ON_ERROR_STOP=1 -f scripts/upgrade-agent-access.sql.
BEGIN;

CREATE TABLE IF NOT EXISTS agent_credentials (
    id VARCHAR PRIMARY KEY,
    owner_user_id VARCHAR NOT NULL REFERENCES users(id),
    name VARCHAR NOT NULL,
    secret_hash VARCHAR NOT NULL UNIQUE,
    level VARCHAR NOT NULL CHECK (level IN ('low', 'high')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE transfers
    ADD COLUMN IF NOT EXISTS submitted_credential_id VARCHAR REFERENCES agent_credentials(id),
    ADD COLUMN IF NOT EXISTS submitted_credential_name VARCHAR;
ALTER TABLE stock_transfers
    ADD COLUMN IF NOT EXISTS submitted_credential_id VARCHAR REFERENCES agent_credentials(id),
    ADD COLUMN IF NOT EXISTS submitted_credential_name VARCHAR;
ALTER TABLE stock_confirmations
    ADD COLUMN IF NOT EXISTS submitted_credential_id VARCHAR REFERENCES agent_credentials(id),
    ADD COLUMN IF NOT EXISTS submitted_credential_name VARCHAR;
ALTER TABLE audit_events
    ADD COLUMN IF NOT EXISTS agent_credential_id VARCHAR REFERENCES agent_credentials(id),
    ADD COLUMN IF NOT EXISTS agent_credential_name VARCHAR;
ALTER TABLE stock_audit_events
    ADD COLUMN IF NOT EXISTS agent_credential_id VARCHAR REFERENCES agent_credentials(id),
    ADD COLUMN IF NOT EXISTS agent_credential_name VARCHAR;

COMMIT;
