import random
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from db.db_models import ClosingsModel, InvoiceModel
from invoices.afip_client import (
    AfipAuthorization,
    AfipUnavailableError,
    MockAfipClient,
)
from invoices.models.invoice_models import RetryInvoicePeriodRequest
from invoices.service.invoice_service import InvoiceService
from shared.time_utils import local_now


class FakeSession:
    def __init__(self):
        self.invoice = None

    def commit(self):
        for index, attempt in enumerate(self.invoice.attempts, 1):
            attempt.id = index

    def rollback(self):
        pass


def _invoice():
    return InvoiceModel(
        voucher_type="Factura B",
        point_of_sale=1,
        voucher_number=1,
        issued_at=local_now(),
        status="pendiente",
    )


def test_mock_afip_can_be_forced_to_succeed():
    client = MockAfipClient(1, random.Random(10))

    response = client.authorize({"request_id": "test-1"})

    assert len(response.cae) == 14
    assert response.response_payload["result"] == "A"


def test_mock_afip_can_be_forced_to_fail():
    client = MockAfipClient(0, random.Random(10))

    with pytest.raises(AfipUnavailableError):
        client.authorize({"request_id": "test-2"})


@pytest.mark.parametrize(
    ("success_rate", "expected_status", "expected_success"),
    [
        (1, "autorizada", True),
        (0, "pendiente", False),
    ],
)
def test_invoice_attempt_is_persisted_once(
    success_rate,
    expected_status,
    expected_success,
):
    service = InvoiceService(
        FakeSession(),
        MockAfipClient(success_rate, random.Random(5)),
    )
    invoice = _invoice()
    closing = SimpleNamespace(id=3, total=5000, table_number=2)

    result = service._attempt_authorization(invoice, closing)

    assert result is expected_success
    assert invoice.status == expected_status
    assert len(invoice.attempts) == 1
    assert invoice.attempts[0].success is expected_success


def test_pending_invoice_can_be_retried_successfully():
    session = FakeSession()
    service = InvoiceService(
        session,
        MockAfipClient(0, random.Random(5)),
    )
    invoice = _invoice()
    invoice.id = 9
    invoice.closing_id = 3
    invoice.closing = ClosingsModel(
        id=3,
        table_id=1,
        table_number=2,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=1,
        subtotal=5000,
        discount=0,
        total=5000,
        status="cerrada",
    )
    session.invoice = invoice
    service.repository.get_by_id = lambda _: invoice

    assert service._attempt_authorization(invoice, invoice.closing) is False
    invoice.attempts[0].id = 1
    service.afip_client = MockAfipClient(1, random.Random(5))

    response = service.retry(invoice.id)

    assert response.status == "autorizada"
    assert len(response.attempts) == 2
    assert response.attempts[-1].success is True


class SequenceAfipClient:
    def __init__(self, results: list[bool]):
        self.results = iter(results)

    def authorize(self, request_payload):
        if not next(self.results):
            raise AfipUnavailableError("AFIP no está disponible")
        return AfipAuthorization(
            cae="12345678901234",
            cae_expiration=date(2026, 6, 19),
            response_payload={
                "result": "A",
                "request_id": request_payload["request_id"],
            },
        )


def _period_invoice(invoice_id: int):
    invoice = _invoice()
    invoice.id = invoice_id
    invoice.closing_id = invoice_id
    invoice.attempts = []
    invoice.closing = ClosingsModel(
        id=invoice_id,
        table_id=1,
        table_number=invoice_id,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=1,
        subtotal=5000,
        discount=0,
        total=5000,
        status="cerrada",
    )
    return invoice


@pytest.mark.parametrize(
    ("results", "expected_status", "authorized", "failed"),
    [
        ([True, True], "completado", 2, 0),
        ([True, False], "parcial", 1, 1),
        ([False, False], "error", 0, 2),
    ],
)
def test_retry_period_returns_aggregate_result(
    results,
    expected_status,
    authorized,
    failed,
):
    session = MagicMock()
    invoices = [_period_invoice(1), _period_invoice(2)]

    def assign_attempt_ids():
        for invoice in invoices:
            for index, attempt in enumerate(invoice.attempts, 1):
                attempt.id = index

    session.commit.side_effect = assign_attempt_ids
    service = InvoiceService(session, SequenceAfipClient(results))
    service.repository = MagicMock()
    service.repository.get_pending_by_closing_period.return_value = invoices

    response = service.retry_period(
        RetryInvoicePeriodRequest(
            period="diario",
            date=date(2026, 6, 9),
        )
    )

    assert response.status == expected_status
    assert response.processed_count == 2
    assert response.authorized_count == authorized
    assert response.failed_count == failed
    assert len(response.invoices) == 2


def test_retry_period_returns_without_calling_afip_when_empty():
    service = InvoiceService(MagicMock(), SequenceAfipClient([]))
    service.repository = MagicMock()
    service.repository.get_pending_by_closing_period.return_value = []

    response = service.retry_period(
        RetryInvoicePeriodRequest(
            period="mensual",
            year=2026,
            month=6,
        )
    )

    assert response.status == "sin_pendientes"
    assert response.processed_count == 0


def test_retry_period_uses_daily_and_monthly_bounds():
    service = InvoiceService(MagicMock(), SequenceAfipClient([]))
    service.repository = MagicMock()
    service.repository.get_pending_by_closing_period.return_value = []

    service.retry_period(
        RetryInvoicePeriodRequest(
            period="diario",
            date=date(2026, 6, 9),
        )
    )
    daily_start, daily_end = (
        service.repository.get_pending_by_closing_period.call_args.args
    )
    assert daily_start.date() == date(2026, 6, 9)
    assert daily_end.date() == date(2026, 6, 10)

    service.retry_period(
        RetryInvoicePeriodRequest(
            period="mensual",
            year=2026,
            month=6,
        )
    )
    monthly_start, monthly_end = (
        service.repository.get_pending_by_closing_period.call_args.args
    )
    assert monthly_start.date() == date(2026, 6, 1)
    assert monthly_end.date() == date(2026, 7, 1)
