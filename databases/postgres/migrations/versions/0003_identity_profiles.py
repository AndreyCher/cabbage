"""Add durable editable Identity profiles."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_identity_profiles"
down_revision = "0002_fix_identity_scenario"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "identity_profiles",
        sa.Column("identity", sa.String(128), primary_key=True),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    table = sa.table(
        "identity_profiles",
        sa.column("identity", sa.String()),
        sa.column("config", postgresql.JSONB()),
        sa.column("revision", sa.Integer()),
    )
    op.bulk_insert(table, [{
        "identity": "test-user-001",
        "config": {
            "fingerprint": {
                "os": "default", "preset": "default", "screen": "default",
                "locale": "default", "window": "default",
                "device_pixel_ratio": "default", "hardware_concurrency": "default",
                "webgl": "default", "languages": "default", "timezone": "default"
            }
        },
        "revision": 1,
    }])


def downgrade():
    op.drop_table("identity_profiles")
