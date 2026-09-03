"""Remove scenario-level proxy configuration.

Revision ID: 0009_remove_scenario_proxy
Revises: 0008_context_proxy_defaults
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_remove_scenario_proxy"
down_revision = "0008_context_proxy_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("fk_scenario_templates_default_proxy", "scenario_templates", type_="foreignkey")
    op.drop_column("scenario_templates", "default_proxy_config_id")


def downgrade() -> None:
    op.add_column("scenario_templates", sa.Column("default_proxy_config_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_scenario_templates_default_proxy", "scenario_templates", "proxy_configs", ["default_proxy_config_id"], ["id"])
