"""Add the invoice outbox table.

Revision ID: 60d926272d46
Revises: 0004_cash_closing_revisions
Create Date: 2026-06-11 21:14:44.039363
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "60d926272d46"
down_revision: Union[str, Sequence[str], None] = (
    "0004_cash_closing_revisions"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )


def downgrade() -> None:
    op.drop_table("outbox_invoices", schema="public")
