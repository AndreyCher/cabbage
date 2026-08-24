"""Initial Controller persistence schema."""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_controller"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("scenario_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version"))
    op.create_index("ix_scenario_templates_name", "scenario_templates", ["name"])
    op.create_table("proxy_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False),
        sa.Column("scheme", sa.String(16), nullable=False, server_default="http"),
        sa.Column("host", sa.String(255), nullable=False), sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(255)), sa.Column("encrypted_password", sa.Text()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("identity", sa.String(128), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_templates.id"), nullable=False),
        sa.Column("proxy_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proxy_configs.id")),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debug", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("proxy_mode", sa.String(16), nullable=False, server_default="default"),
        sa.Column("overrides", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("current_stage", sa.String(255)), sa.Column("current_action", sa.Integer()),
        sa.Column("container_id", sa.String(128)), sa.Column("controller_id", sa.String(128)),
        sa.Column("error_reason", sa.Text()), sa.Column("artifact_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)))
    for column in ("identity", "status", "priority", "container_id", "controller_id", "created_at"):
        op.create_index(f"ix_runs_{column}", "runs", [column])
    scenario_templates = sa.table(
        "scenario_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("definition", postgresql.JSONB()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        scenario_templates,
        [{
            "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "name": "identity",
            "version": 1,
            "definition": {
                "name": "identity",
                "version": 1,
                "actions": [
                    {"type": "goto", "url": "https://example.com"},
                    {"type": "wait", "seconds": 2},
                ],
            },
            "active": True,
        }],
    )


def downgrade():
    op.drop_table("runs")
    op.drop_table("proxy_configs")
    op.drop_table("scenario_templates")
