"""Add soft deletion to restaurant tables."""

from alembic import op
import sqlalchemy as sa


revision = "0003_table_soft_delete"
down_revision = "0002_inventory_afip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(
            "open_tables",
            schema="public",
        )
    }
    if "deleted_at" not in columns:
        op.add_column(
            "open_tables",
            sa.Column(
                "deleted_at",
                sa.DateTime(),
                nullable=True,
            ),
            schema="public",
        )


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(
            "open_tables",
            schema="public",
        )
    }
    if "deleted_at" in columns:
        op.drop_column(
            "open_tables",
            "deleted_at",
            schema="public",
        )
