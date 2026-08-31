"""Add full worker control-plane fields.

Revision ID: 0006_full_worker_control
Revises: 0005_scenario_logical_delete
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_full_worker_control"
down_revision = "0005_scenario_logical_delete"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("proxy_configs", sa.Column("bypass", sa.Text(), nullable=True))
    op.add_column("proxy_configs", sa.Column("geoip", postgresql.JSONB(), nullable=False, server_default='{"enabled":true,"validate_identity":true,"fail_on_mismatch":false}'))
    op.add_column("proxy_configs", sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("identity_profiles", sa.Column("pending_operation", sa.String(16), nullable=True))
    op.add_column("runs", sa.Column("timeout_seconds", sa.Integer(), nullable=True))
    op.add_column("runs", sa.Column("worker_run_id", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("runs", "worker_run_id")
    op.drop_column("runs", "timeout_seconds")
    op.drop_column("identity_profiles", "pending_operation")
    op.drop_column("proxy_configs", "verify_ssl")
    op.drop_column("proxy_configs", "geoip")
    op.drop_column("proxy_configs", "bypass")
