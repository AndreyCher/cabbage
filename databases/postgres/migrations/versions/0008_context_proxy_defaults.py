"""Add Identity and scenario default proxy references.

Revision ID: 0008_context_proxy_defaults
Revises: 0007_worker_defaults
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_context_proxy_defaults"
down_revision = "0007_worker_defaults"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("identity_profiles", sa.Column("default_proxy_config_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_identity_profiles_default_proxy", "identity_profiles", "proxy_configs", ["default_proxy_config_id"], ["id"])
    op.add_column("scenario_templates", sa.Column("default_proxy_config_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_scenario_templates_default_proxy", "scenario_templates", "proxy_configs", ["default_proxy_config_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_scenario_templates_default_proxy", "scenario_templates", type_="foreignkey")
    op.drop_column("scenario_templates", "default_proxy_config_id")
    op.drop_constraint("fk_identity_profiles_default_proxy", "identity_profiles", type_="foreignkey")
    op.drop_column("identity_profiles", "default_proxy_config_id")
