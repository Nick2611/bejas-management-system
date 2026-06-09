from typing import Annotated

from fastapi import APIRouter, Depends, Query

from auth.auth import is_admin
from db.db_conn import SessionDep
from stock.models.stock_dto import (
    StockAdjustmentRequest,
    StockAdjustmentResponse,
    StockMovementResponse,
)
from stock.service.stock_service import StockService


stock_router = APIRouter(prefix="/stock", tags=["stock"])
AdminClaims = Annotated[dict, Depends(is_admin)]


@stock_router.post(
    "/products/{product_id}/adjustments",
    response_model=StockAdjustmentResponse,
)
def adjust_stock(
    product_id: int,
    payload: StockAdjustmentRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return StockService(session).adjust_stock(
        product_id=product_id,
        payload=payload,
        user_id=int(claims["user_id"]),
    )


@stock_router.get("/movements", response_model=list[StockMovementResponse])
def get_stock_movements(
    session: SessionDep,
    claims: AdminClaims,
    product_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    return StockService(session).get_movements(product_id, limit)
