"""Add auditable cash closing revisions."""

from alembic import op
import sqlalchemy as sa


revision = "0004_cash_closing_revisions"
down_revision = "0003_table_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "cash_closing_revisions" in inspector.get_table_names(schema="public"):
        return

    op.create_table(
        "cash_closing_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cash_closing_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("previous_counted_cash", sa.Integer(), nullable=False),
        sa.Column("new_counted_cash", sa.Integer(), nullable=False),
        sa.Column("previous_notes", sa.Text(), nullable=True),
        sa.Column("new_notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "previous_counted_cash >= 0",
            name="ck_cash_closing_revisions_previous_cash",
        ),
        sa.CheckConstraint(
            "new_counted_cash >= 0",
            name="ck_cash_closing_revisions_new_cash",
        ),
        sa.ForeignKeyConstraint(
            ["cash_closing_id"],
            ["public.cash_closings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["public.user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_cash_closing_revisions_cash_closing_id",
        "cash_closing_revisions",
        ["cash_closing_id"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "cash_closing_revisions" not in inspector.get_table_names(
        schema="public"
    ):
        return

    op.drop_index(
        "ix_cash_closing_revisions_cash_closing_id",
        table_name="cash_closing_revisions",
        schema="public",
    )
    op.drop_table("cash_closing_revisions", schema="public")
