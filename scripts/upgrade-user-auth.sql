-- Explicit PostgreSQL upgrade for existing development databases only.
-- Formal environments start from an empty database; metadata creates the new
-- schema and does not need this script.
-- Back up the database, stop related services and confirm the target database
-- before running: psql -v ON_ERROR_STOP=1 -f scripts/upgrade-user-auth.sql.
-- Existing development users keep sso_subject NULL; existing sessions receive
-- the default 168-hour lifetime measured from this migration.
BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS sso_subject VARCHAR,
    ADD COLUMN IF NOT EXISTS sso_username VARCHAR,
    ADD COLUMN IF NOT EXISTS email VARCHAR,
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE;

UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;
ALTER TABLE users
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN created_at SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS users_sso_subject_key
    ON users (sso_subject) WHERE sso_subject IS NOT NULL;

ALTER TABLE login_sessions
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE;

UPDATE login_sessions
    SET expires_at = CURRENT_TIMESTAMP + INTERVAL '168 hours'
    WHERE expires_at IS NULL;
UPDATE login_sessions SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;
ALTER TABLE login_sessions
    ALTER COLUMN expires_at SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN created_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS login_sessions_user_id_key ON login_sessions (user_id);
CREATE INDEX IF NOT EXISTS login_sessions_expires_at_key ON login_sessions (expires_at);

COMMIT;
