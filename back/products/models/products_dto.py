from datetime import datetime
from http import HTTPStatus

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str
    price: int
    unit: str
    qty: int
    minimum_qty: int = 0
    capacity_qty: int | None = None
    last_restocked_at: datetime | None = None


class CreateProductRequest(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    price: int = Field(gt=0)
    qty: int = Field(ge=0)
    unit: str = Field(min_length=1)
    minimum_qty: int = Field(default=0, ge=0)
    capacity_qty: int | None = Field(default=None, gt=0)


class CreateProductResponse(BaseModel):
    status: HTTPStatus
    id: int
    name: str


class UpdateProductRequest(BaseModel):
    qty: int | None = Field(default=None, ge=0)
    price: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    unit: str | None = Field(default=None, min_length=1)
    minimum_qty: int | None = Field(default=None, ge=0)
    capacity_qty: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Al menos un campo debe estar ingresado")
        return self


class UpdateProductResponse(ProductResponse):
    status: HTTPStatus


class GetProductByIdRequest(BaseModel):
    id: int
    name: str | None = None


GetProductResponse = ProductResponse
