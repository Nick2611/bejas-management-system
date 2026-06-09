"""Create the existing application schema without replacing existing tables."""

from alembic import op
from sqlalchemy import text

from db.db_models import Base


revision = "0001_existing_schema"
down_revision = None
branch_labels = None
depends_on = None

BASE_TABLES = (
    "public.user",
    "public.products",
    "public.open_tables",
    "public.open_table_items",
    "public.cash_closings",
    "public.closings",
    "public.closing_items",
    "public.closing_payments",
    "public.invoices",
    "public.sales_goals",
    "public.stock_movements",
)


def upgrade() -> None:
    op.get_bind().execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    metadata = Base.metadata
    metadata.create_all(
        bind=op.get_bind(),
        tables=[metadata.tables[name] for name in BASE_TABLES],
        checkfirst=True,
    )


def downgrade() -> None:
    metadata = Base.metadata
    metadata.drop_all(
        bind=op.get_bind(),
        tables=[metadata.tables[name] for name in reversed(BASE_TABLES)],
        checkfirst=True,
    )
