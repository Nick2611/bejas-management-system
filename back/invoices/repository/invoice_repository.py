from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.db_models import (
    ClosingsModel,
    InvoiceModel,
    OutboxModel,
    invoice_closings_table,
)
from shared.shared_repository import BaseRepository


class InvoiceRepository(BaseRepository[InvoiceModel]):
    def __init__(self, session: Session):
        super().__init__(model=InvoiceModel, session=session)

    @staticmethod
    def _options():
        return (
            selectinload(InvoiceModel.attempts),
            selectinload(InvoiceModel.closings),
        )

    def next_voucher_number(
        self,
        point_of_sale: int,
        voucher_type: str,
    ) -> int:
        statement = select(
            func.coalesce(func.max(InvoiceModel.voucher_number), 0) + 1
        ).where(
            InvoiceModel.point_of_sale == point_of_sale,
            InvoiceModel.voucher_type == voucher_type,
        )
        return int(self.session.scalar(statement) or 1)

    def get_by_id(self, invoice_id: int) -> InvoiceModel | None:
        statement = (
            select(InvoiceModel)
            .where(InvoiceModel.id == invoice_id)
            .options(*self._options())
        )
        return self.session.scalar(statement)

    def get_by_id_for_update(self, invoice_id: int) -> InvoiceModel | None:
        statement = (
            select(InvoiceModel)
            .where(InvoiceModel.id == invoice_id)
            .options(*self._options())
            .with_for_update(of=InvoiceModel)
        )
        return self.session.scalar(statement)

    def get_all(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[InvoiceModel]:
        statement = (
            select(InvoiceModel)
            .options(*self._options())
            .order_by(InvoiceModel.issued_at.desc())
        )
        if start is not None:
            statement = statement.where(InvoiceModel.issued_at >= start)
        if end is not None:
            statement = statement.where(InvoiceModel.issued_at < end)
        return list(self.session.scalars(statement).unique().all())

    def get_for_sales_period(
        self,
        start: datetime,
        end: datetime,
    ) -> list[InvoiceModel]:
        statement = (
            select(InvoiceModel)
            .join(
                invoice_closings_table,
                invoice_closings_table.c.invoice_id == InvoiceModel.id,
            )
            .join(
                ClosingsModel,
                ClosingsModel.id == invoice_closings_table.c.closing_id,
            )
            .where(
                ClosingsModel.business_date >= start.date(),
                ClosingsModel.business_date < end.date(),
            )
            .options(*self._options())
            .order_by(InvoiceModel.id)
        )
        return list(self.session.scalars(statement).unique().all())

    def get_orphans_issued_in_period(
        self,
        start: datetime,
        end: datetime,
    ) -> list[InvoiceModel]:
        statement = (
            select(InvoiceModel)
            .where(
                InvoiceModel.issued_at >= start,
                InvoiceModel.issued_at < end,
                ~InvoiceModel.closings.any(),
            )
            .options(*self._options())
            .order_by(InvoiceModel.id)
        )
        return list(self.session.scalars(statement).unique().all())

    def get_retryable_for_period(
        self,
        start: datetime,
        end: datetime,
        statuses: list[str],
    ) -> list[InvoiceModel]:
        statement = (
            select(InvoiceModel)
            .join(
                invoice_closings_table,
                invoice_closings_table.c.invoice_id == InvoiceModel.id,
            )
            .join(
                ClosingsModel,
                ClosingsModel.id == invoice_closings_table.c.closing_id,
            )
            .where(
                ClosingsModel.business_date >= start.date(),
                ClosingsModel.business_date < end.date(),
                InvoiceModel.status.in_(statuses),
            )
            .options(*self._options())
            .order_by(InvoiceModel.id)
            .with_for_update(of=InvoiceModel, skip_locked=True)
        )
        return list(self.session.scalars(statement).unique().all())

    def get_duplicate_sale_invoice_rows(
        self,
        start: datetime,
        end: datetime,
    ) -> list[tuple[int, int]]:
        statement = (
            select(
                invoice_closings_table.c.closing_id,
                func.count(invoice_closings_table.c.invoice_id),
            )
            .join(
                ClosingsModel,
                ClosingsModel.id == invoice_closings_table.c.closing_id,
            )
            .where(
                ClosingsModel.business_date >= start.date(),
                ClosingsModel.business_date < end.date(),
            )
            .group_by(invoice_closings_table.c.closing_id)
            .having(func.count(invoice_closings_table.c.invoice_id) > 1)
        )
        return [
            (int(sale_id), int(invoice_count))
            for sale_id, invoice_count in self.session.execute(statement)
        ]

    def get_outbox_by_id(
        self,
        outbox_id: int,
        *,
        for_update: bool = False,
    ) -> OutboxModel | None:
        statement = select(OutboxModel).where(OutboxModel.id == outbox_id)
        if for_update:
            statement = statement.with_for_update(of=OutboxModel)
        return self.session.scalar(statement)

    def get_unprocessed_outboxes(self) -> list[OutboxModel]:
        statement = (
            select(OutboxModel)
            .where(OutboxModel.is_processed.is_(False))
            .order_by(OutboxModel.id)
        )
        return list(self.session.scalars(statement).all())
