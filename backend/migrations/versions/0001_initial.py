"""Initial development funds schema."""
from alembic import op
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute('CREATE TABLE ledger_accounts (\n\tid VARCHAR NOT NULL, \n\tname VARCHAR NOT NULL, \n\tkind VARCHAR NOT NULL, \n\ttags JSON NOT NULL, \n\tPRIMARY KEY (id)\n)')
    op.execute('CREATE TABLE stock_locations (\n\tid VARCHAR NOT NULL, \n\tname VARCHAR NOT NULL, \n\tcustodian_label VARCHAR NOT NULL, \n\ttags JSON NOT NULL, \n\tPRIMARY KEY (id)\n)')
    op.execute('CREATE TABLE users (\n\tid VARCHAR NOT NULL, \n\tdisplay_name VARCHAR NOT NULL, \n\trole VARCHAR NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tPRIMARY KEY (id)\n)')
    op.execute('CREATE TABLE fund_accounts (\n\taccount_id VARCHAR NOT NULL, \n\tPRIMARY KEY (account_id), \n\tFOREIGN KEY(account_id) REFERENCES ledger_accounts (id)\n)')
    op.execute('CREATE TABLE login_sessions (\n\tid VARCHAR NOT NULL, \n\tuser_id VARCHAR NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)')
    op.execute('CREATE TABLE transfers (\n\tid VARCHAR NOT NULL, \n\tsource_account_id VARCHAR NOT NULL, \n\tdestination_account_id VARCHAR NOT NULL, \n\tamount_minor BIGINT NOT NULL, \n\teffective_date DATE NOT NULL, \n\tdescription VARCHAR NOT NULL, \n\tcounterparty VARCHAR, \n\tactor_id VARCHAR NOT NULL, \n\tapproved_by VARCHAR, \n\tapproval_mode VARCHAR, \n\tstatus VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\tidempotency_key VARCHAR NOT NULL, \n\tpayload JSON NOT NULL, \n\treversal_of VARCHAR, \n\treason VARCHAR, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (actor_id, idempotency_key), \n\tCHECK (amount_minor > 0), \n\tFOREIGN KEY(source_account_id) REFERENCES ledger_accounts (id), \n\tFOREIGN KEY(destination_account_id) REFERENCES ledger_accounts (id), \n\tFOREIGN KEY(actor_id) REFERENCES users (id), \n\tFOREIGN KEY(approved_by) REFERENCES users (id), \n\tFOREIGN KEY(reversal_of) REFERENCES transfers (id)\n)')
    op.execute('CREATE TABLE audit_events (\n\tid VARCHAR NOT NULL, \n\ttransfer_id VARCHAR NOT NULL, \n\tactor_id VARCHAR NOT NULL, \n\taction VARCHAR NOT NULL, \n\tdetail VARCHAR NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(transfer_id) REFERENCES transfers (id), \n\tFOREIGN KEY(actor_id) REFERENCES users (id)\n)')
    op.execute('CREATE TABLE journal_lines (\n\tid VARCHAR NOT NULL, \n\ttransfer_id VARCHAR NOT NULL, \n\taccount_id VARCHAR NOT NULL, \n\tdebit_minor BIGINT NOT NULL, \n\tcredit_minor BIGINT NOT NULL, \n\tPRIMARY KEY (id), \n\tCHECK ((debit_minor > 0 AND credit_minor = 0) OR (credit_minor > 0 AND debit_minor = 0)), \n\tFOREIGN KEY(transfer_id) REFERENCES transfers (id), \n\tFOREIGN KEY(account_id) REFERENCES ledger_accounts (id)\n)')

def downgrade():
    op.drop_table('journal_lines')
    op.drop_table('audit_events')
    op.drop_table('transfers')
    op.drop_table('login_sessions')
    op.drop_table('fund_accounts')
    op.drop_table('users')
    op.drop_table('stock_locations')
    op.drop_table('ledger_accounts')
