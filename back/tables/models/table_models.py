from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class CreateTableRequest(BaseModel):
    table_number: int = Field(gt=0)
    table_name: str | None = None
    people: int = Field(default=0, ge=0)


class UpdateTableRequest(BaseModel):
    table_name: str | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un campo para actualizar")
        return self


class OccupyTableRequest(BaseModel):
    people: int = Field(gt=0)


class AddProductRequest(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class RemoveProductRequest(BaseModel):
    quantity_to_remove: int = Field(gt=0)


class RemovePeopleRequest(BaseModel):
    quantity_to_remove: int = Field(gt=0)


class TableItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    curr_price: int


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    table_number: int
    table_name: str | None
    opening_time: datetime
    people: int
    items: list[TableItemResponse]

    @field_validator("people", mode="before")
    @classmethod
    def normalize_people(cls, value):
        return value if value is not None else 0


class AddProductResponse(BaseModel):
    table_number: int
    added_items: list[TableItemResponse]


class RemoveProductResponse(BaseModel):
    table_number: int
    item_id: int
    product_id: int
    removed_quantity: int
    remaining_quantity: int


class RemovePeopleResponse(BaseModel):
    table_number: int
    removed_people: int
    previous_people: int
    current_people: int
