from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from auth.auth import is_admin
from db.db_conn import SessionDep
from invoices.models.invoice_models import (
    InvoiceReportResponse,
    InvoiceResponse,
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
