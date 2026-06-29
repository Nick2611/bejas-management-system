from datetime import date, datetime, timedelta
from http import HTTPStatus
from typing import Callable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from closings.service.fiscal_period_guard import FiscalPeriodGuard
from db.db_models import (
    CashClosingModel,
    ClosingsModel,
    InvoiceAttemptModel,
    InvoiceModel,
    OutboxModel,
)
from invoices.afip_client import (
    AfipClient,
    AfipRejectedError,
    AfipTemporaryError,
    InvalidFiscalPayloadError,
    get_afip_client,
)
from invoices.models.invoice_models import (
    InvoiceAttemptResponse,
    InvoiceReportResponse,
    InvoiceResponse,
    PendingInvoiceSummaryResponse,
    RetryInvoicePeriodRequest,
    RetryInvoicePeriodResponse,
)
from invoices.repository.invoice_repository import InvoiceRepository
from shared.time_utils import day_bounds, local_now
from shared.utils import commit_session, publish_afip_messages


INVOICE_PENDING = "INVOICE_PENDING"
INVOICE_QUEUED = "INVOICE_QUEUED"
INVOICE_AUTHORIZING = "INVOICE_AUTHORIZING"
INVOICE_AUTHORIZED = "INVOICE_AUTHORIZED"
INVOICE_REJECTED = "INVOICE_REJECTED"
INVOICE_CANCELLED = "INVOICE_CANCELLED"
INVOICE_RETRY_PENDING = "INVOICE_RETRY_PENDING"

RETRYABLE_INVOICE_STATUSES = frozenset(
    {
        INVOICE_PENDING,
        INVOICE_REJECTED,
        INVOICE_RETRY_PENDING,
    }
)
PROCESSABLE_INVOICE_STATUSES = frozenset(
    {
        INVOICE_PENDING,
        INVOICE_QUEUED,
        INVOICE_REJECTED,
        INVOICE_RETRY_PENDING,
    }
)
PENDING_INVOICE_STATUSES = frozenset(
    {
        INVOICE_PENDING,
        INVOICE_QUEUED,
        INVOICE_AUTHORIZING,
        INVOICE_RETRY_PENDING,
    }
)
INVOICE_MESSAGE_SOURCES = frozenset(
    {"sale_close", "ticket", "manual", "retry_period"}
)
# Kept as an import-compatible alias for the existing worker.
AFIP_DECLARATION_SOURCES = INVOICE_MESSAGE_SOURCES

LEGACY_STATUS_MAP = {
    "pendiente": INVOICE_PENDING,
    "autorizada": INVOICE_AUTHORIZED,
    "rechazada": INVOICE_REJECTED,
    "anulada": INVOICE_CANCELLED,
}


