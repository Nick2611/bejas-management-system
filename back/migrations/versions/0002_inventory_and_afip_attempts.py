"""Add inventory settings and AFIP attempt history."""

from alembic import op

from db.db_models import Base


revision = "0002_inventory_afip"
down_revision = "0001_existing_schema"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "public.product_inventory_settings",
    "public.invoice_attempts",
)


def upgrade() -> None:
    metadata = Base.metadata
    metadata.create_all(
        bind=op.get_bind(),
        tables=[metadata.tables[name] for name in NEW_TABLES],
        checkfirst=True,
    )


def downgrade() -> None:
    metadata = Base.metadata
    metadata.drop_all(
        bind=op.get_bind(),
        tables=[metadata.tables[name] for name in reversed(NEW_TABLES)],
        checkfirst=True,
    )
