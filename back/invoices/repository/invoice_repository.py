from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.db_models import ClosingsModel, InvoiceModel
from shared.shared_repository import BaseRepository


class InvoiceRepository(BaseRepository[InvoiceModel]):
    def __init__(self, session: Session):
        super().__init__(model=InvoiceModel, session=session)

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
            .options(
                selectinload(InvoiceModel.attempts),
                selectinload(InvoiceModel.closing),
            )
        )
        return self.session.scalar(statement)

    def get_all(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[InvoiceModel]:
        statement = (
            select(InvoiceModel)
            .options(
                selectinload(InvoiceModel.attempts),
                selectinload(InvoiceModel.closing),
            )
            .order_by(InvoiceModel.issued_at.desc())
        )
        if start is not None:
            statement = statement.where(InvoiceModel.issued_at >= start)
        if end is not None:
            statement = statement.where(InvoiceModel.issued_at < end)
        return list(self.session.scalars(statement).unique().all())

    def get_pending_by_closing_period(
        self,
        start: datetime,
        end: datetime,
    ) -> list[InvoiceModel]:
        statement = (
            select(InvoiceModel)
            .join(InvoiceModel.closing)
            .where(
                InvoiceModel.status == "pendiente",
                ClosingsModel.closing_time >= start,
                ClosingsModel.closing_time < end,
            )
            .options(
                selectinload(InvoiceModel.attempts),
                selectinload(InvoiceModel.closing),
            )
            .order_by(ClosingsModel.closing_time, InvoiceModel.id)
        )
        return list(self.session.scalars(statement).unique().all())
