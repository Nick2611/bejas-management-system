from datetime import date
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from db.db_models import ProductInventorySettingsModel, ProductModel
from shared.time_utils import period_dates
from stock.models.stock_dto import StockAdjustmentRequest
from stock.service.stock_service import StockService


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, movement):
        movement.id = 1
        movement.product_id = movement.product.id
        movement.created_at = movement.created_at or date.today()


def _stock_service(qty=10):
    session = FakeSession()
    service = StockService(session)
    product = ProductModel(
        id=2,
        name="Golden",
        type="cerveza",
        price=3000,
        qty=qty,
        unit="pinta",
        inventory_settings=ProductInventorySettingsModel(
            minimum_qty=3,
            capacity_qty=30,
            deleted_at=None,
        ),
    )
    service.products_repository = MagicMock()
    service.products_repository.get_active_by_id.return_value = product
    service.repository = MagicMock()

    def add_movement(movement):
        movement.id = 1
        movement.product_id = product.id
        movement.created_at = movement.created_at or date.today()

    service.repository.add.side_effect = add_movement
    return service, session, product


def test_stock_adjustment_updates_product_and_audit_movement():
    service, session, product = _stock_service()

    response = service.adjust_stock(
        2,
        StockAdjustmentRequest(
            quantity_delta=5,
            movement_type="reposicion",
            note="Compra semanal",
        ),
        user_id=1,
    )

    assert product.qty == 15
    assert response.previous_qty == 10
    assert response.current_qty == 15
    assert response.movement.stock_before == 10
    assert response.movement.stock_after == 15
    assert response.movement.created_by_id == 1
    assert session.commits == 1


def test_stock_adjustment_rejects_negative_result():
    service, session, product = _stock_service(qty=2)

    with pytest.raises(HTTPException) as error:
        service.adjust_stock(
            2,
            StockAdjustmentRequest(
                quantity_delta=-3,
                movement_type="merma",
            ),
            user_id=1,
        )

    assert error.value.status_code == HTTPStatus.CONFLICT
    assert product.qty == 2
    assert session.commits == 0


def test_stock_adjustment_rejects_quantity_above_capacity():
    service, session, product = _stock_service(qty=28)

    with pytest.raises(HTTPException) as error:
        service.adjust_stock(
            2,
            StockAdjustmentRequest(
                quantity_delta=5,
                movement_type="reposicion",
            ),
            user_id=1,
        )

    assert error.value.status_code == HTTPStatus.CONFLICT
    assert "máximo que puede agregarse es 2" in error.value.detail
    assert product.qty == 28
    assert session.commits == 0


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("diario", (date(2026, 6, 9), date(2026, 6, 9))),
        ("semanal", (date(2026, 6, 8), date(2026, 6, 14))),
        ("mensual", (date(2026, 6, 1), date(2026, 6, 30))),
    ],
)
def test_goal_period_dates(period, expected):
    assert period_dates(period, date(2026, 6, 9)) == expected
