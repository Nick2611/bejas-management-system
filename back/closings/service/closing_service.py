from decimal import Decimal, ROUND_HALF_UP
from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from closings.models.closing_models import (
    CashClosingRevisionResponse,
    CashClosingResponse,
    CloseTableRequest,
    CloseTableResponse,
    ClosingItemResponse,
    ClosingPaymentResponse,
    ClosingResponse,
    CreateCashClosingRequest,
    UpdateCashClosingRequest,
    MonthlyClosingSummaryResponse,
)
from closings.repository.closing_repository import (
    CashClosingRepository,
    ClosingRepository,
)
from db.db_models import (
    CashClosingRevisionModel,
    CashClosingModel,
    ClosingItemModel,
    ClosingPaymentModel,
    ClosingsModel,
)
from invoices.afip_client import AfipClient
from invoices.service.invoice_service import InvoiceService
from shared.time_utils import day_bounds, local_now
from shared.utils import commit_session
from tables.repository.table_repository import TableRepository


class ClosingService:
    def __init__(
        self,
        session: Session,
        afip_client: AfipClient | None = None,
    ):
        self.session = session
        self.repository = ClosingRepository(session)
        self.cash_repository = CashClosingRepository(session)
        self.table_repository = TableRepository(session)
        self.invoice_service = InvoiceService(session, afip_client)

    def _response(self, closing: ClosingsModel) -> ClosingResponse:
        invoice = (
            self.invoice_service._response(closing.invoice)
            if closing.invoice is not None
            else None
        )
        amount_received = sum(payment.amount for payment in closing.payments)
        return ClosingResponse(
            id=closing.id,
            table_number=closing.table_number,
            table_name=closing.table_name,
            opening_time=closing.opening_time,
            closing_time=closing.closing_time,
            people=closing.people,
            served_by=closing.served_by,
            subtotal=closing.subtotal,
            discount=closing.discount,
            total=closing.total,
            amount_received=amount_received,
            change=max(amount_received - closing.total, 0),
            status=closing.status,
            cash_closing_id=closing.cash_closing_id,
            items=[
                ClosingItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    product_type=item.product_type,
                    unit=item.unit,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    subtotal=item.subtotal,
                )
                for item in closing.items
            ],
            payments=[
                ClosingPaymentResponse(
                    id=payment.id,
                    method=payment.method,
                    amount=payment.amount,
                )
                for payment in closing.payments
            ],
            invoice=invoice,
        )

    @staticmethod
    def _payment_totals(sales: list[ClosingsModel]) -> dict[str, int]:
        totals = {
            "efectivo": 0,
            "tarjeta_credito": 0,
            "tarjeta_debito": 0,
            "mercado_pago": 0,
        }
        for sale in sales:
            sale_totals = {method: 0 for method in totals}
            for payment in sale.payments:
                sale_totals[payment.method] += payment.amount

            excess = max(sum(sale_totals.values()) - sale.total, 0)
            for method in (
                "efectivo",
                "mercado_pago",
                "tarjeta_debito",
                "tarjeta_credito",
            ):
                if excess == 0:
                    break
                returned = min(sale_totals[method], excess)
                sale_totals[method] -= returned
                excess -= returned

            for method, amount in sale_totals.items():
                totals[method] += amount
        return totals

    def close_table(
        self,
        table_number: int,
        payload: CloseTableRequest,
        user_id: int,
    ) -> CloseTableResponse:
        table = self.table_repository.get_by_number(table_number)
        if table is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"La mesa {table_number} no existe",
            )
        subtotal = sum(
            item.quantity * item.curr_price for item in table.items
        )
        has_cash = any(
            payment.method == "efectivo" for payment in payload.payments
        )
        discount = (
            int(
                (Decimal(subtotal) * Decimal("0.10")).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            )
            if has_cash
            else 0
        )
        total = subtotal - discount
        paid_total = sum(payment.amount for payment in payload.payments)
        if total > 0 and not payload.payments:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail="Debe indicar al menos un método de pago",
            )
        if paid_total < total:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail=(
                    f"Los pagos suman {paid_total}, pero el total mínimo es {total}"
                ),
            )

        closing_time = local_now()
        if closing_time < table.opening_time:
            closing_time = table.opening_time

        closing = ClosingsModel(
            table_id=table.id,
            table_number=table.table_number,
            table_name=table.table_name,
            opening_time=table.opening_time,
            closing_time=closing_time,
            people=table.people,
            served_by=user_id,
            subtotal=subtotal,
            discount=discount,
            total=total,
            status="cerrada",
            items=[
                ClosingItemModel(
                    product_id=item.product_id,
                    product_name=item.product.name,
                    product_type=item.product.type,
                    unit=item.product.unit,
                    quantity=item.quantity,
                    unit_price=item.curr_price,
                    subtotal=item.quantity * item.curr_price,
                )
                for item in table.items
            ],
            payments=[
                ClosingPaymentModel(
                    method=payment.method,
                    amount=payment.amount,
                )
                for payment in payload.payments
            ],
        )
        self.repository.add(closing)

        electronic_payment = any(
            payment.method != "efectivo" for payment in payload.payments
        )
        afip_authorized: bool | None = None
        warning: str | None = None
        try:
            self.session.flush()
            if electronic_payment and total > 0:
                _, afip_authorized = self.invoice_service.create_for_closing(
                    closing
                )
                if not afip_authorized:
                    warning = (
                        "La venta se cerró, pero AFIP no respondió. "
                        "La factura quedó pendiente."
                    )

            table.items.clear()
            table.people = 0
            table.opening_time = closing_time
            commit_session(self.session)
        except Exception:
            self.session.rollback()
            raise

        persisted = self.repository.get_by_id(closing.id)
        return CloseTableResponse(
            closing=self._response(persisted),
            afip_authorized=afip_authorized,
            warning=warning,
        )

    def list_closings(
        self,
        start_date=None,
        end_date=None,
        status=None,
    ) -> list[ClosingResponse]:
        start = day_bounds(start_date)[0] if start_date else None
        end = day_bounds(end_date)[1] if end_date else None
        return [
            self._response(closing)
            for closing in self.repository.get_all(start, end, status)
        ]

    def get_closing(self, closing_id: int) -> ClosingResponse:
        closing = self.repository.get_by_id(closing_id)
        if closing is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Venta no encontrada",
            )
        return self._response(closing)

    def _cash_response(
        self,
        cash_closing: CashClosingModel,
    ) -> CashClosingResponse:
        totals = self._payment_totals(cash_closing.sales)
        return CashClosingResponse(
            id=cash_closing.id,
            business_date=cash_closing.business_date,
            closed_at=cash_closing.closed_at,
            closed_by_id=cash_closing.closed_by_id,
            total_sales=cash_closing.total_sales,
            expected_cash=cash_closing.expected_cash,
            counted_cash=cash_closing.counted_cash,
            difference=cash_closing.difference,
            status=cash_closing.status,
            notes=cash_closing.notes,
            sales_count=len(cash_closing.sales),
            total_credit_card=totals["tarjeta_credito"],
            total_debit_card=totals["tarjeta_debito"],
            total_mercado_pago=totals["mercado_pago"],
        )

    def create_cash_closing(
        self,
        payload: CreateCashClosingRequest,
        user_id: int,
    ) -> CashClosingResponse:
        if self.cash_repository.get_by_date(payload.business_date):
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="Ya existe un cierre para esa fecha",
            )
        start, end = day_bounds(payload.business_date)
        sales = self.repository.get_unclosed_sales(start, end)
        if not sales:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="No hay ventas pendientes de cierre para esa fecha",
            )
        totals = self._payment_totals(sales)
        total_sales = sum(sale.total for sale in sales)
        expected_cash = totals["efectivo"]
        cash_closing = CashClosingModel(
            business_date=payload.business_date,
            closed_at=local_now(),
            closed_by_id=user_id,
            total_sales=total_sales,
            expected_cash=expected_cash,
            counted_cash=payload.counted_cash,
            difference=payload.counted_cash - expected_cash,
            status="cerrado",
            notes=payload.notes,
            sales=sales,
        )
        self.cash_repository.add(cash_closing)
        commit_session(self.session)
        return self._cash_response(
            self.cash_repository.get_by_date(payload.business_date)
        )

    def list_cash_closings(self) -> list[CashClosingResponse]:
        return [
            self._cash_response(cash_closing)
            for cash_closing in self.cash_repository.get_all()
        ]

    @staticmethod
    def _revision_response(
        revision: CashClosingRevisionModel,
    ) -> CashClosingRevisionResponse:
        return CashClosingRevisionResponse(
            id=revision.id,
            cash_closing_id=revision.cash_closing_id,
            changed_by_id=revision.changed_by_id,
            changed_at=revision.changed_at,
            previous_counted_cash=revision.previous_counted_cash,
            new_counted_cash=revision.new_counted_cash,
            previous_notes=revision.previous_notes,
            new_notes=revision.new_notes,
        )

    def update_cash_closing(
        self,
        cash_closing_id: int,
        payload: UpdateCashClosingRequest,
        user_id: int,
    ) -> CashClosingResponse:
        cash_closing = self.cash_repository.get_by_id(cash_closing_id)
        if cash_closing is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Cierre de caja no encontrado",
            )

        previous_counted_cash = cash_closing.counted_cash
        previous_notes = cash_closing.notes
        if "counted_cash" in payload.model_fields_set:
            cash_closing.counted_cash = payload.counted_cash
        if "notes" in payload.model_fields_set:
            cash_closing.notes = payload.notes

        if (
            cash_closing.counted_cash == previous_counted_cash
            and cash_closing.notes == previous_notes
        ):
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="El cierre no contiene cambios",
            )

        cash_closing.difference = (
            cash_closing.counted_cash - cash_closing.expected_cash
        )
        revision = CashClosingRevisionModel(
            cash_closing=cash_closing,
            changed_by_id=user_id,
            changed_at=local_now(),
            previous_counted_cash=previous_counted_cash,
            new_counted_cash=cash_closing.counted_cash,
            previous_notes=previous_notes,
            new_notes=cash_closing.notes,
        )
        self.session.add(revision)
        commit_session(self.session)
        return self._cash_response(
            self.cash_repository.get_by_id(cash_closing_id)
        )

    def list_cash_closing_revisions(
        self,
        cash_closing_id: int,
    ) -> list[CashClosingRevisionResponse]:
        if self.cash_repository.get_by_id(cash_closing_id) is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Cierre de caja no encontrado",
            )
        return [
            self._revision_response(revision)
            for revision in self.cash_repository.get_revisions(cash_closing_id)
        ]

    def monthly_summary(
        self,
        year: int,
        month: int,
    ) -> MonthlyClosingSummaryResponse:
        sales = self.repository.get_month_sales(year, month)
        totals = self._payment_totals(sales)
        total_sales = sum(sale.total for sale in sales)
        active_days = len({sale.closing_time.date() for sale in sales})
        return MonthlyClosingSummaryResponse(
            year=year,
            month=month,
            total_sales=total_sales,
            sales_count=len(sales),
            active_days=active_days,
            daily_average=(
                int(round(total_sales / active_days)) if active_days else 0
            ),
            total_cash=totals["efectivo"],
            total_credit_card=totals["tarjeta_credito"],
            total_debit_card=totals["tarjeta_debito"],
            total_mercado_pago=totals["mercado_pago"],
        )