class InvoiceService:
    POINT_OF_SALE = 1
    VOUCHER_TYPE = "C"
    CUIT = "20-12345678-9"
    BUSINESS_NAME = "Estación de Cervezas Bejas"
    MESSAGE_SOURCES = INVOICE_MESSAGE_SOURCES
    AUTHORIZING_STALE_AFTER = timedelta(minutes=10)

    def __init__(
        self,
        session: Session,
        afip_client: AfipClient | None = None,
        message_publisher: Callable[[list[dict]], int] | None = None,
    ):
        self.session = session
        self.repository = InvoiceRepository(session)
        self.fiscal_period_guard = FiscalPeriodGuard(session)
        self.afip_client = afip_client or get_afip_client()
        self.message_publisher = message_publisher or publish_afip_messages

    @staticmethod
    def _normalized_status(status: str) -> str:
        return LEGACY_STATUS_MAP.get(status, status)

    @classmethod
    def _response(cls, invoice: InvoiceModel) -> InvoiceResponse:
        closing_ids = sorted(closing.id for closing in invoice.closings)
        attempts = []
        for index, attempt in enumerate(invoice.attempts, 1):
            error_reason = getattr(attempt, "error_reason", None)
            if error_reason is None:
                error_reason = attempt.error
            attempts.append(
                InvoiceAttemptResponse(
                    id=attempt.id,
                    invoice_id=attempt.invoice_id or invoice.id,
                    attempt_number=(
                        getattr(attempt, "attempt_number", None) or index
                    ),
                    attempted_at=attempt.attempted_at,
                    previous_status=(
                        getattr(attempt, "status_before", None)
                        or INVOICE_AUTHORIZING
                    ),
                    new_status=(
                        getattr(attempt, "status_after", None)
                        or (
                            INVOICE_AUTHORIZED
                            if attempt.success
                            else INVOICE_RETRY_PENDING
                        )
                    ),
                    request_payload=attempt.request_payload,
                    response_payload=attempt.response_payload,
                    error_reason=error_reason,
                    worker_id=getattr(attempt, "worker_id", None),
                    correlation_id=getattr(
                        attempt,
                        "correlation_id",
                        None,
                    ),
                    success=attempt.success,
                    error=attempt.error,
                )
            )
        return InvoiceResponse(
            id=invoice.id,
            closing_id=closing_ids[0] if len(closing_ids) == 1 else None,
            closing_ids=closing_ids,
            voucher_type=invoice.voucher_type,
            point_of_sale=invoice.point_of_sale,
            voucher_number=invoice.voucher_number,
            display_number=(
                f"{invoice.point_of_sale:05d}-"
                f"{invoice.voucher_number:08d}"
            ),
            issued_at=invoice.issued_at,
            declaration_type=invoice.declaration_type,
            total=invoice.total,
            sales_count=invoice.sales_count,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            cae=invoice.cae,
            cae_expiration=invoice.cae_expiration,
            authorization_code=invoice.authorization_code,
            authorization_date=invoice.authorization_date,
            rejection_reason=invoice.rejection_reason,
            fiscal_payload_json=invoice.fiscal_payload_json,
            arca_response_json=invoice.arca_response_json,
            status=cls._normalized_status(invoice.status),
            created_at=invoice.created_at or invoice.issued_at,
            updated_at=invoice.updated_at or invoice.issued_at,
            attempts=attempts,
        )

    @staticmethod
    def _request_payload(invoice: InvoiceModel) -> dict:
        closing_ids = sorted(closing.id for closing in invoice.closings)
        payload = {
            "request_id": f"invoice-{invoice.id}",
            "invoice_id": invoice.id,
            "point_of_sale": invoice.point_of_sale,
            "voucher_type": invoice.voucher_type,
            "voucher_number": invoice.voucher_number,
            "issued_at": invoice.issued_at.isoformat(),
            "total_amount": invoice.total,
            "sales_count": invoice.sales_count,
            "sale_ids": closing_ids,
        }
        if len(invoice.closings) != 1:
            payload["legacy_consolidated"] = True
            return payload

        sale = invoice.closings[0]
        business_date = sale.business_date or sale.closing_time.date()
        payload.update(
            {
                "sale_id": sale.id,
                "table_id": sale.table_id,
                "table_number": sale.table_number,
                "business_date": business_date.isoformat(),
                "closed_at": sale.closing_time.isoformat(),
                "subtotal": sale.subtotal,
                "discount_amount": sale.discount,
                "tax_amount": 0,
                "payment_methods": [
                    {
                        "method": payment.method,
                        "amount": payment.amount,
                    }
                    for payment in sale.payments
                ],
                "items": [
                    {
                        "product_id": item.product_id,
                        "description": item.product_name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "subtotal": item.subtotal,
                    }
                    for item in sale.items
                ],
            }
        )
        return payload

    @staticmethod
    def _validate_fiscal_payload(
        invoice: InvoiceModel,
        payload: dict | None,
    ) -> dict:
        if not isinstance(payload, dict):
            raise InvalidFiscalPayloadError(
                "El payload fiscal no es un objeto JSON válido"
            )
        required = {
            "request_id",
            "invoice_id",
            "point_of_sale",
            "voucher_type",
            "voucher_number",
            "total_amount",
            "sale_ids",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise InvalidFiscalPayloadError(
                "Faltan campos fiscales obligatorios: "
                + ", ".join(missing)
            )
        if payload["invoice_id"] != invoice.id:
            raise InvalidFiscalPayloadError(
                "El payload fiscal pertenece a otra factura"
            )
        if payload["total_amount"] != invoice.total:
            raise InvalidFiscalPayloadError(
                "El total del payload fiscal no coincide con la factura"
            )
        return payload

    def _create_outbox(
        self,
        invoice: InvoiceModel,
        message_source: str,
    ) -> OutboxModel:
        if message_source not in self.MESSAGE_SOURCES:
            raise ValueError("Origen del mensaje fiscal inválido")
        correlation_id = str(uuid4())
        invoice.status = INVOICE_QUEUED
        invoice.updated_at = local_now()
        for sale in invoice.closings:
            sale.invoicing_status = "SALE_INVOICING_PENDING"
        outbox = OutboxModel(
            invoice_id=invoice.id,
            correlation_id=correlation_id,
            payload={
                "message_type": "invoice.authorization.requested",
                "message_source": message_source,
                "invoice_id": invoice.id,
                "correlation_id": correlation_id,
            },
            is_processed=False,
            created_at=local_now(),
        )
        self.repository.add(outbox)
        self.session.flush()
        outbox.payload = {**outbox.payload, "outbox_id": outbox.id}
        return outbox

    def create_for_closing(
        self,
        closing: ClosingsModel,
        message_source: str = "sale_close",
    ) -> tuple[InvoiceModel, OutboxModel]:
        if closing.invoice is not None:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail={
                    "code": "SALE_ALREADY_INVOICED",
                    "message": (
                        f"La venta {closing.id} ya tiene una factura asociada."
                    ),
                    "invoice_id": closing.invoice.id,
                },
            )
        self.fiscal_period_guard.ensure_sale_mutable(
            closing.id,
            action=f"crear una factura para la venta {closing.id}",
        )
        now = local_now()
        invoice = InvoiceModel(
            closings=[closing],
            voucher_type=self.VOUCHER_TYPE,
            point_of_sale=self.POINT_OF_SALE,
            voucher_number=self.repository.next_voucher_number(
                self.POINT_OF_SALE,
                self.VOUCHER_TYPE,
            ),
            issued_at=now,
            declaration_type="ticket",
            total=closing.total,
            sales_count=1,
            period_start=None,
            period_end=None,
            status=INVOICE_PENDING,
            created_at=now,
            updated_at=now,
        )
        self.repository.add(invoice)
        self.session.flush()
        invoice.fiscal_payload_json = self._request_payload(invoice)
        closing.invoicing_status = "SALE_INVOICING_PENDING"
        return invoice, self._create_outbox(invoice, message_source)

    def _ensure_invoice_mutable(
        self,
        invoice: InvoiceModel,
        *,
        action: str,
    ) -> None:
        self.fiscal_period_guard.ensure_invoice_mutable(
            invoice.id,
            action=action,
        )

    def _mark_published(
        self,
        outboxes: list[OutboxModel],
        published_count: int,
    ) -> None:
        published_at = local_now()
        for outbox in outboxes[:published_count]:
            outbox.published_at = published_at

    def publish_outboxes(self, outboxes: list[OutboxModel]) -> int:
        payloads = [
            outbox.payload
            for outbox in outboxes
            if outbox.payload is not None
        ]
        published_count = self.message_publisher(payloads)
        self._mark_published(outboxes, published_count)
        for outbox in outboxes[published_count:]:
            if outbox.invoice_id is None:
                continue
            invoice = self.repository.get_by_id(outbox.invoice_id)
            if invoice is None or invoice.status != INVOICE_QUEUED:
                continue
            source = (outbox.payload or {}).get("message_source")
            invoice.status = (
                INVOICE_PENDING
                if source in {"sale_close", "ticket"}
                else INVOICE_RETRY_PENDING
            )
            invoice.updated_at = local_now()
        if outboxes:
            commit_session(self.session)
        return published_count

    @staticmethod
    def _record_attempt(
        invoice: InvoiceModel,
        *,
        attempted_at: datetime,
        previous_status: str,
        new_status: str,
        request_payload: dict | None,
        response_payload: dict | None,
        error_reason: str | None,
        worker_id: str | None,
        correlation_id: str | None,
    ) -> None:
        success = new_status == INVOICE_AUTHORIZED
        invoice.attempts.append(
            InvoiceAttemptModel(
                attempt_number=len(invoice.attempts) + 1,
                attempted_at=attempted_at,
                status_before=previous_status,
                status_after=new_status,
                request_payload=request_payload,
                response_payload=response_payload,
                error_reason=error_reason,
                worker_id=worker_id,
                correlation_id=correlation_id,
                success=success,
                error=error_reason,
            )
        )

    @staticmethod
    def _set_sale_invoicing_status(
        invoice: InvoiceModel,
        status: str,
    ) -> None:
        for sale in invoice.closings:
            sale.invoicing_status = status

    def process_outbox(
        self,
        message: dict,
        *,
        worker_id: str | None = None,
    ) -> bool:
        try:
            invoice_id = int(message["invoice_id"])
            outbox_id = int(message["outbox_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Mensaje de factura inválido") from error

        outbox = self.repository.get_outbox_by_id(
            outbox_id,
            for_update=True,
        )
        if outbox is None:
            raise ValueError(f"Outbox {outbox_id} no encontrado")
        if outbox.is_processed:
            return False
        if outbox.invoice_id not in (None, invoice_id):
            raise ValueError("El outbox pertenece a otra factura")
        correlation_id = message.get("correlation_id")
        if (
            outbox.correlation_id is not None
            and correlation_id is not None
            and correlation_id != outbox.correlation_id
        ):
            raise ValueError("El correlation_id del mensaje es inválido")

        invoice = self.repository.get_by_id_for_update(invoice_id)
        if invoice is None:
            raise ValueError(f"Factura {invoice_id} no encontrada")
        invoice.status = self._normalized_status(invoice.status)
        if invoice.status == INVOICE_AUTHORIZED:
            outbox.is_processed = True
            return False

        now = local_now()
        if invoice.status == INVOICE_AUTHORIZING:
            updated_at = invoice.updated_at or invoice.issued_at
            if now - updated_at < self.AUTHORIZING_STALE_AFTER:
                outbox.is_processed = True
                return False
        elif invoice.status not in PROCESSABLE_INVOICE_STATUSES:
            outbox.is_processed = True
            return False

        previous_status = invoice.status
        invoice.status = INVOICE_AUTHORIZING
        invoice.updated_at = now
        request_payload = invoice.fiscal_payload_json

        try:
            validated_payload = self._validate_fiscal_payload(
                invoice,
                request_payload,
            )
            authorization = self.afip_client.authorize(validated_payload)
        except InvalidFiscalPayloadError as error:
            response_payload = error.response_payload
            invoice.status = INVOICE_REJECTED
            invoice.rejection_reason = str(error)
            invoice.arca_response_json = response_payload
            invoice.updated_at = local_now()
            self._set_sale_invoicing_status(
                invoice,
                "SALE_INVOICE_REJECTED",
            )
            outbox.is_processed = True
            self._record_attempt(
                invoice,
                attempted_at=now,
                previous_status=previous_status,
                new_status=INVOICE_REJECTED,
                request_payload=request_payload,
                response_payload=response_payload,
                error_reason=str(error),
                worker_id=worker_id,
                correlation_id=outbox.correlation_id,
            )
            return False
        except AfipRejectedError as error:
            invoice.status = INVOICE_REJECTED
            invoice.rejection_reason = str(error)
            invoice.arca_response_json = error.response_payload
            invoice.updated_at = local_now()
            self._set_sale_invoicing_status(
                invoice,
                "SALE_INVOICE_REJECTED",
            )
            outbox.is_processed = True
            self._record_attempt(
                invoice,
                attempted_at=now,
                previous_status=previous_status,
                new_status=INVOICE_REJECTED,
                request_payload=request_payload,
                response_payload=error.response_payload,
                error_reason=str(error),
                worker_id=worker_id,
                correlation_id=outbox.correlation_id,
            )
            return False
        except AfipTemporaryError as error:
            invoice.status = INVOICE_RETRY_PENDING
            invoice.rejection_reason = str(error)
            invoice.arca_response_json = error.response_payload
            invoice.updated_at = local_now()
            self._set_sale_invoicing_status(
                invoice,
                "SALE_INVOICING_PENDING",
            )
            self._record_attempt(
                invoice,
                attempted_at=now,
                previous_status=previous_status,
                new_status=INVOICE_RETRY_PENDING,
                request_payload=request_payload,
                response_payload=error.response_payload,
                error_reason=str(error),
                worker_id=worker_id,
                correlation_id=outbox.correlation_id,
            )
            raise
        except Exception as error:
            technical_error = AfipTemporaryError(
                f"Error inesperado al autorizar la factura: {error}"
            )
            invoice.status = INVOICE_RETRY_PENDING
            invoice.rejection_reason = str(technical_error)
            invoice.arca_response_json = technical_error.response_payload
            invoice.updated_at = local_now()
            self._set_sale_invoicing_status(
                invoice,
                "SALE_INVOICING_PENDING",
            )
            self._record_attempt(
                invoice,
                attempted_at=now,
                previous_status=previous_status,
                new_status=INVOICE_RETRY_PENDING,
                request_payload=request_payload,
                response_payload=technical_error.response_payload,
                error_reason=str(technical_error),
                worker_id=worker_id,
                correlation_id=outbox.correlation_id,
            )
            raise technical_error from error

        invoice.status = INVOICE_AUTHORIZED
        invoice.authorization_code = authorization.cae
        invoice.authorization_date = local_now()
        invoice.cae_expiration = authorization.cae_expiration
        invoice.rejection_reason = None
        invoice.arca_response_json = authorization.response_payload
        invoice.updated_at = local_now()
        self._set_sale_invoicing_status(invoice, "SALE_INVOICED")
        outbox.is_processed = True
        self._record_attempt(
            invoice,
            attempted_at=now,
            previous_status=previous_status,
            new_status=INVOICE_AUTHORIZED,
            request_payload=request_payload,
            response_payload=authorization.response_payload,
            error_reason=None,
            worker_id=worker_id,
            correlation_id=outbox.correlation_id,
        )
        return True

    def mark_outbox_processed(self, message: dict) -> None:
        try:
            outbox_id = int(message["outbox_id"])
        except (KeyError, TypeError, ValueError):
            return
        outbox = self.repository.get_outbox_by_id(
            outbox_id,
            for_update=True,
        )
        if outbox is not None:
            outbox.is_processed = True

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

    def get_for_pdf(self, invoice_id: int) -> "InvoiceModel":
        """Devuelve el InvoiceModel si está autorizado; lanza HTTPException para cualquier otro estado."""
        invoice = self.repository.get_by_id(invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Factura no encontrada",
            )
        status = self._normalized_status(invoice.status)
        if status == INVOICE_AUTHORIZED:
            return invoice
        if status in PENDING_INVOICE_STATUSES:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail={
                    "status": "pending",
                    "invoice_status": status,
                    "message": "El comprobante aún no fue autorizado por AFIP",
                },
            )
        if status == INVOICE_REJECTED:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={
                    "status": "rejected",
                    "invoice_status": status,
                    "message": invoice.rejection_reason or "Comprobante rechazado por AFIP",
                },
            )
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "status": "cancelled",
                "invoice_status": status,
                "message": "El comprobante fue cancelado y no puede generarse",
            },
        )

    def retry(self, invoice_id: int) -> InvoiceResponse:
        invoice = self.repository.get_by_id_for_update(invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Factura no encontrada",
            )
        invoice.status = self._normalized_status(invoice.status)
        if invoice.status not in RETRYABLE_INVOICE_STATUSES:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=(
                    "Sólo pueden reintentarse facturas pendientes, "
                    "rechazadas o marcadas para reintento"
                ),
            )

        self._ensure_invoice_mutable(
            invoice,
            action=f"reintentar la factura {invoice.id}",
        )
        outbox = self._create_outbox(invoice, "manual")
        commit_session(self.session)
        self.publish_outboxes([outbox])
        return self.get_invoice(invoice_id)

    @staticmethod
    def _period_bounds(
        payload: RetryInvoicePeriodRequest,
    ) -> tuple[datetime, datetime]:
        if payload.period_from is not None:
            start = datetime.combine(payload.period_from, datetime.min.time())
            end = datetime.combine(
                payload.period_to + timedelta(days=1),
                datetime.min.time(),
            )
            return start, end
        if payload.period == "diario":
            return day_bounds(payload.date)

        start = datetime(payload.year, payload.month, 1)
        end = (
            datetime(payload.year + 1, 1, 1)
            if payload.month == 12
            else datetime(payload.year, payload.month + 1, 1)
        )
        return start, end

    def pending_summary(
        self,
        payload: RetryInvoicePeriodRequest,
    ) -> PendingInvoiceSummaryResponse:
        start, end = self._period_bounds(payload)
        invoices = self.repository.get_for_sales_period(start, end)
        pending = [
            invoice
            for invoice in invoices
            if self._normalized_status(invoice.status)
            in PENDING_INVOICE_STATUSES | {INVOICE_REJECTED}
        ]
        sales = {
            sale.id: sale
            for invoice in invoices
            for sale in invoice.closings
        }
        cash_closing_exists = True
        if payload.period == "diario":
            cash_closing_exists = (
                self.session.scalar(
                    select(CashClosingModel.id).where(
                        CashClosingModel.business_date == payload.date,
                        CashClosingModel.status == "cerrado",
                    )
                )
                is not None
            )
        can_declare = (
            cash_closing_exists
            and bool(sales)
            and not pending
            and all(
                self._normalized_status(invoice.status)
                == INVOICE_AUTHORIZED
                for invoice in invoices
            )
        )
        if not cash_closing_exists:
            blocking_reason = "Primero debe realizar el cierre de caja del día"
        elif pending:
            blocking_reason = (
                "Existen comprobantes pendientes o rechazados en el período"
            )
        elif not sales:
            blocking_reason = "No hay ventas en el período seleccionado"
        else:
            blocking_reason = None
        return PendingInvoiceSummaryResponse(
            period=payload.period or "diario",
            period_start=start,
            period_end=end,
            sales_count=len(sales),
            total=sum(sale.total for sale in sales.values()),
            cash_closing_exists=cash_closing_exists,
            can_declare=can_declare,
            blocking_reason=blocking_reason,
        )

    def retry_period(
        self,
        payload: RetryInvoicePeriodRequest,
    ) -> RetryInvoicePeriodResponse:
        start, end = self._period_bounds(payload)
        invoices = self.repository.get_retryable_for_period(
            start,
            end,
            list(payload.statuses),
        )
        if not invoices:
            return RetryInvoicePeriodResponse(
                status="sin_pendientes",
                message=(
                    "No hay comprobantes pendientes o rechazados "
                    "para el período seleccionado"
                ),
                queued_count=0,
                published_count=0,
                invoice_ids=[],
                invoices=[],
                sales_count=0,
                total=0,
                invoice=None,
            )

        for invoice in invoices:
            self._ensure_invoice_mutable(
                invoice,
                action=f"reintentar la factura {invoice.id}",
            )
        outboxes = [
            self._create_outbox(invoice, "retry_period")
            for invoice in invoices
        ]
        commit_session(self.session)
        published_count = self.publish_outboxes(outboxes)
        status = "encolado" if published_count == len(outboxes) else "error"
        message = (
            "Los comprobantes fueron encolados para autorización"
            if status == "encolado"
            else (
                "Los comprobantes quedaron registrados para reintento, "
                "pero no todos pudieron publicarse en RabbitMQ"
            )
        )
        responses = [self._response(invoice) for invoice in invoices]
        sale_ids = {
            sale.id
            for invoice in invoices
            for sale in invoice.closings
        }
        return RetryInvoicePeriodResponse(
            status=status,
            message=message,
            queued_count=len(outboxes),
            published_count=published_count,
            invoice_ids=[invoice.id for invoice in invoices],
            invoices=responses,
            sales_count=len(sale_ids),
            total=sum(invoice.total for invoice in invoices),
            invoice=responses[0] if len(responses) == 1 else None,
        )

    def report(self, report_date: date) -> InvoiceReportResponse:
        invoices = self.list_invoices(report_date)
        authorized = [
            invoice
            for invoice in invoices
            if invoice.status == INVOICE_AUTHORIZED
        ]
        return InvoiceReportResponse(
            date=report_date,
            cuit=self.CUIT,
            business_name=self.BUSINESS_NAME,
            total_invoiced=sum(invoice.total for invoice in authorized),
            invoice_count=len(authorized),
            invoices=authorized,
        )
