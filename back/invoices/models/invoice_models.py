from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class InvoiceAttemptResponse(BaseModel):
    id: int
    attempted_at: datetime
    success: bool
    error: str | None


class InvoiceResponse(BaseModel):
    id: int
    closing_id: int
    voucher_type: str
    point_of_sale: int
    voucher_number: int
    display_number: str
    issued_at: datetime
    cae: str | None
    cae_expiration: Date | None
    status: str
    attempts: list[InvoiceAttemptResponse]


class InvoiceReportResponse(BaseModel):
    date: Date
    cuit: str
    business_name: str
    total_invoiced: int
    invoice_count: int
    invoices: list[InvoiceResponse]


class RetryInvoicePeriodRequest(BaseModel):
    period: Literal["diario", "mensual"]
    date: Date | None = None
    year: int | None = Field(default=None, ge=1)
    month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def validate_period_fields(self):
        if self.period == "diario":
            if self.date is None:
                raise ValueError("La fecha es obligatoria para el período diario")
            if self.year is not None or self.month is not None:
                raise ValueError(
                    "El período diario sólo acepta el campo date"
                )
        else:
            if self.year is None or self.month is None:
                raise ValueError(
                    "El año y el mes son obligatorios para el período mensual"
                )
            if self.date is not None:
                raise ValueError(
                    "El período mensual no acepta el campo date"
                )
        return self


class RetryInvoicePeriodResponse(BaseModel):
    status: Literal["completado", "parcial", "error", "sin_pendientes"]
    message: str
    processed_count: int
    authorized_count: int
    failed_count: int
    invoices: list[InvoiceResponse]
