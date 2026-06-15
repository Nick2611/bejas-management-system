"""Add the operational business date to sales.

Revision ID: 0008_closing_business_date
Revises: 0007_multiple_cash_closings
Create Date: 2026-06-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_closing_business_date"
down_revision: str | Sequence[str] | None = "0007_multiple_cash_closings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "ix_public_closings_business_date"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("closings", schema="public")
    }
    if "business_date" not in columns:
        op.add_column(
            "closings",
            sa.Column("business_date", sa.Date(), nullable=True),
            schema="public",
        )
        op.execute(
            """
            UPDATE public.closings
            SET business_date = closing_time::date
            WHERE business_date IS NULL
            """
        )
        op.alter_column(
            "closings",
            "business_date",
            existing_type=sa.Date(),
            nullable=False,
            schema="public",
        )

    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(
            "closings",
            schema="public",
        )
    }
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            "closings",
            ["business_date"],
            schema="public",
        )


def downgrade() -> None:
    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(
            "closings",
            schema="public",
        )
    }
    if INDEX_NAME in indexes:
        op.drop_index(
            INDEX_NAME,
            table_name="closings",
            schema="public",
        )
    op.drop_column("closings", "business_date", schema="public")
