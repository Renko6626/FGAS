"""Persist the administrator-configured shared DeepSeek key."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('web_agent_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deepseek_api_key', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_web_agent_settings')))


def downgrade():
    op.drop_table('web_agent_settings')
