"""Add verified country proxy pools.

Revision ID: 0010_country_proxy_pools
Revises: 0009_remove_scenario_proxy
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_country_proxy_pools"
down_revision = "0009_remove_scenario_proxy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxy_configs", sa.Column("country_code", sa.String(2), nullable=True))
    op.add_column("proxy_configs", sa.Column("country_name", sa.String(128), nullable=True))
    op.add_column("proxy_configs", sa.Column("exit_ip", sa.String(64), nullable=True))
    op.add_column("proxy_configs", sa.Column("timezone", sa.String(128), nullable=True))
    op.add_column("proxy_configs", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("proxy_configs", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_proxy_configs_country_code", "proxy_configs", ["country_code"])
    op.create_index("ix_proxy_configs_last_used_at", "proxy_configs", ["last_used_at"])
    op.add_column("identity_profiles", sa.Column("proxy_country_code", sa.String(2), nullable=True))
    op.create_index("ix_identity_profiles_proxy_country_code", "identity_profiles", ["proxy_country_code"])
    op.execute("""
        UPDATE identity_profiles i SET proxy_country_code = p.country_code
        FROM proxy_configs p WHERE i.default_proxy_config_id = p.id
    """)
    op.drop_constraint("fk_identity_profiles_default_proxy", "identity_profiles", type_="foreignkey")
    op.drop_column("identity_profiles", "default_proxy_config_id")


def downgrade() -> None:
    op.add_column("identity_profiles", sa.Column("default_proxy_config_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_identity_profiles_default_proxy", "identity_profiles", "proxy_configs", ["default_proxy_config_id"], ["id"])
    op.drop_index("ix_identity_profiles_proxy_country_code", table_name="identity_profiles")
    op.drop_column("identity_profiles", "proxy_country_code")
    op.drop_index("ix_proxy_configs_last_used_at", table_name="proxy_configs")
    op.drop_index("ix_proxy_configs_country_code", table_name="proxy_configs")
    for column in ("last_used_at", "last_checked_at", "timezone", "exit_ip", "country_name", "country_code"):
        op.drop_column("proxy_configs", column)
