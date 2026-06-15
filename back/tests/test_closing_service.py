from datetime import date, timedelta
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from closings.models.closing_models import (
    CloseTableRequest,
    ClosingPaymentRequest,
    CreateCashClosingRequest,
    UpdateCashClosingRequest,
)
from closings.service.closing_service import ClosingService
from db.db_models import (
    CashClosingModel,
    ClosingPaymentModel,
    ClosingsModel,
    InvoiceModel,
    OpenTableItemModel,
    OpenTableModel,
    OutboxModel,
    ProductModel,
)
from invoices.service.invoice_service import (
    INVOICE_AUTHORIZED,
    INVOICE_AUTHORIZING,
    INVOICE_PENDING,
    INVOICE_QUEUED,
    INVOICE_REJECTED,
)
from shared.time_utils import local_now


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.added = []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def flush(self):
        pass

    def add(self, entity):
        entity.id = len(self.added) + 1
        self.added.append(entity)


def _service_with_table(price=1000, quantity=1):
    session = FakeSession()
    service = ClosingService(session)
    product = ProductModel(
        id=5,
        name="IPA",
        type="cerveza",
        unit="pinta",
        price=price,
        qty=20,
    )
    item = OpenTableItemModel(
        id=8,
        product_id=product.id,
        product=product,
        quantity=quantity,
        curr_price=price,
    )
    table = OpenTableModel(
        id=2,
        table_number=7,
        table_name="Patio",
        opening_time=local_now(),
        people=3,
        items=[item],
    )
    captured = {}

    def add_closing(closing):
        closing.id = 11
        for index, closing_item in enumerate(closing.items, 1):
            closing_item.id = index
        for index, payment in enumerate(closing.payments, 1):
            payment.id = index
        captured["closing"] = closing

    service.table_repository = MagicMock()
    service.table_repository.get_by_number.return_value = table
    service.fiscal_period_guard = MagicMock()
    service.repository = MagicMock()
    service.repository.add.side_effect = add_closing
    service.repository.get_by_id.side_effect = lambda _: captured["closing"]
    service.repository.get_by_id_for_update.side_effect = (
        lambda _: captured["closing"]
    )
    service.invoice_service.repository = MagicMock()
    service.invoice_service.repository.next_voucher_number.return_value = 1
    next_outbox_id = iter(range(31, 100))

    def add_invoice_entity(entity):
        if isinstance(entity, InvoiceModel):
            entity.id = 21
            captured["invoice"] = entity
        elif isinstance(entity, OutboxModel):
            entity.id = next(next_outbox_id)

    service.invoice_service.repository.add.side_effect = add_invoice_entity
    service.invoice_service.repository.get_by_id.side_effect = (
        lambda _: captured.get("invoice")
    )
    service.invoice_service.fiscal_period_guard = MagicMock()
    service.invoice_service.message_publisher = MagicMock(return_value=1)
    return service, session, table, captured


def _attach_invoice(
    sale: ClosingsModel,
    *,
    status: str = INVOICE_AUTHORIZED,
    invoice_id: int = 70,
) -> InvoiceModel:
    now = local_now()
    invoice = InvoiceModel(
        id=invoice_id,
        closings=[sale],
        voucher_type="Factura B",
        point_of_sale=1,
        voucher_number=invoice_id,
        issued_at=now,
        declaration_type="ticket",
        total=sale.total,
        sales_count=1,
        period_start=None,
        period_end=None,
        status=status,
        created_at=now,
        updated_at=now,
        attempts=[],
    )
    sale.invoice = invoice
    return invoice


def test_close_with_sales_is_independent_from_fiscal_period_dates():
    service, session, table, _ = _service_with_table()

    response = service.close_table(
        7,
        CloseTableRequest(
            payments=[ClosingPaymentRequest(method="efectivo", amount=900)]
        ),
        user_id=4,
    )

    assert response.closing.business_date == response.closing.closing_time.date()
    assert table.people == 0
    assert table.items == []
    assert session.commits == 2


def test_cash_close_applies_discount_and_frees_table():
    service, session, table, captured = _service_with_table()
    payload = CloseTableRequest(
        payments=[ClosingPaymentRequest(method="efectivo", amount=900)]
    )

    response = service.close_table(7, payload, user_id=4)

    assert response.closing.subtotal == 1000
    assert response.closing.discount == 100
    assert response.closing.total == 900
    assert response.closing.served_by == 4
    assert response.closing.invoice is not None
    assert response.closing.invoice.status == INVOICE_QUEUED
    assert response.closing.invoicing_status == "SALE_INVOICING_PENDING"
    assert captured["closing"].items[0].product_name == "IPA"
    assert table.people == 0
    assert table.items == []
    assert session.commits == 2


