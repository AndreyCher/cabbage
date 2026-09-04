"""Track whether a GEO provider was actually reached.

Revision ID: 0013_proxy_attempts
Revises: 0012_run_policy_flags
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_proxy_attempts"
down_revision = "0012_run_policy_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxy_check_results", sa.Column("provider_reached", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("proxy_check_results", "provider_reached")
