from datetime import date, datetime

from sqlalchemy import extract, select
from sqlalchemy.orm import Session, selectinload

from db.db_models import (
    CashClosingModel,
    CashClosingRevisionModel,
    ClosingsModel,
    InvoiceModel,
)
from shared.shared_repository import BaseRepository


class ClosingRepository(BaseRepository[ClosingsModel]):
    def __init__(self, session: Session):
        super().__init__(model=ClosingsModel, session=session)

    @staticmethod
    def _options():
        return (
            selectinload(ClosingsModel.items),
            selectinload(ClosingsModel.payments),
            selectinload(ClosingsModel.invoice).selectinload(
                InvoiceModel.attempts
            ),
        )

    def get_by_id(self, closing_id: int) -> ClosingsModel | None:
        statement = (
            select(ClosingsModel)
            .where(ClosingsModel.id == closing_id)
            .options(*self._options())
        )
        return self.session.scalar(statement)

    def get_all(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
    ) -> list[ClosingsModel]:
        statement = (
            select(ClosingsModel)
            .options(*self._options())
            .order_by(ClosingsModel.closing_time.desc())
        )
        if start is not None:
            statement = statement.where(ClosingsModel.closing_time >= start)
        if end is not None:
            statement = statement.where(ClosingsModel.closing_time < end)
        if status is not None:
            statement = statement.where(ClosingsModel.status == status)
        return list(self.session.scalars(statement).unique().all())

    def get_unclosed_sales(
        self,
        start: datetime,
        end: datetime,
    ) -> list[ClosingsModel]:
        statement = (
            select(ClosingsModel)
            .where(
                ClosingsModel.closing_time >= start,
                ClosingsModel.closing_time < end,
                ClosingsModel.status == "cerrada",
                ClosingsModel.cash_closing_id.is_(None),
            )
            .options(selectinload(ClosingsModel.payments))
        )
        return list(self.session.scalars(statement).unique().all())

    def get_month_sales(
        self,
        year: int,
        month: int,
    ) -> list[ClosingsModel]:
        statement = (
            select(ClosingsModel)
            .where(
                extract("year", ClosingsModel.closing_time) == year,
                extract("month", ClosingsModel.closing_time) == month,
                ClosingsModel.status == "cerrada",
            )
            .options(selectinload(ClosingsModel.payments))
        )
        return list(self.session.scalars(statement).unique().all())


class CashClosingRepository(BaseRepository[CashClosingModel]):
    def __init__(self, session: Session):
        super().__init__(model=CashClosingModel, session=session)

    def get_by_date(self, business_date: date) -> CashClosingModel | None:
        return self.session.scalar(
            select(CashClosingModel)
            .where(CashClosingModel.business_date == business_date)
            .options(
                selectinload(CashClosingModel.sales).selectinload(
                    ClosingsModel.payments
                )
            )
        )

    def get_by_id(self, cash_closing_id: int) -> CashClosingModel | None:
        return self.session.scalar(
            select(CashClosingModel)
            .where(CashClosingModel.id == cash_closing_id)
            .options(
                selectinload(CashClosingModel.sales).selectinload(
                    ClosingsModel.payments
                ),
                selectinload(CashClosingModel.revisions),
            )
        )

    def get_revisions(
        self,
        cash_closing_id: int,
    ) -> list[CashClosingRevisionModel]:
        statement = (
            select(CashClosingRevisionModel)
            .where(
                CashClosingRevisionModel.cash_closing_id == cash_closing_id
            )
            .order_by(CashClosingRevisionModel.changed_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def get_all(self) -> list[CashClosingModel]:
        statement = (
            select(CashClosingModel)
            .options(
                selectinload(CashClosingModel.sales).selectinload(
                    ClosingsModel.payments
                )
            )
            .order_by(CashClosingModel.business_date.desc())
        )
        return list(self.session.scalars(statement).unique().all())
