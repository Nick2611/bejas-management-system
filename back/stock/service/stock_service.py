from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db.db_models import ProductInventorySettingsModel, StockMovementModel
from products.repository.products_repository import ProductsRepository
from shared.time_utils import local_now
from shared.utils import commit_session
from stock.models.stock_dto import (
    StockAdjustmentRequest,
    StockAdjustmentResponse,
    StockMovementResponse,
)
from stock.repository.stock_repository import StockRepository


class StockService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = StockRepository(session)
        self.products_repository = ProductsRepository(session)

    @staticmethod
    def _movement_response(
        movement: StockMovementModel,
    ) -> StockMovementResponse:
        return StockMovementResponse(
            id=movement.id,
            product_id=movement.product_id,
            product_name=movement.product.name,
            closing_id=movement.closing_id,
            created_by_id=movement.created_by_id,
            movement_type=movement.movement_type,
            quantity_delta=movement.quantity_delta,
            stock_before=movement.stock_before,
            stock_after=movement.stock_after,
            created_at=movement.created_at,
            note=movement.note,
        )

    def adjust_stock(
        self,
        product_id: int,
        payload: StockAdjustmentRequest,
        user_id: int,
    ) -> StockAdjustmentResponse:
        if payload.quantity_delta == 0:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail="El ajuste de stock no puede ser cero",
            )

        product = self.products_repository.get_active_by_id(product_id)
        if product is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Producto no encontrado",
            )

        previous_qty = product.qty
        current_qty = previous_qty + payload.quantity_delta
        if current_qty < 0:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=f"Stock insuficiente. Disponible: {previous_qty}",
            )

        settings = product.inventory_settings
        if (
            payload.quantity_delta > 0
            and settings is not None
            and settings.capacity_qty is not None
            and current_qty > settings.capacity_qty
        ):
            available_capacity = max(settings.capacity_qty - previous_qty, 0)
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=(
                    f"El máximo que puede agregarse es {available_capacity}. "
                    f"Capacidad total: {settings.capacity_qty}"
                ),
            )

        movement = StockMovementModel(
            product=product,
            created_by_id=user_id,
            movement_type=payload.movement_type,
            quantity_delta=payload.quantity_delta,
            stock_before=previous_qty,
            stock_after=current_qty,
            note=payload.note,
        )
        product.qty = current_qty

        if product.inventory_settings is None:
            product.inventory_settings = ProductInventorySettingsModel(
                minimum_qty=0,
                deleted_at=None,
            )
        if payload.quantity_delta > 0:
            product.inventory_settings.last_restocked_at = local_now()

        self.repository.add(movement)
        try:
            commit_session(self.session)
            self.session.refresh(movement)
        except Exception:
            self.session.rollback()
            raise

        return StockAdjustmentResponse(
            product_id=product.id,
            previous_qty=previous_qty,
            current_qty=current_qty,
            movement=self._movement_response(movement),
        )

    def get_movements(
        self,
        product_id: int | None,
        limit: int,
    ) -> list[StockMovementResponse]:
        return [
            self._movement_response(movement)
            for movement in self.repository.get_movements(product_id, limit)
        ]
