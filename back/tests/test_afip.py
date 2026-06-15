import random
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from db.db_models import (
    ClosingItemModel,
    ClosingPaymentModel,
    ClosingsModel,
    InvoiceModel,
    OutboxModel,
)
from invoices.afip_client import (
    AfipAuthorization,
    AfipRejectedError,
    AfipUnavailableError,
    MockAfipClient,
)
from invoices.models.invoice_models import RetryInvoicePeriodRequest
from invoices.service.invoice_service import (
    INVOICE_AUTHORIZED,
    INVOICE_QUEUED,
    INVOICE_REJECTED,
    INVOICE_RETRY_PENDING,
    InvoiceService,
)
from shared.time_utils import local_now


class SuccessfulAfipClient:
    def __init__(self):
        self.requests = []

    def authorize(self, request_payload):
        self.requests.append(request_payload)
        return AfipAuthorization(
            cae="12345678901234",
            cae_expiration=date(2026, 6, 25),
            response_payload={
                "result": "A",
                "request_id": request_payload["request_id"],
            },
        )


class RejectingAfipClient:
    def authorize(self, request_payload):
        raise AfipRejectedError(
            "CUIT inválido",
            {
                "result": "R",
                "reason": "CUIT inválido",
                "request_id": request_payload["request_id"],
            },
        )


class UnavailableAfipClient:
    def authorize(self, request_payload):
        raise AfipUnavailableError("ARCA temporalmente no disponible")


def _sale(sale_id: int, total: int = 5000) -> ClosingsModel:
    return ClosingsModel(
        id=sale_id,
        table_id=1,
        table_number=sale_id,
        opening_time=local_now(),
        closing_time=local_now(),
        business_date=local_now().date(),
        people=2,
        served_by=1,
        subtotal=total,
        discount=0,
        total=total,
        status="cerrada",
        invoicing_status="SALE_INVOICING_PENDING",
        items=[
            ClosingItemModel(
                id=sale_id,
                product_id=4,
                product_name="IPA",
                product_type="cerveza",
                unit="pinta",
                quantity=1,
                unit_price=total,
                subtotal=total,
            )
        ],
        payments=[
            ClosingPaymentModel(
                id=sale_id,
                method="tarjeta_debito",
                amount=total,
            )
        ],
    )


def _invoice(
    invoice_id: int = 1,
    *,
    status: str = INVOICE_QUEUED,
    total: int = 5000,
) -> InvoiceModel:
    now = local_now()
    invoice = InvoiceModel(
        id=invoice_id,
        closings=[_sale(invoice_id + 10, total)],
        voucher_type="Factura B",
        point_of_sale=1,
        voucher_number=invoice_id,
        issued_at=now,
        declaration_type="ticket",
        total=total,
        sales_count=1,
        period_start=None,
        period_end=None,
        status=status,
        created_at=now,
        updated_at=now,
        attempts=[],
    )
    invoice.fiscal_payload_json = InvoiceService._request_payload(invoice)
    return invoice


def _service_with_repository(
    afip_client=None,
    publisher=None,
) -> tuple[InvoiceService, MagicMock, MagicMock]:
    session = MagicMock()
    service = InvoiceService(
        session,
        afip_client or SuccessfulAfipClient(),
        publisher or (lambda payloads: len(payloads)),
    )
    service.repository = MagicMock()
    service.fiscal_period_guard = MagicMock()
    return service, session, service.repository


def _configure_outbox(
    repository: MagicMock,
    invoice: InvoiceModel,
    outbox_id: int = 20,
) -> OutboxModel:
    outbox = OutboxModel(
        id=outbox_id,
        invoice_id=invoice.id,
        correlation_id=f"corr-{outbox_id}",
        payload={
            "invoice_id": invoice.id,
            "outbox_id": outbox_id,
            "correlation_id": f"corr-{outbox_id}",
        },
        is_processed=False,
        created_at=local_now(),
    )
    repository.get_by_id_for_update.return_value = invoice
    repository.get_outbox_by_id.return_value = outbox
    return outbox


def test_mock_afip_has_a_configurable_rejection_probability():
    client = MockAfipClient(0, random.Random(10))

    with pytest.raises(AfipRejectedError):
        client.authorize({"request_id": "test-2"})


def test_create_for_closing_persists_individual_invoice_payload_and_outbox():
    service, session, repository = _service_with_repository()
    repository.next_voucher_number.return_value = 12

    def assign_database_id(entity):
        if isinstance(entity, InvoiceModel):
            entity.id = 21
        elif isinstance(entity, OutboxModel):
            entity.id = 34

    repository.add.side_effect = assign_database_id
    sale = _sale(7)

    invoice, outbox = service.create_for_closing(sale)

    assert invoice.closings == [sale]
    assert invoice.status == INVOICE_QUEUED
    assert invoice.fiscal_payload_json["sale_id"] == sale.id
    assert invoice.fiscal_payload_json["items"][0]["description"] == "IPA"
    assert invoice.fiscal_payload_json["payment_methods"] == [
        {"method": "tarjeta_debito", "amount": 5000}
    ]
    assert outbox.invoice_id == invoice.id
    assert outbox.payload["invoice_id"] == invoice.id
    assert "items" not in outbox.payload
    assert repository.add.call_count == 2
    assert session.flush.call_count == 2


