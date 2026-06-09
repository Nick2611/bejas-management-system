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
    OpenTableItemModel,
    OpenTableModel,
    ProductModel,
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
    service.repository = MagicMock()
    service.repository.add.side_effect = add_closing
    service.repository.get_by_id.side_effect = lambda _: captured["closing"]
    service.invoice_service = MagicMock()
    return service, session, table, captured


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
    assert response.closing.invoice is None
    assert captured["closing"].items[0].product_name == "IPA"
    assert table.people == 0
    assert table.items == []
    assert session.commits == 1


def test_split_payment_uses_discount_on_full_subtotal():
    service, _, _, _ = _service_with_table(price=1000, quantity=2)
    service.invoice_service.create_for_closing.return_value = (None, True)
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
    assert session.commits == 1


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
    service.cash_repository = MagicMock()
    service.cash_repository.get_by_date.side_effect = [None, None]
    service.repository.get_unclosed_sales.return_value = [sale]
    captured = {}

    def add_cash_closing(cash_closing):
        cash_closing.id = 30
        captured["cash_closing"] = cash_closing

    service.cash_repository.add.side_effect = add_cash_closing
    service.cash_repository.get_by_date.side_effect = [
        None,
        lambda: captured["cash_closing"],
    ]
    service.cash_repository.get_by_date.side_effect = (
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
    service.cash_repository = MagicMock()
    service.repository.get_unclosed_sales.return_value = [sale]
    captured = {}

    def add_cash_closing(cash_closing):
        cash_closing.id = 30
        captured["cash_closing"] = cash_closing

    service.cash_repository.add.side_effect = add_cash_closing
    service.cash_repository.get_by_date.side_effect = (
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
