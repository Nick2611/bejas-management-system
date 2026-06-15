from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from auth.auth import is_admin
from db.db_conn import SessionDep
from invoices.models.invoice_models import (
    InvoiceReportResponse,
    InvoiceResponse,
    PendingInvoiceSummaryResponse,
    RetryInvoicePeriodRequest,
    RetryInvoicePeriodResponse,
)
from invoices.service.invoice_service import InvoiceService


invoice_router = APIRouter(prefix="/invoices", tags=["invoices"])
AdminClaims = Annotated[dict, Depends(is_admin)]


@invoice_router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    session: SessionDep,
    claims: AdminClaims,
    date_filter: date | None = None,
):
    return InvoiceService(session).list_invoices(date_filter)


@invoice_router.get("/report", response_model=InvoiceReportResponse)
def invoice_report(
    date: date,
    session: SessionDep,
    claims: AdminClaims,
):
    return InvoiceService(session).report(date)


@invoice_router.get(
    "/pending-summary",
    response_model=PendingInvoiceSummaryResponse,
)
def pending_invoice_summary(
    session: SessionDep,
    claims: AdminClaims,
    period: Literal["diario", "mensual"],
    date_filter: date | None = Query(default=None, alias="date"),
    year: int | None = Query(default=None, ge=1),
    month: int | None = Query(default=None, ge=1, le=12),
):
    try:
        payload = RetryInvoicePeriodRequest(
            period=period,
            date=date_filter,
            year=year,
            month=month,
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=error.errors(),
        ) from error
    return InvoiceService(session).pending_summary(payload)


@invoice_router.post(
    "/retry-period",
    response_model=RetryInvoicePeriodResponse,
)
def retry_invoice_period(
    payload: RetryInvoicePeriodRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return InvoiceService(session).retry_period(payload)


@invoice_router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    session: SessionDep,
    claims: AdminClaims,
):
    return InvoiceService(session).get_invoice(invoice_id)


@invoice_router.post("/{invoice_id}/retry", response_model=InvoiceResponse)
def retry_invoice(
    invoice_id: int,
    session: SessionDep,
    claims: AdminClaims,
):
    return InvoiceService(session).retry(invoice_id)