def test_split_payment_creates_one_pending_invoice():
    service, session, _, _ = _service_with_table(price=1000, quantity=2)
    payload = CloseTableRequest(
        payments=[
            ClosingPaymentRequest(method="efectivo", amount=900),
            ClosingPaymentRequest(method="tarjeta_debito", amount=900),
        ]
    )

    response = service.close_table(7, payload, user_id=4)

    assert response.closing.subtotal == 2000
    assert response.closing.discount == 200
    assert response.closing.total == 1800
    assert response.closing.invoice is not None
    assert response.closing.invoice.total == 1800
    assert session.commits == 2
    service.invoice_service.message_publisher.assert_called_once()


def test_electronic_close_persists_invoice_when_rabbit_is_unavailable():
    service, session, table, _ = _service_with_table()
    service.invoice_service.message_publisher = MagicMock(return_value=0)
    payload = CloseTableRequest(
        payments=[
            ClosingPaymentRequest(method="tarjeta_debito", amount=1000),
        ]
    )

    response = service.close_table(7, payload, user_id=4)

    assert response.warning is not None
    assert response.closing.invoice is not None
    assert response.closing.invoice.status == "INVOICE_PENDING"
    assert table.items == []
    assert session.commits == 2
    service.invoice_service.message_publisher.assert_called_once()


def test_printing_ticket_creates_and_enqueues_invoice():
    service, session, _, captured = _service_with_table()
    closing = captured.setdefault(
        "closing",
        ClosingsModel(
            id=11,
            table_id=2,
            table_number=7,
            opening_time=local_now(),
            closing_time=local_now(),
            people=3,
            served_by=4,
            subtotal=1000,
            discount=0,
            total=1000,
            status="cerrada",
            invoicing_status="SALE_REGISTERED",
            items=[],
            payments=[],
        ),
    )

    response = service.issue_ticket(closing.id)

    assert response.closing_id == closing.id
    assert response.status == INVOICE_QUEUED
    service.invoice_service.message_publisher.assert_called_once()
    assert session.commits == 2


def test_printing_ticket_returns_existing_invoice_without_duplicate():
    service, session, _, captured = _service_with_table()
    closing = captured.setdefault(
        "closing",
        ClosingsModel(
            id=11,
            table_id=2,
            table_number=7,
            opening_time=local_now(),
            closing_time=local_now(),
            people=3,
            served_by=4,
            subtotal=1000,
            discount=0,
            total=1000,
            status="cerrada",
            invoicing_status="SALE_INVOICING_PENDING",
            items=[],
            payments=[],
        ),
    )
    now = local_now()
    closing.invoice = InvoiceModel(
        id=31,
        closings=[closing],
        voucher_type="Factura B",
        point_of_sale=1,
        voucher_number=1,
        issued_at=now,
        declaration_type="ticket",
        total=closing.total,
        sales_count=1,
        period_start=None,
        period_end=None,
        status=INVOICE_QUEUED,
        created_at=now,
        updated_at=now,
        attempts=[],
    )

    response = service.issue_ticket(closing.id)

    assert response.id == 31
    assert service.invoice_service.repository.add.call_count == 0
    service.invoice_service.message_publisher.assert_not_called()
    assert session.commits == 0


def test_incorrect_payment_does_not_modify_table():
    service, session, table, _ = _service_with_table()
    payload = CloseTableRequest(
        payments=[ClosingPaymentRequest(method="efectivo", amount=800)]
    )

    with pytest.raises(HTTPException) as error:
        service.close_table(7, payload, user_id=4)

    assert error.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert table.people == 3
    assert len(table.items) == 1
    assert session.commits == 0


def test_overpayment_is_accepted_and_returns_change():
    service, session, table, _ = _service_with_table()
    payload = CloseTableRequest(
        payments=[ClosingPaymentRequest(method="efectivo", amount=1000)]
    )

    response = service.close_table(7, payload, user_id=4)

    assert response.closing.total == 900
    assert response.closing.amount_received == 1000
    assert response.closing.change == 100
    assert table.items == []
    assert session.commits == 2


def test_empty_table_can_be_closed_without_payments():
    service, session, table, _ = _service_with_table()
    table.items = []

    response = service.close_table(
        7,
        CloseTableRequest(payments=[]),
        user_id=4,
    )

    assert response.closing.subtotal == 0
    assert response.closing.total == 0
    assert response.closing.payments == []
    assert response.closing.change == 0
    assert table.people == 0
    assert session.commits == 1


