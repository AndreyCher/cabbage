"""Split run location and proxy overrides.

Revision ID: 0012_run_policy_flags
Revises: 0011_proxy_checker_jobs
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_run_policy_flags"
down_revision = "0011_proxy_checker_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("ignore_identity_location", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("runs", sa.Column("ignore_proxy_requirement", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("runs", "ignore_proxy_requirement")
    op.drop_column("runs", "ignore_identity_location")
