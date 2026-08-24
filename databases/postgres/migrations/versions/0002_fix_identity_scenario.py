"""Replace invalid identity seed with a valid versioned scenario."""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_fix_identity_scenario"
down_revision = "0001_controller"
branch_labels = None
depends_on = None


def _scenario_table():
    return sa.table(
        "scenario_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("definition", postgresql.JSONB()),
        sa.column("active", sa.Boolean()),
    )


def upgrade():
    scenario_templates = _scenario_table()
    op.execute(
        sa.update(scenario_templates)
        .where(scenario_templates.c.name == "identity")
        .values(active=False)
    )
    op.bulk_insert(
        scenario_templates,
        [{
            "id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
            "name": "identity",
            "version": 2,
            "definition": {
                "name": "identity",
                "version": 2,
                "actions": [
                    {"type": "open", "url": "https://example.com"},
                    {"type": "wait", "seconds": 2},
                    {"type": "screenshot", "name": "identity-test.png", "full_page": True},
                ],
            },
            "active": True,
        }],
    )


def downgrade():
    scenario_templates = _scenario_table()
    op.execute(
        sa.delete(scenario_templates).where(
            scenario_templates.c.id == uuid.UUID("00000000-0000-0000-0000-000000000002")
        )
    )
    op.execute(
        sa.update(scenario_templates)
        .where(scenario_templates.c.id == uuid.UUID("00000000-0000-0000-0000-000000000001"))
        .values(active=True)
    )
