"""Allow successive cash closings for the same business date.

Revision ID: 0007_multiple_cash_closings
Revises: 0006_fiscal_closure_refactor
Create Date: 2026-06-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_multiple_cash_closings"
down_revision: str | Sequence[str] | None = "0006_fiscal_closure_refactor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "ix_public_cash_closings_business_date"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {
        index["name"]: index
        for index in inspector.get_indexes(
            "cash_closings",
            schema="public",
        )
    }
    current = indexes.get(INDEX_NAME)
    if current is not None and current.get("unique"):
        op.drop_index(
            INDEX_NAME,
            table_name="cash_closings",
            schema="public",
        )
        op.create_index(
            INDEX_NAME,
            "cash_closings",
            ["business_date"],
            unique=False,
            schema="public",
        )


def downgrade() -> None:
    duplicate_date = op.get_bind().scalar(
        sa.text(
            """
            SELECT business_date
            FROM public.cash_closings
            GROUP BY business_date
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    )
    if duplicate_date is not None:
        raise RuntimeError(
            "No se puede restaurar la unicidad de cash_closings.business_date: "
            "existen cierres sucesivos para una misma fecha."
        )

    inspector = sa.inspect(op.get_bind())
    indexes = {
        index["name"]: index
        for index in inspector.get_indexes(
            "cash_closings",
            schema="public",
        )
    }
    current = indexes.get(INDEX_NAME)
    if current is not None and not current.get("unique"):
        op.drop_index(
            INDEX_NAME,
            table_name="cash_closings",
            schema="public",
        )
        op.create_index(
            INDEX_NAME,
            "cash_closings",
            ["business_date"],
            unique=True,
            schema="public",
        )
