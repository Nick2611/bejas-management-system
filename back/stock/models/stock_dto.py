from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ManualMovementType = Literal[
    "ajuste_manual",
    "reposicion",
    "merma",
    "correccion",
]


class StockAdjustmentRequest(BaseModel):
    quantity_delta: int
    movement_type: ManualMovementType
    note: str | None = None


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    closing_id: int | None
    created_by_id: int | None
    movement_type: str
    quantity_delta: int
    stock_before: int
    stock_after: int
    created_at: datetime
    note: str | None


class StockAdjustmentResponse(BaseModel):
    product_id: int
    previous_qty: int
    current_qty: int
    movement: StockMovementResponse
