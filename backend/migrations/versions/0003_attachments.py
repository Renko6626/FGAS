"""Add private image attachments for records and catalogs."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('attachments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('target_kind', sa.String(), nullable=False),
        sa.Column('target_id', sa.String(), nullable=False),
        sa.Column('uploaded_by', sa.String(), nullable=False),
        sa.Column('caption', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("target_kind IN ('transfer','stock_transfer','sku','fund_account','stock_account')", name=op.f('ck_attachments_target_kind_valid')),
        sa.CheckConstraint('byte_size > 0', name=op.f('ck_attachments_byte_size_positive')),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_attachments_uploaded_by_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_attachments')))
    op.create_index('attachments_target_key', 'attachments', ['target_kind', 'target_id'], unique=False)


def downgrade():
    op.drop_index('attachments_target_key', table_name='attachments')
    op.drop_table('attachments')
