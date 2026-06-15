from datetime import date, datetime

from sqlalchemy import delete, extract, select
from sqlalchemy.orm import Session, selectinload

from db.db_models import (
    CashClosingModel,
    CashClosingRevisionModel,
    ClosureValidationIssueModel,
    ClosingsModel,
    FiscalClosureModel,
    InvoiceModel,
    fiscal_closure_invoices_table,
    invoice_closings_table,
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
            selectinload(ClosingsModel.invoice).selectinload(
                InvoiceModel.closings
            ),
        )

    def get_by_id(self, closing_id: int) -> ClosingsModel | None:
        statement = (
            select(ClosingsModel)
            .where(ClosingsModel.id == closing_id)
            .options(*self._options())
        )
        return self.session.scalar(statement)

    def get_by_id_for_update(
        self,
        closing_id: int,
    ) -> ClosingsModel | None:
        statement = (
            select(ClosingsModel)
            .where(ClosingsModel.id == closing_id)
            .options(*self._options())
            .with_for_update(of=ClosingsModel)
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
            statement = statement.where(
                ClosingsModel.business_date >= start.date()
            )
        if end is not None:
            statement = statement.where(
                ClosingsModel.business_date < end.date()
            )
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
                ClosingsModel.business_date >= start.date(),
                ClosingsModel.business_date < end.date(),
                ClosingsModel.status == "cerrada",
                ClosingsModel.cash_closing_id.is_(None),
            )
            .options(
                selectinload(ClosingsModel.payments),
                selectinload(ClosingsModel.invoice).selectinload(
                    InvoiceModel.attempts
                ),
                selectinload(ClosingsModel.invoice).selectinload(
                    InvoiceModel.closings
                ),
            )
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
                extract("year", ClosingsModel.business_date) == year,
                extract("month", ClosingsModel.business_date) == month,
                ClosingsModel.status == "cerrada",
            )
            .options(selectinload(ClosingsModel.payments))
        )
        return list(self.session.scalars(statement).unique().all())

    def get_period_sales(
        self,
        start: datetime,
        end: datetime,
    ) -> list[ClosingsModel]:
        statement = (
            select(ClosingsModel)
            .where(
                ClosingsModel.business_date >= start.date(),
                ClosingsModel.business_date < end.date(),
            )
            .options(
                *self._options(),
                selectinload(ClosingsModel.cash_closing).selectinload(
                    CashClosingModel.sales
                ).selectinload(ClosingsModel.payments),
            )
            .order_by(
                ClosingsModel.business_date,
                ClosingsModel.closing_time,
                ClosingsModel.id,
            )
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
            .order_by(
                CashClosingModel.closed_at.desc(),
                CashClosingModel.id.desc(),
            )
            .limit(1)
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


class FiscalClosureRepository(BaseRepository[FiscalClosureModel]):
    def __init__(self, session: Session):
        super().__init__(model=FiscalClosureModel, session=session)

    @staticmethod
    def _options():
        return (
            selectinload(FiscalClosureModel.invoices).selectinload(
                InvoiceModel.attempts
            ),
            selectinload(FiscalClosureModel.invoices).selectinload(
                InvoiceModel.closings
            ),
            selectinload(FiscalClosureModel.validation_issues),
        )

    def get_declared_period(
        self,
        period_type: str,
        period_from: date,
        period_to: date,
    ) -> FiscalClosureModel | None:
        statement = (
            select(FiscalClosureModel)
            .where(
                FiscalClosureModel.period_type == period_type,
                FiscalClosureModel.period_from == period_from,
                FiscalClosureModel.period_to == period_to,
                FiscalClosureModel.status == "CLOSURE_DECLARED",
            )
            .options(*self._options())
        )
        return self.session.scalar(statement)

    def get_declared_for_invoice(
        self,
        invoice_id: int,
    ) -> FiscalClosureModel | None:
        statement = (
            select(FiscalClosureModel)
            .join(
                fiscal_closure_invoices_table,
                fiscal_closure_invoices_table.c.closure_id
                == FiscalClosureModel.id,
            )
            .where(
                fiscal_closure_invoices_table.c.invoice_id == invoice_id,
                FiscalClosureModel.status == "CLOSURE_DECLARED",
            )
            .order_by(
                FiscalClosureModel.declared_at.desc(),
                FiscalClosureModel.id.desc(),
            )
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_declared_for_sale(
        self,
        sale_id: int,
    ) -> FiscalClosureModel | None:
        statement = (
            select(FiscalClosureModel)
            .join(
                fiscal_closure_invoices_table,
                fiscal_closure_invoices_table.c.closure_id
                == FiscalClosureModel.id,
            )
            .join(
                invoice_closings_table,
                invoice_closings_table.c.invoice_id
                == fiscal_closure_invoices_table.c.invoice_id,
            )
            .where(
                invoice_closings_table.c.closing_id == sale_id,
                FiscalClosureModel.status == "CLOSURE_DECLARED",
            )
            .order_by(
                FiscalClosureModel.declared_at.desc(),
                FiscalClosureModel.id.desc(),
            )
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_declared_for_cash_closing(
        self,
        cash_closing_id: int,
    ) -> FiscalClosureModel | None:
        statement = (
            select(FiscalClosureModel)
            .join(
                fiscal_closure_invoices_table,
                fiscal_closure_invoices_table.c.closure_id
                == FiscalClosureModel.id,
            )
            .join(
                invoice_closings_table,
                invoice_closings_table.c.invoice_id
                == fiscal_closure_invoices_table.c.invoice_id,
            )
            .join(
                ClosingsModel,
                ClosingsModel.id == invoice_closings_table.c.closing_id,
            )
            .where(
                ClosingsModel.cash_closing_id == cash_closing_id,
                FiscalClosureModel.status == "CLOSURE_DECLARED",
            )
            .order_by(
                FiscalClosureModel.declared_at.desc(),
                FiscalClosureModel.id.desc(),
            )
            .limit(1)
        )
        return self.session.scalar(statement)

    def get_by_id(
        self,
        closure_id: int,
    ) -> FiscalClosureModel | None:
        statement = (
            select(FiscalClosureModel)
            .where(FiscalClosureModel.id == closure_id)
            .options(*self._options())
        )
        return self.session.scalar(statement)

    def replace_period_issues(
        self,
        period_from: date,
        period_to: date,
        issues: list[ClosureValidationIssueModel],
    ) -> None:
        self.session.execute(
            delete(ClosureValidationIssueModel).where(
                ClosureValidationIssueModel.closure_id.is_(None),
                ClosureValidationIssueModel.period_from == period_from,
                ClosureValidationIssueModel.period_to == period_to,
            )
        )
        self.session.add_all(issues)
