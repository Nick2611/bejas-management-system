from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from invoices.models.invoice_models import InvoiceResponse


PaymentMethod = Literal[
    "efectivo",
    "tarjeta_credito",
    "tarjeta_debito",
    "mercado_pago",
]


class ClosingPaymentRequest(BaseModel):
    method: PaymentMethod
    amount: int = Field(gt=0)


class CloseTableRequest(BaseModel):
    payments: list[ClosingPaymentRequest] = Field(
        default_factory=list,
        max_length=2,
    )

    @model_validator(mode="after")
    def validate_unique_methods(self):
        methods = [payment.method for payment in self.payments]
        if len(methods) != len(set(methods)):
            raise ValueError("Los métodos de pago no pueden repetirse")
        return self


class ClosingItemResponse(BaseModel):
    id: int
    product_id: int | None
    product_name: str
    product_type: str
    unit: str
    quantity: int
    unit_price: int
    subtotal: int


class ClosingPaymentResponse(BaseModel):
    id: int
    method: str
    amount: int


class ClosingResponse(BaseModel):
    id: int
    table_number: int
    table_name: str | None
    opening_time: datetime
    closing_time: datetime
    people: int
    served_by: int
    subtotal: int
    discount: int
    total: int
    amount_received: int
    change: int
    status: str
    cash_closing_id: int | None
    items: list[ClosingItemResponse]
    payments: list[ClosingPaymentResponse]
    invoice: InvoiceResponse | None


class CloseTableResponse(BaseModel):
    closing: ClosingResponse
    afip_authorized: bool | None
    warning: str | None


class CreateCashClosingRequest(BaseModel):
    business_date: date
    counted_cash: int = Field(ge=0)
    notes: str | None = None


class UpdateCashClosingRequest(BaseModel):
    counted_cash: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Al menos un campo debe estar ingresado")
        if (
            "counted_cash" in self.model_fields_set
            and self.counted_cash is None
        ):
            raise ValueError("El efectivo contado no puede ser nulo")
        return self


class CashClosingRevisionResponse(BaseModel):
    id: int
    cash_closing_id: int
    changed_by_id: int
    changed_at: datetime
    previous_counted_cash: int
    new_counted_cash: int
    previous_notes: str | None
    new_notes: str | None


class CashClosingResponse(BaseModel):
    id: int
    business_date: date
    closed_at: datetime
    closed_by_id: int
    total_sales: int
    expected_cash: int
    counted_cash: int
    difference: int
    status: str
    notes: str | None
    sales_count: int
    total_credit_card: int
    total_debit_card: int
    total_mercado_pago: int


class MonthlyClosingSummaryResponse(BaseModel):
    year: int
    month: int
    total_sales: int
    sales_count: int
    active_days: int
    daily_average: int
    total_cash: int
    total_credit_card: int
    total_debit_card: int
    total_mercado_pago: int
