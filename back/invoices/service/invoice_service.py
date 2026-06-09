from datetime import date, datetime
from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db.db_models import (
    ClosingsModel,
    InvoiceAttemptModel,
    InvoiceModel,
)
from invoices.afip_client import (
    AfipClient,
    AfipUnavailableError,
    get_afip_client,
)
from invoices.models.invoice_models import (
    InvoiceAttemptResponse,
    InvoiceReportResponse,
    InvoiceResponse,
    RetryInvoicePeriodRequest,
    RetryInvoicePeriodResponse,
)
from invoices.repository.invoice_repository import InvoiceRepository
from shared.time_utils import day_bounds, local_now
from shared.utils import commit_session


class InvoiceService:
    POINT_OF_SALE = 1
    VOUCHER_TYPE = "Factura B"
    CUIT = "20-12345678-9"
    BUSINESS_NAME = "Estación de Cervezas Bejas"

    def __init__(
        self,
        session: Session,
        afip_client: AfipClient | None = None,
    ):
        self.session = session
        self.repository = InvoiceRepository(session)
        self.afip_client = afip_client or get_afip_client()

    @staticmethod
    def _response(invoice: InvoiceModel) -> InvoiceResponse:
        return InvoiceResponse(
            id=invoice.id,
            closing_id=invoice.closing_id,
            voucher_type=invoice.voucher_type,
            point_of_sale=invoice.point_of_sale,
            voucher_number=invoice.voucher_number,
            display_number=(
                f"{invoice.point_of_sale:05d}-"
                f"{invoice.voucher_number:08d}"
            ),
            issued_at=invoice.issued_at,
            cae=invoice.cae,
            cae_expiration=invoice.cae_expiration,
            status=invoice.status,
            attempts=[
                InvoiceAttemptResponse(
                    id=attempt.id,
                    attempted_at=attempt.attempted_at,
                    success=attempt.success,
                    error=attempt.error,
                )
                for attempt in invoice.attempts
            ],
        )

    def _request_payload(
        self,
        invoice: InvoiceModel,
        closing: ClosingsModel,
    ) -> dict:
        return {
            "request_id": (
                f"closing-{closing.id}-attempt-{len(invoice.attempts) + 1}"
            ),
            "point_of_sale": invoice.point_of_sale,
            "voucher_type": invoice.voucher_type,
            "voucher_number": invoice.voucher_number,
            "issued_at": invoice.issued_at.isoformat(),
            "total": closing.total,
            "table_number": closing.table_number,
        }

    def _attempt_authorization(
        self,
        invoice: InvoiceModel,
        closing: ClosingsModel,
    ) -> bool:
        request_payload = self._request_payload(invoice, closing)
        attempt = InvoiceAttemptModel(
            attempted_at=local_now(),
            success=False,
            request_payload=request_payload,
        )
        invoice.afip_request = request_payload
        try:
            authorization = self.afip_client.authorize(request_payload)
            attempt.success = True
            attempt.response_payload = authorization.response_payload
            invoice.status = "autorizada"
            invoice.cae = authorization.cae
            invoice.cae_expiration = authorization.cae_expiration
            invoice.afip_response = authorization.response_payload
            return True
        except AfipUnavailableError as error:
            attempt.error = str(error)
            attempt.response_payload = {
                "error": str(error),
                "mock": True,
            }
            invoice.status = "pendiente"
            invoice.afip_response = attempt.response_payload
            return False
        finally:
            invoice.attempts.append(attempt)

    def create_for_closing(
        self,
        closing: ClosingsModel,
    ) -> tuple[InvoiceModel, bool]:
        invoice = InvoiceModel(
            closing=closing,
            voucher_type=self.VOUCHER_TYPE,
            point_of_sale=self.POINT_OF_SALE,
            voucher_number=self.repository.next_voucher_number(
                self.POINT_OF_SALE,
                self.VOUCHER_TYPE,
            ),
            issued_at=local_now(),
            status="pendiente",
        )
        self.repository.add(invoice)
        self.session.flush()
        authorized = self._attempt_authorization(invoice, closing)
        return invoice, authorized

    def list_invoices(
        self,
        report_date: date | None = None,
    ) -> list[InvoiceResponse]:
        start = end = None
        if report_date is not None:
            start, end = day_bounds(report_date)
        return [
            self._response(invoice)
            for invoice in self.repository.get_all(start, end)
        ]

    def get_invoice(self, invoice_id: int) -> InvoiceResponse:
        invoice = self.repository.get_by_id(invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Factura no encontrada",
            )
        return self._response(invoice)

    def retry(self, invoice_id: int) -> InvoiceResponse:
        invoice = self.repository.get_by_id(invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Factura no encontrada",
            )
        if invoice.status == "autorizada":
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="La factura ya está autorizada",
            )

        self._attempt_authorization(invoice, invoice.closing)
        commit_session(self.session)
        return self.get_invoice(invoice_id)

    @staticmethod
    def _period_bounds(
        payload: RetryInvoicePeriodRequest,
    ) -> tuple[datetime, datetime]:
        if payload.period == "diario":
            return day_bounds(payload.date)

        start = datetime(payload.year, payload.month, 1)
        end = (
            datetime(payload.year + 1, 1, 1)
            if payload.month == 12
            else datetime(payload.year, payload.month + 1, 1)
        )
        return start, end

    def retry_period(
        self,
        payload: RetryInvoicePeriodRequest,
    ) -> RetryInvoicePeriodResponse:
        start, end = self._period_bounds(payload)
        invoices = self.repository.get_pending_by_closing_period(start, end)
        if not invoices:
            return RetryInvoicePeriodResponse(
                status="sin_pendientes",
                message="No hay facturas pendientes para el período seleccionado",
                processed_count=0,
                authorized_count=0,
                failed_count=0,
                invoices=[],
            )

        authorized_count = 0
        for invoice in invoices:
            if self._attempt_authorization(invoice, invoice.closing):
                authorized_count += 1
        commit_session(self.session)

        processed_count = len(invoices)
        failed_count = processed_count - authorized_count
        if authorized_count == processed_count:
            status = "completado"
            message = "Todas las facturas pendientes fueron autorizadas"
        elif authorized_count == 0:
            status = "error"
            message = "AFIP no autorizó ninguna factura del período"
        else:
            status = "parcial"
            message = (
                "Algunas facturas fueron autorizadas y otras continúan "
                "pendientes"
            )

        return RetryInvoicePeriodResponse(
            status=status,
            message=message,
            processed_count=processed_count,
            authorized_count=authorized_count,
            failed_count=failed_count,
            invoices=[self._response(invoice) for invoice in invoices],
        )

    def report(self, report_date: date) -> InvoiceReportResponse:
        invoices = self.list_invoices(report_date)
        authorized = [
            invoice for invoice in invoices
            if invoice.status == "autorizada"
        ]
        total = sum(
            self.repository.get_by_id(invoice.id).closing.total
            for invoice in authorized
        )
        return InvoiceReportResponse(
            date=report_date,
            cuit=self.CUIT,
            business_name=self.BUSINESS_NAME,
            total_invoiced=total,
            invoice_count=len(authorized),
            invoices=authorized,
        )