def test_closing_time_never_precedes_opening_time():
    service, _, table, captured = _service_with_table()
    table.opening_time = local_now() + timedelta(minutes=15)

    service.close_table(
        7,
        CloseTableRequest(
            payments=[ClosingPaymentRequest(method="efectivo", amount=900)]
        ),
        user_id=4,
    )

    assert captured["closing"].closing_time == table.opening_time


def test_cash_closing_calculates_difference_and_links_sales():
    service, session, _, _ = _service_with_table()
    sale = ClosingsModel(
        id=20,
        table_id=2,
        table_number=7,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=4,
        subtotal=1000,
        discount=100,
        total=900,
        status="cerrada",
        payments=[
            ClosingPaymentModel(
                id=1,
                method="efectivo",
                amount=900,
            )
        ],
    )
    _attach_invoice(sale)
    service.cash_repository = MagicMock()
    service.repository.get_unclosed_sales.return_value = [sale]
    captured = {}

    def add_cash_closing(cash_closing):
        cash_closing.id = 30
        captured["cash_closing"] = cash_closing

    service.cash_repository.add.side_effect = add_cash_closing
    service.cash_repository.get_by_id.side_effect = (
        lambda _: captured.get("cash_closing")
    )

    response = service.create_cash_closing(
        CreateCashClosingRequest(
            business_date=date(2026, 6, 9),
            counted_cash=850,
        ),
        user_id=1,
    )

    assert response.expected_cash == 900
    assert response.difference == -50
    assert response.total_sales == 900
    assert response.sales_count == 1
    assert session.commits == 1


@pytest.mark.parametrize(
    ("invoice_status", "issue_code"),
    [
        (INVOICE_PENDING, "INVOICE_PENDING"),
        (INVOICE_AUTHORIZING, "INVOICE_PENDING"),
        (INVOICE_REJECTED, "INVOICE_REJECTED"),
    ],
)
def test_cash_closing_blocks_incomplete_invoice_states(
    invoice_status,
    issue_code,
):
    service, session, _, _ = _service_with_table()
    sale = ClosingsModel(
        id=25,
        table_id=2,
        table_number=7,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=4,
        subtotal=1000,
        discount=0,
        total=1000,
        status="cerrada",
        payments=[
            ClosingPaymentModel(
                id=1,
                method="tarjeta_debito",
                amount=1000,
            )
        ],
    )
    _attach_invoice(sale, status=invoice_status)
    service.repository.get_unclosed_sales.return_value = [sale]

    with pytest.raises(HTTPException) as error:
        service.create_cash_closing(
            CreateCashClosingRequest(
                business_date=date(2026, 6, 9),
                counted_cash=0,
            ),
            user_id=1,
        )

    assert error.value.status_code == HTTPStatus.CONFLICT
    assert error.value.detail["code"] == "CASH_CLOSING_BLOCKED"
    assert any(
        issue["code"] == issue_code
        for issue in error.value.detail["issues"]
    )
    assert session.commits == 0


def test_cash_closing_blocks_sale_without_invoice():
    service, session, _, _ = _service_with_table()
    sale = ClosingsModel(
        id=26,
        table_id=2,
        table_number=7,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=4,
        subtotal=1000,
        discount=0,
        total=1000,
        status="cerrada",
        payments=[
            ClosingPaymentModel(
                id=1,
                method="efectivo",
                amount=1000,
            )
        ],
    )
    service.repository.get_unclosed_sales.return_value = [sale]

    with pytest.raises(HTTPException) as error:
        service.create_cash_closing(
            CreateCashClosingRequest(
                business_date=date(2026, 6, 9),
                counted_cash=1000,
            ),
            user_id=1,
        )

    assert error.value.status_code == HTTPStatus.CONFLICT
    assert any(
        issue["code"] == "SALE_WITHOUT_INVOICE"
        for issue in error.value.detail["issues"]
    )
    assert session.commits == 0


def test_cash_totals_do_not_count_change_as_revenue():
    service, _, _, _ = _service_with_table()
    sale = ClosingsModel(
        id=21,
        table_id=2,
        table_number=7,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=4,
        subtotal=1000,
        discount=100,
        total=900,
        status="cerrada",
        payments=[
            ClosingPaymentModel(
                id=1,
                method="efectivo",
                amount=1000,
            )
        ],
    )

    assert service._payment_totals([sale])["efectivo"] == 900


