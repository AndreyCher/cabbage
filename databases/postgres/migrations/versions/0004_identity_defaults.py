"""Add Controller settings and default Identity profile."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_identity_defaults"
down_revision = "0003_identity_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "controller_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    table = sa.table(
        "controller_settings",
        sa.column("key", sa.String()), sa.column("value", postgresql.JSONB()),
        sa.column("revision", sa.Integer()),
    )
    op.bulk_insert(table, [{
        "key": "identity_defaults",
        "value": {
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
    op.drop_table("controller_settings")
