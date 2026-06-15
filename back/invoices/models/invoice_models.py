from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


InvoiceStatus = Literal[
    "INVOICE_PENDING",
    "INVOICE_QUEUED",
    "INVOICE_AUTHORIZING",
    "INVOICE_AUTHORIZED",
    "INVOICE_REJECTED",
    "INVOICE_CANCELLED",
    "INVOICE_RETRY_PENDING",
]
RetryableInvoiceStatus = Literal[
    "INVOICE_PENDING",
    "INVOICE_REJECTED",
    "INVOICE_RETRY_PENDING",
]


class InvoiceAttemptResponse(BaseModel):
    id: int
    invoice_id: int
    attempt_number: int
    attempted_at: datetime
    previous_status: str
    new_status: str
    request_payload: dict | None
    response_payload: dict | None
    error_reason: str | None
    worker_id: str | None
    correlation_id: str | None
    success: bool
    error: str | None


class InvoiceResponse(BaseModel):
    id: int
    closing_id: int | None
    closing_ids: list[int]
    voucher_type: str
    point_of_sale: int
    voucher_number: int
    display_number: str
    issued_at: datetime
    declaration_type: Literal["ticket", "diario", "mensual", "legacy"]
    total: int
    sales_count: int
    period_start: datetime | None
    period_end: datetime | None
    cae: str | None
    cae_expiration: Date | None
    authorization_code: str | None
    authorization_date: datetime | None
    rejection_reason: str | None
    fiscal_payload_json: dict | None
    arca_response_json: dict | None
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime
    attempts: list[InvoiceAttemptResponse]


class InvoiceReportResponse(BaseModel):
    date: Date
    cuit: str
    business_name: str
    total_invoiced: int
    invoice_count: int
    invoices: list[InvoiceResponse]


class RetryInvoicePeriodRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period_from: Date | None = Field(default=None, alias="periodFrom")
    period_to: Date | None = Field(default=None, alias="periodTo")
    statuses: list[RetryableInvoiceStatus] = Field(
        default_factory=lambda: [
            "INVOICE_PENDING",
            "INVOICE_REJECTED",
            "INVOICE_RETRY_PENDING",
        ],
    )
    period: Literal["diario", "mensual"] | None = None
    date: Date | None = None
    year: int | None = Field(default=None, ge=1)
    month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def validate_period_fields(self):
        if self.period_from is not None or self.period_to is not None:
            if self.period_from is None or self.period_to is None:
                raise ValueError(
                    "periodFrom y periodTo deben informarse juntos"
                )
            if self.period_to < self.period_from:
                raise ValueError(
                    "periodTo no puede ser anterior a periodFrom"
                )
            if any(
                value is not None
                for value in (self.period, self.date, self.year, self.month)
            ):
                raise ValueError(
                    "No mezcle el rango de fechas con el formato heredado"
                )
            return self

        if self.period is None:
            raise ValueError(
                "Debe indicar periodFrom/periodTo o un período diario/mensual"
            )
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
    status: Literal["encolado", "error", "sin_pendientes"]
    message: str
    queued_count: int
    published_count: int
    invoice_ids: list[int]
    invoices: list[InvoiceResponse]
    sales_count: int
    total: int
    invoice: InvoiceResponse | None


class PendingInvoiceSummaryResponse(BaseModel):
    period: Literal["diario", "mensual"]
    period_start: datetime
    period_end: datetime
    sales_count: int
    total: int
    cash_closing_exists: bool
    can_declare: bool
    blocking_reason: str | None
