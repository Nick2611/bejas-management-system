from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from closings.service.fiscal_period_guard import FiscalPeriodGuard


@pytest.mark.parametrize(
    ("method_name", "repository_method", "entity_type"),
    [
        ("ensure_sale_mutable", "get_declared_for_sale", "la venta"),
        (
            "ensure_invoice_mutable",
            "get_declared_for_invoice",
            "la factura",
        ),
        (
            "ensure_cash_closing_mutable",
            "get_declared_for_cash_closing",
            "el cierre de caja",
        ),
    ],
)
def test_guard_blocks_only_records_included_in_a_declaration(
    method_name,
    repository_method,
    entity_type,
):
    guard = FiscalPeriodGuard(MagicMock())
    guard.repository = MagicMock()
    getattr(guard.repository, repository_method).return_value = MagicMock(
        id=7,
        period_from=MagicMock(isoformat=lambda: "2026-06-01"),
        period_to=MagicMock(isoformat=lambda: "2026-06-30"),
    )

    with pytest.raises(HTTPException) as error:
        getattr(guard, method_name)(12, action="modificar el registro")

    assert error.value.status_code == 409
    assert error.value.detail == {
        "code": "FISCAL_RECORD_ALREADY_DECLARED",
        "message": (
            f"No se puede modificar el registro: {entity_type} 12 "
            "forma parte de la declaración fiscal 7."
        ),
        "closure_id": 7,
        "period_from": "2026-06-01",
        "period_to": "2026-06-30",
        "entity_type": entity_type,
        "entity_id": 12,
    }


def test_guard_allows_a_sale_not_included_in_a_declaration():
    guard = FiscalPeriodGuard(MagicMock())
    guard.repository = MagicMock()
    guard.repository.get_declared_for_sale.return_value = None

    guard.ensure_sale_mutable(12, action="modificar la venta")

    guard.repository.get_declared_for_sale.assert_called_once_with(12)
