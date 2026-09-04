"""Add asynchronous proxy checker jobs and history.

Revision ID: 0011_proxy_checker_jobs
Revises: 0010_country_proxy_pools
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_proxy_checker_jobs"
down_revision = "0010_country_proxy_pools"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("proxy_configs", sa.Column("expected_country_code", sa.String(2), nullable=True))
    op.add_column("proxy_configs", sa.Column("check_status", sa.String(32), nullable=False, server_default="pending"))
    op.add_column("proxy_configs", sa.Column("check_error", sa.Text(), nullable=True))
    op.add_column("proxy_configs", sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_proxy_configs_check_status", "proxy_configs", ["check_status"])
    op.create_table("proxy_check_jobs", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("proxy_config_id", sa.UUID(), sa.ForeignKey("proxy_configs.id"), nullable=False), sa.Column("priority", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(24), nullable=False, server_default="queued"), sa.Column("requested_by", sa.String(32), nullable=False, server_default="scheduler"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("error", sa.Text()))
    op.create_index("ix_proxy_check_jobs_proxy_config_id", "proxy_check_jobs", ["proxy_config_id"])
    op.create_index("ix_proxy_check_jobs_priority", "proxy_check_jobs", ["priority"])
    op.create_index("ix_proxy_check_jobs_status", "proxy_check_jobs", ["status"])
    op.create_table("proxy_check_results", sa.Column("id", sa.UUID(), primary_key=True), sa.Column("job_id", sa.UUID(), sa.ForeignKey("proxy_check_jobs.id"), nullable=False), sa.Column("proxy_config_id", sa.UUID(), sa.ForeignKey("proxy_configs.id"), nullable=False), sa.Column("provider", sa.String(64), nullable=False), sa.Column("success", sa.Boolean(), nullable=False), sa.Column("exit_ip", sa.String(64)), sa.Column("country_code", sa.String(2)), sa.Column("country_name", sa.String(128)), sa.Column("timezone", sa.String(128)), sa.Column("latency_ms", sa.Integer()), sa.Column("error", sa.Text()), sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_proxy_check_results_job_id", "proxy_check_results", ["job_id"])
    op.create_index("ix_proxy_check_results_proxy_config_id", "proxy_check_results", ["proxy_config_id"])

def downgrade() -> None:
    op.drop_table("proxy_check_results")
    op.drop_table("proxy_check_jobs")
    op.drop_index("ix_proxy_configs_check_status", table_name="proxy_configs")
    op.drop_column("proxy_configs", "consecutive_failures")
    op.drop_column("proxy_configs", "check_error")
    op.drop_column("proxy_configs", "check_status")
    op.drop_column("proxy_configs", "expected_country_code")
