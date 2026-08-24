"""Add history-safe logical scenario deletion."""
from alembic import op
import sqlalchemy as sa

revision = "0005_scenario_logical_delete"
down_revision = "0004_identity_defaults"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("scenario_templates", sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_scenario_templates_deleted", "scenario_templates", ["deleted"])


def downgrade():
    op.drop_index("ix_scenario_templates_deleted", table_name="scenario_templates")
    op.drop_column("scenario_templates", "deleted")
