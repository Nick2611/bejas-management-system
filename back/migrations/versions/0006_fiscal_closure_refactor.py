"""Separate sale invoicing from fiscal period declarations.

Revision ID: 0006_fiscal_closure_refactor
Revises: 0005_consolidated_invoices
Create Date: 2026-06-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_fiscal_closure_refactor"
down_revision: str | Sequence[str] | None = "0005_consolidated_invoices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(
            table_name,
            schema="public",
        )
    }


def _indexes(table_name: str) -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(
            table_name,
            schema="public",
        )
    }


def upgrade() -> None:
    bind = op.get_bind()

    closing_columns = _columns("closings")
    if "invoicing_status" not in closing_columns:
        op.add_column(
            "closings",
            sa.Column("invoicing_status", sa.String(40), nullable=True),
            schema="public",
        )
    op.alter_column(
        "invoices",
        "status",
        existing_type=sa.String(),
        type_=sa.String(40),
        existing_nullable=False,
        schema="public",
    )
    bind.execute(
        sa.text(
            """
            UPDATE public.closings AS sale
            SET invoicing_status = CASE
                WHEN invoice.status IN ('autorizada', 'INVOICE_AUTHORIZED')
                    THEN 'SALE_INVOICED'
                WHEN invoice.status IN ('rechazada', 'INVOICE_REJECTED')
                    THEN 'SALE_INVOICE_REJECTED'
                WHEN invoice.id IS NOT NULL
                    THEN 'SALE_INVOICING_PENDING'
                ELSE 'SALE_REGISTERED'
            END
            FROM public.invoice_closings AS relation
            LEFT JOIN public.invoices AS invoice
                ON invoice.id = relation.invoice_id
            WHERE relation.closing_id = sale.id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE public.closings
            SET invoicing_status = 'SALE_REGISTERED'
            WHERE invoicing_status IS NULL
            """
        )
    )
    op.alter_column(
        "closings",
        "invoicing_status",
        existing_type=sa.String(40),
        nullable=False,
        schema="public",
    )

    invoice_columns = _columns("invoices")
    if "authorization_date" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("authorization_date", sa.DateTime(), nullable=True),
            schema="public",
        )
    if "rejection_reason" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            schema="public",
        )
    if "created_at" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("created_at", sa.DateTime(), nullable=True),
            schema="public",
        )
    if "updated_at" not in invoice_columns:
        op.add_column(
            "invoices",
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            schema="public",
        )

    bind.execute(
        sa.text(
            """
            UPDATE public.invoices
            SET status = CASE status
                WHEN 'pendiente' THEN 'INVOICE_PENDING'
                WHEN 'autorizada' THEN 'INVOICE_AUTHORIZED'
                WHEN 'rechazada' THEN 'INVOICE_REJECTED'
                WHEN 'anulada' THEN 'INVOICE_CANCELLED'
                ELSE status
            END,
            authorization_date = CASE
                WHEN status IN ('autorizada', 'INVOICE_AUTHORIZED')
                    THEN COALESCE(authorization_date, issued_at)
                ELSE authorization_date
            END,
            created_at = COALESCE(created_at, issued_at),
            updated_at = COALESCE(updated_at, issued_at)
            """
        )
    )
    op.alter_column(
        "invoices",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=False,
        schema="public",
    )
    op.alter_column(
        "invoices",
        "updated_at",
        existing_type=sa.DateTime(),
        nullable=False,
        schema="public",
    )
    if "ix_invoices_updated_at" not in _indexes("invoices"):
        op.create_index(
            "ix_invoices_updated_at",
            "invoices",
            ["updated_at"],
            schema="public",
        )

    attempt_columns = _columns("invoice_attempts")
    additions = (
        ("attempt_number", sa.Integer()),
        ("status_before", sa.String(40)),
        ("status_after", sa.String(40)),
        ("error_reason", sa.Text()),
        ("correlation_id", sa.String(64)),
        ("worker_id", sa.String(100)),
    )
    for name, column_type in additions:
        if name not in attempt_columns:
            op.add_column(
                "invoice_attempts",
                sa.Column(name, column_type, nullable=True),
                schema="public",
            )
    bind.execute(
        sa.text(
            """
            UPDATE public.invoice_attempts AS attempt
            SET attempt_number = (
                    SELECT COUNT(*)
                    FROM public.invoice_attempts AS previous
                    WHERE previous.invoice_id = attempt.invoice_id
                      AND (
                        previous.attempted_at < attempt.attempted_at
                        OR (
                            previous.attempted_at = attempt.attempted_at
                            AND previous.id <= attempt.id
                        )
                      )
                ),
                status_before = COALESCE(
                    attempt.status_before,
                    'INVOICE_AUTHORIZING'
                ),
                status_after = COALESCE(
                    attempt.status_after,
                    CASE
                        WHEN attempt.success
                            THEN 'INVOICE_AUTHORIZED'
                        ELSE 'INVOICE_RETRY_PENDING'
                    END
                ),
                error_reason = COALESCE(attempt.error_reason, attempt.error)
            """
        )
    )
    for column_name, column_type in (
        ("attempt_number", sa.Integer()),
        ("status_before", sa.String(40)),
        ("status_after", sa.String(40)),
    ):
        op.alter_column(
            "invoice_attempts",
            column_name,
            existing_type=column_type,
            nullable=False,
            schema="public",
        )

    outbox_columns = _columns("outbox_invoices")
    if "invoice_id" not in outbox_columns:
        op.add_column(
            "outbox_invoices",
            sa.Column("invoice_id", sa.Integer(), nullable=True),
            schema="public",
        )
        op.create_foreign_key(
            "fk_outbox_invoices_invoice_id",
            "outbox_invoices",
            "invoices",
            ["invoice_id"],
            ["id"],
            source_schema="public",
            referent_schema="public",
            ondelete="CASCADE",
        )
    if "correlation_id" not in outbox_columns:
        op.add_column(
            "outbox_invoices",
            sa.Column("correlation_id", sa.String(64), nullable=True),
            schema="public",
        )
    if "created_at" not in outbox_columns:
        op.add_column(
            "outbox_invoices",
            sa.Column("created_at", sa.DateTime(), nullable=True),
            schema="public",
        )
    if "published_at" not in outbox_columns:
        op.add_column(
            "outbox_invoices",
            sa.Column("published_at", sa.DateTime(), nullable=True),
            schema="public",
        )
    bind.execute(
        sa.text(
            """
            UPDATE public.outbox_invoices
            SET invoice_id = COALESCE(
                    invoice_id,
                    NULLIF(payload ->> 'invoice_id', '')::integer
                ),
                correlation_id = COALESCE(
                    correlation_id,
                    'legacy-outbox-' || id::text
                ),
                created_at = COALESCE(created_at, CURRENT_TIMESTAMP)
            """
        )
    )
    if "ix_outbox_invoices_invoice_id" not in _indexes("outbox_invoices"):
        op.create_index(
            "ix_outbox_invoices_invoice_id",
            "outbox_invoices",
            ["invoice_id"],
            schema="public",
        )
    if "uq_outbox_invoices_correlation_id" not in _indexes(
        "outbox_invoices"
    ):
        op.create_index(
            "uq_outbox_invoices_correlation_id",
            "outbox_invoices",
            ["correlation_id"],
            unique=True,
            schema="public",
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("fiscal_closures", schema="public"):
        op.create_table(
            "fiscal_closures",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("period_type", sa.String(20), nullable=False),
            sa.Column("period_from", sa.Date(), nullable=False),
            sa.Column("period_to", sa.Date(), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("total_sales_amount", sa.Integer(), nullable=False),
            sa.Column("total_authorized_amount", sa.Integer(), nullable=False),
            sa.Column("total_pending_amount", sa.Integer(), nullable=False),
            sa.Column("total_rejected_amount", sa.Integer(), nullable=False),
            sa.Column("sales_count", sa.Integer(), nullable=False),
            sa.Column("invoices_count", sa.Integer(), nullable=False),
            sa.Column("authorized_invoices_count", sa.Integer(), nullable=False),
            sa.Column("pending_invoices_count", sa.Integer(), nullable=False),
            sa.Column("rejected_invoices_count", sa.Integer(), nullable=False),
            sa.Column("sales_without_invoice_count", sa.Integer(), nullable=False),
            sa.Column("declared_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "period_to >= period_from",
                name="ck_fiscal_closures_period",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "period_type",
                "period_from",
                "period_to",
                name="uq_fiscal_closures_period",
            ),
            schema="public",
        )
        op.create_index(
            "ix_fiscal_closures_period_from",
            "fiscal_closures",
            ["period_from"],
            schema="public",
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("fiscal_closure_invoices", schema="public"):
        op.create_table(
            "fiscal_closure_invoices",
            sa.Column("closure_id", sa.Integer(), nullable=False),
            sa.Column("invoice_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["closure_id"],
                ["public.fiscal_closures.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["invoice_id"],
                ["public.invoices.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("closure_id", "invoice_id"),
            schema="public",
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table(
        "closure_validation_issues",
        schema="public",
    ):
        op.create_table(
            "closure_validation_issues",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("closure_id", sa.Integer(), nullable=True),
            sa.Column("period_from", sa.Date(), nullable=False),
            sa.Column("period_to", sa.Date(), nullable=False),
            sa.Column("issue_type", sa.String(60), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("sale_id", sa.Integer(), nullable=True),
            sa.Column("invoice_id", sa.Integer(), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("suggested_action", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["closure_id"],
                ["public.fiscal_closures.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["sale_id"],
                ["public.closings.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["invoice_id"],
                ["public.invoices.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema="public",
        )
        op.create_index(
            "ix_closure_validation_issues_closure_id",
            "closure_validation_issues",
            ["closure_id"],
            schema="public",
        )
        op.create_index(
            "ix_closure_validation_issues_period_from",
            "closure_validation_issues",
            ["period_from"],
            schema="public",
        )
        op.create_index(
            "ix_closure_validation_issues_issue_type",
            "closure_validation_issues",
            ["issue_type"],
            schema="public",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("closure_validation_issues", schema="public"):
        op.drop_table("closure_validation_issues", schema="public")
    if inspector.has_table("fiscal_closure_invoices", schema="public"):
        op.drop_table("fiscal_closure_invoices", schema="public")
    if inspector.has_table("fiscal_closures", schema="public"):
        op.drop_table("fiscal_closures", schema="public")

    outbox_columns = _columns("outbox_invoices")
    if "published_at" in outbox_columns:
        op.drop_column("outbox_invoices", "published_at", schema="public")
    if "created_at" in outbox_columns:
        op.drop_column("outbox_invoices", "created_at", schema="public")
    if "correlation_id" in outbox_columns:
        op.drop_index(
            "uq_outbox_invoices_correlation_id",
            table_name="outbox_invoices",
            schema="public",
        )
        op.drop_column("outbox_invoices", "correlation_id", schema="public")
    if "invoice_id" in outbox_columns:
        op.drop_index(
            "ix_outbox_invoices_invoice_id",
            table_name="outbox_invoices",
            schema="public",
        )
        op.drop_constraint(
            "fk_outbox_invoices_invoice_id",
            "outbox_invoices",
            schema="public",
            type_="foreignkey",
        )
        op.drop_column("outbox_invoices", "invoice_id", schema="public")

    for column_name in (
        "worker_id",
        "correlation_id",
        "error_reason",
        "status_after",
        "status_before",
        "attempt_number",
    ):
        if column_name in _columns("invoice_attempts"):
            op.drop_column(
                "invoice_attempts",
                column_name,
                schema="public",
            )

    bind.execute(
        sa.text(
            """
            UPDATE public.invoices
            SET status = CASE status
                WHEN 'INVOICE_PENDING' THEN 'pendiente'
                WHEN 'INVOICE_QUEUED' THEN 'pendiente'
                WHEN 'INVOICE_AUTHORIZING' THEN 'pendiente'
                WHEN 'INVOICE_AUTHORIZED' THEN 'autorizada'
                WHEN 'INVOICE_REJECTED' THEN 'rechazada'
                WHEN 'INVOICE_CANCELLED' THEN 'anulada'
                WHEN 'INVOICE_RETRY_PENDING' THEN 'pendiente'
                ELSE status
            END
            """
        )
    )
    for column_name in (
        "updated_at",
        "created_at",
        "rejection_reason",
        "authorization_date",
    ):
        if column_name in _columns("invoices"):
            op.drop_column("invoices", column_name, schema="public")

    if "invoicing_status" in _columns("closings"):
        op.drop_column("closings", "invoicing_status", schema="public")