def test_cash_closing_accepts_explicit_zero_counted_cash():
    service, _, _, _ = _service_with_table()
    sale = ClosingsModel(
        id=22,
        table_id=2,
        table_number=7,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=4,
        subtotal=1000,
        discount=0,
        total=1000,
        status="cerrada",
        payments=[
            ClosingPaymentModel(
                id=1,
                method="tarjeta_debito",
                amount=1000,
            )
        ],
    )
    _attach_invoice(sale)
    service.cash_repository = MagicMock()
    service.repository.get_unclosed_sales.return_value = [sale]
    captured = {}

    def add_cash_closing(cash_closing):
        cash_closing.id = 30
        captured["cash_closing"] = cash_closing

    service.cash_repository.add.side_effect = add_cash_closing
    service.cash_repository.get_by_id.side_effect = (
        lambda _: captured.get("cash_closing")
    )

    response = service.create_cash_closing(
        CreateCashClosingRequest(
            business_date=date(2026, 6, 9),
            counted_cash=0,
        ),
        user_id=1,
    )

    assert response.counted_cash == 0
    assert response.difference == 0


def test_successive_cash_closing_only_uses_new_unclosed_sales():
    service, _, _, _ = _service_with_table()
    sale = ClosingsModel(
        id=27,
        table_id=2,
        table_number=7,
        opening_time=local_now(),
        closing_time=local_now(),
        people=2,
        served_by=4,
        subtotal=500,
        discount=0,
        total=500,
        status="cerrada",
        payments=[
            ClosingPaymentModel(
                id=1,
                method="efectivo",
                amount=500,
            )
        ],
    )
    _attach_invoice(sale)
    service.cash_repository = MagicMock()
    service.repository.get_unclosed_sales.return_value = [sale]
    captured = {}

    def add_cash_closing(cash_closing):
        cash_closing.id = 31
        captured["cash_closing"] = cash_closing

    service.cash_repository.add.side_effect = add_cash_closing
    service.cash_repository.get_by_id.side_effect = (
        lambda _: captured["cash_closing"]
    )

    response = service.create_cash_closing(
        CreateCashClosingRequest(
            business_date=date(2026, 6, 9),
            counted_cash=500,
        ),
        user_id=1,
    )

    assert response.sales_count == 1
    assert response.total_sales == 500
    service.repository.get_unclosed_sales.assert_called_once()
    service.cash_repository.get_by_date.assert_not_called()


def test_cash_closing_update_recalculates_and_records_revision():
    service, session, _, _ = _service_with_table()
    cash_closing = CashClosingModel(
        id=30,
        business_date=date(2026, 6, 9),
        closed_at=local_now(),
        closed_by_id=1,
        total_sales=1000,
        expected_cash=900,
        counted_cash=850,
        difference=-50,
        status="cerrado",
        notes="Original",
        sales=[],
    )
    service.cash_repository = MagicMock()
    service.cash_repository.get_by_id.return_value = cash_closing

    response = service.update_cash_closing(
        30,
        UpdateCashClosingRequest(
            counted_cash=900,
            notes="Corregido",
        ),
        user_id=2,
    )

    assert response.counted_cash == 900
    assert response.difference == 0
    assert response.notes == "Corregido"
    revision = session.added[0]
    assert revision.previous_counted_cash == 850
    assert revision.new_counted_cash == 900
    assert revision.previous_notes == "Original"
    assert revision.new_notes == "Corregido"
    assert revision.changed_by_id == 2
    service.fiscal_period_guard.ensure_cash_closing_mutable.assert_called_once_with(
        cash_closing.id,
        action=f"modificar el cierre de caja {cash_closing.id}",
    )


def test_cash_closing_update_rejects_unchanged_values():
    service, _, _, _ = _service_with_table()
    cash_closing = CashClosingModel(
        id=30,
        business_date=date(2026, 6, 9),
        closed_at=local_now(),
        closed_by_id=1,
        total_sales=1000,
        expected_cash=900,
        counted_cash=900,
        difference=0,
        status="cerrado",
        notes=None,
        sales=[],
    )
    service.cash_repository = MagicMock()
    service.cash_repository.get_by_id.return_value = cash_closing

    with pytest.raises(HTTPException) as error:
        service.update_cash_closing(
            30,
            UpdateCashClosingRequest(counted_cash=900),
            user_id=2,
        )

    assert error.value.status_code == HTTPStatus.CONFLICT


def test_cash_closing_update_rejects_missing_closing():
    service, _, _, _ = _service_with_table()
    service.cash_repository = MagicMock()
    service.cash_repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        service.update_cash_closing(
            999,
            UpdateCashClosingRequest(counted_cash=0),
            user_id=2,
        )

    assert error.value.status_code == HTTPStatus.NOT_FOUND
