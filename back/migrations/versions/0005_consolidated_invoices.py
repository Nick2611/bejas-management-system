"""Normalize invoice sales and support consolidated period invoices.

Revision ID: 0005_consolidated_invoices
Revises: 60d926272d46
Create Date: 2026-06-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_consolidated_invoices"
down_revision: str | Sequence[str] | None = "60d926272d46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(inspector: sa.Inspector) -> set[str]:
    return {
        column["name"]
        for column in inspector.get_columns("invoices", schema="public")
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector)

    if "declaration_type" not in columns:
        op.add_column(
            "invoices",
            sa.Column("declaration_type", sa.String(20), nullable=True),
            schema="public",
        )
    if "total" not in columns:
        op.add_column(
            "invoices",
            sa.Column("total", sa.Integer(), nullable=True),
            schema="public",
        )
    if "sales_count" not in columns:
        op.add_column(
            "invoices",
            sa.Column("sales_count", sa.Integer(), nullable=True),
            schema="public",
        )
    if "period_start" not in columns:
        op.add_column(
            "invoices",
            sa.Column("period_start", sa.DateTime(), nullable=True),
            schema="public",
        )
    if "period_end" not in columns:
        op.add_column(
            "invoices",
            sa.Column("period_end", sa.DateTime(), nullable=True),
            schema="public",
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("invoice_closings", schema="public"):
        op.create_table(
            "invoice_closings",
            sa.Column("invoice_id", sa.Integer(), nullable=False),
            sa.Column("closing_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["invoice_id"],
                ["public.invoices.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["closing_id"],
                ["public.closings.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("invoice_id", "closing_id"),
            sa.UniqueConstraint(
                "closing_id",
                name="uq_invoice_closings_closing_id",
            ),
            schema="public",
        )

    columns = _column_names(sa.inspect(bind))
    if "closing_id" in columns:
        bind.execute(
            sa.text(
                """
                INSERT INTO public.invoice_closings (invoice_id, closing_id)
                SELECT id, closing_id
                FROM public.invoices
                ON CONFLICT (closing_id) DO NOTHING
                """
            )
        )
        bind.execute(
            sa.text(
                """
                UPDATE public.invoices AS invoice
                SET declaration_type = COALESCE(invoice.declaration_type, 'legacy'),
                    total = COALESCE(invoice.total, closing.total),
                    sales_count = COALESCE(invoice.sales_count, 1)
                FROM public.closings AS closing
                WHERE closing.id = invoice.closing_id
                """
            )
        )

        inspector = sa.inspect(bind)
        for constraint in inspector.get_foreign_keys(
            "invoices",
            schema="public",
        ):
            if constraint["constrained_columns"] == ["closing_id"]:
                op.drop_constraint(
                    constraint["name"],
                    "invoices",
                    schema="public",
                    type_="foreignkey",
                )
        for constraint in inspector.get_unique_constraints(
            "invoices",
            schema="public",
        ):
            if constraint["column_names"] == ["closing_id"]:
                op.drop_constraint(
                    constraint["name"],
                    "invoices",
                    schema="public",
                    type_="unique",
                )
        op.drop_column("invoices", "closing_id", schema="public")

    bind.execute(
        sa.text(
            """
            UPDATE public.invoices
            SET declaration_type = COALESCE(declaration_type, 'legacy'),
                total = COALESCE(total, 1),
                sales_count = COALESCE(sales_count, 1)
            """
        )
    )
    op.alter_column(
        "invoices",
        "declaration_type",
        existing_type=sa.String(20),
        nullable=False,
        schema="public",
    )
    op.alter_column(
        "invoices",
        "total",
        existing_type=sa.Integer(),
        nullable=False,
        schema="public",
    )
    op.alter_column(
        "invoices",
        "sales_count",
        existing_type=sa.Integer(),
        nullable=False,
        schema="public",
    )

    inspector = sa.inspect(bind)
    check_names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(
            "invoices",
            schema="public",
        )
    }
    if "ck_invoices_total" not in check_names:
        op.create_check_constraint(
            "ck_invoices_total",
            "invoices",
            "total > 0",
            schema="public",
        )
    if "ck_invoices_sales_count" not in check_names:
        op.create_check_constraint(
            "ck_invoices_sales_count",
            "invoices",
            "sales_count > 0",
            schema="public",
        )
    if "ck_invoices_declaration_type" not in check_names:
        op.create_check_constraint(
            "ck_invoices_declaration_type",
            "invoices",
            (
                "declaration_type IN "
                "('ticket', 'diario', 'mensual', 'legacy')"
            ),
            schema="public",
        )


def downgrade() -> None:
    bind = op.get_bind()
    invalid = bind.scalar(
        sa.text(
            """
            SELECT COUNT(*)
            FROM public.invoices AS invoice
            LEFT JOIN public.invoice_closings AS relation
                ON relation.invoice_id = invoice.id
            GROUP BY invoice.id
            HAVING COUNT(relation.closing_id) <> 1
            LIMIT 1
            """
        )
    )
    if invalid is not None:
        raise RuntimeError(
            "No se puede revertir: existen facturas consolidadas "
            "o sin una única venta"
        )

    op.add_column(
        "invoices",
        sa.Column("closing_id", sa.Integer(), nullable=True),
        schema="public",
    )
    bind.execute(
        sa.text(
            """
            UPDATE public.invoices AS invoice
            SET closing_id = relation.closing_id
            FROM public.invoice_closings AS relation
            WHERE relation.invoice_id = invoice.id
            """
        )
    )
    op.alter_column(
        "invoices",
        "closing_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema="public",
    )
    op.create_unique_constraint(
        "invoices_closing_id_key",
        "invoices",
        ["closing_id"],
        schema="public",
    )
    op.create_foreign_key(
        "invoices_closing_id_fkey",
        "invoices",
        "closings",
        ["closing_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="CASCADE",
    )
    op.drop_table("invoice_closings", schema="public")
    op.drop_constraint(
        "ck_invoices_declaration_type",
        "invoices",
        schema="public",
        type_="check",
    )
    op.drop_constraint(
        "ck_invoices_sales_count",
        "invoices",
        schema="public",
        type_="check",
    )
    op.drop_constraint(
        "ck_invoices_total",
        "invoices",
        schema="public",
        type_="check",
    )
    op.drop_column("invoices", "period_end", schema="public")
    op.drop_column("invoices", "period_start", schema="public")
    op.drop_column("invoices", "sales_count", schema="public")
    op.drop_column("invoices", "total", schema="public")
    op.drop_column("invoices", "declaration_type", schema="public")