def test_create_for_closing_rejects_duplicate_invoice():
    service, _, repository = _service_with_repository()
    sale = _sale(7)
    sale.invoice = _invoice(31)

    with pytest.raises(HTTPException) as error:
        service.create_for_closing(sale)

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "SALE_ALREADY_INVOICED"
    repository.add.assert_not_called()


def test_create_for_closing_checks_that_the_sale_was_not_declared():
    service, _, _ = _service_with_repository()
    sale = _sale(7)

    service.create_for_closing(sale)

    service.fiscal_period_guard.ensure_sale_mutable.assert_called_once_with(
        sale.id,
        action=f"crear una factura para la venta {sale.id}",
    )


def test_worker_authorizes_pending_invoice_and_records_full_attempt():
    service, _, repository = _service_with_repository(
        SuccessfulAfipClient()
    )
    invoice = _invoice()
    outbox = _configure_outbox(repository, invoice)

    processed = service.process_outbox(
        outbox.payload,
        worker_id="worker-1",
    )

    assert processed is True
    assert invoice.status == INVOICE_AUTHORIZED
    assert invoice.authorization_code == "12345678901234"
    assert invoice.authorization_date is not None
    assert invoice.closings[0].invoicing_status == "SALE_INVOICED"
    assert outbox.is_processed is True
    assert len(invoice.attempts) == 1
    attempt = invoice.attempts[0]
    assert attempt.attempt_number == 1
    assert attempt.status_before == INVOICE_QUEUED
    assert attempt.status_after == INVOICE_AUTHORIZED
    assert attempt.worker_id == "worker-1"
    assert attempt.correlation_id == outbox.correlation_id


def test_worker_marks_fiscal_rejection_without_requeueing():
    service, _, repository = _service_with_repository(
        RejectingAfipClient()
    )
    invoice = _invoice()
    outbox = _configure_outbox(repository, invoice)

    processed = service.process_outbox(outbox.payload)

    assert processed is False
    assert invoice.status == INVOICE_REJECTED
    assert invoice.rejection_reason == "CUIT inválido"
    assert invoice.closings[0].invoicing_status == "SALE_INVOICE_REJECTED"
    assert outbox.is_processed is True
    assert invoice.attempts[0].status_after == INVOICE_REJECTED


def test_worker_marks_temporary_error_as_retry_pending():
    service, _, repository = _service_with_repository(
        UnavailableAfipClient()
    )
    invoice = _invoice()
    outbox = _configure_outbox(repository, invoice)

    with pytest.raises(AfipUnavailableError):
        service.process_outbox(outbox.payload)

    assert invoice.status == INVOICE_RETRY_PENDING
    assert outbox.is_processed is False
    assert invoice.attempts[0].status_after == INVOICE_RETRY_PENDING


def test_worker_does_not_authorize_an_authorized_invoice_twice():
    afip = SuccessfulAfipClient()
    service, _, repository = _service_with_repository(afip)
    invoice = _invoice(status=INVOICE_AUTHORIZED)
    outbox = _configure_outbox(repository, invoice)

    processed = service.process_outbox(outbox.payload)

    assert processed is False
    assert outbox.is_processed is True
    assert afip.requests == []
    assert invoice.attempts == []


def test_retry_invoice_rejects_non_retryable_status():
    service, _, repository = _service_with_repository()
    repository.get_by_id_for_update.return_value = _invoice(
        status=INVOICE_AUTHORIZED
    )

    with pytest.raises(HTTPException) as error:
        service.retry(1)

    assert error.value.status_code == 409


def test_retry_invoice_is_blocked_when_invoice_was_declared():
    service, _, repository = _service_with_repository()
    invoice = _invoice(status="INVOICE_PENDING")
    repository.get_by_id_for_update.return_value = invoice
    service.fiscal_period_guard.ensure_invoice_mutable.side_effect = (
        HTTPException(
        status_code=409,
        detail={"code": "FISCAL_RECORD_ALREADY_DECLARED"},
        )
    )

    with pytest.raises(HTTPException) as error:
        service.retry(invoice.id)

    assert error.value.detail["code"] == "FISCAL_RECORD_ALREADY_DECLARED"
    repository.add.assert_not_called()


def test_retry_period_requeues_existing_invoices_without_creating_new_ones():
    published = []
    service, session, repository = _service_with_repository(
        publisher=lambda payloads: published.extend(payloads) or len(payloads)
    )
    invoices = [
        _invoice(1, status="INVOICE_PENDING", total=1000),
        _invoice(2, status="INVOICE_REJECTED", total=2000),
    ]
    repository.get_retryable_for_period.return_value = invoices
    next_outbox_id = iter([31, 32])

    def assign_outbox_id(entity):
        if isinstance(entity, OutboxModel):
            entity.id = next(next_outbox_id)

    repository.add.side_effect = assign_outbox_id

    response = service.retry_period(
        RetryInvoicePeriodRequest(
            periodFrom=date(2026, 6, 1),
            periodTo=date(2026, 6, 30),
        )
    )

    assert response.status == "encolado"
    assert response.invoice_ids == [1, 2]
    assert response.queued_count == 2
    assert response.published_count == 2
    assert response.total == 3000
    assert all(invoice.status == INVOICE_QUEUED for invoice in invoices)
    assert len(published) == 2
    assert not any(
        isinstance(call.args[0], InvoiceModel)
        for call in repository.add.call_args_list
    )
    assert (
        service.fiscal_period_guard.ensure_invoice_mutable.call_count == 2
    )
    assert session.commit.call_count == 2
