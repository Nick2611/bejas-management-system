from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from closings.repository.closing_repository import FiscalClosureRepository


class FiscalPeriodGuard:
    def __init__(self, session: Session):
        self.repository = FiscalClosureRepository(session)

    @staticmethod
    def _raise_declared(
        *,
        closure,
        action: str,
        entity_type: str,
        entity_id: int,
    ) -> None:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "FISCAL_RECORD_ALREADY_DECLARED",
                "message": (
                    f"No se puede {action}: {entity_type} {entity_id} "
                    f"forma parte de la declaración fiscal {closure.id}."
                ),
                "closure_id": closure.id,
                "period_from": closure.period_from.isoformat(),
                "period_to": closure.period_to.isoformat(),
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
        )

    def ensure_sale_mutable(self, sale_id: int, *, action: str) -> None:
        closure = self.repository.get_declared_for_sale(sale_id)
        if closure is not None:
            self._raise_declared(
                closure=closure,
                action=action,
                entity_type="la venta",
                entity_id=sale_id,
            )

    def ensure_invoice_mutable(
        self,
        invoice_id: int,
        *,
        action: str,
    ) -> None:
        closure = self.repository.get_declared_for_invoice(invoice_id)
        if closure is not None:
            self._raise_declared(
                closure=closure,
                action=action,
                entity_type="la factura",
                entity_id=invoice_id,
            )

    def ensure_cash_closing_mutable(
        self,
        cash_closing_id: int,
        *,
        action: str,
    ) -> None:
        closure = self.repository.get_declared_for_cash_closing(
            cash_closing_id
        )
        if closure is not None:
            self._raise_declared(
                closure=closure,
                action=action,
                entity_type="el cierre de caja",
                entity_id=cash_closing_id,
            )
