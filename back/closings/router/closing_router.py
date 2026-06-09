from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from auth.auth import is_admin
from closings.models.closing_models import (
    CashClosingRevisionResponse,
    CashClosingResponse,
    ClosingResponse,
    CreateCashClosingRequest,
    MonthlyClosingSummaryResponse,
    UpdateCashClosingRequest,
)
from closings.service.closing_service import ClosingService
from db.db_conn import SessionDep


closing_router = APIRouter(prefix="/closings", tags=["closings"])
cash_closing_router = APIRouter(
    prefix="/cash-closings",
    tags=["cash-closings"],
)
AdminClaims = Annotated[dict, Depends(is_admin)]


@closing_router.get("", response_model=list[ClosingResponse])
def list_closings(
    session: SessionDep,
    claims: AdminClaims,
    start_date: date | None = None,
    end_date: date | None = None,
    status_filter: Literal["cerrada", "anulada"] | None = Query(
        default=None,
        alias="status",
    ),
):
    return ClosingService(session).list_closings(
        start_date,
        end_date,
        status_filter,
    )


@closing_router.get("/{closing_id}", response_model=ClosingResponse)
def get_closing(
    closing_id: int,
    session: SessionDep,
    claims: AdminClaims,
):
    return ClosingService(session).get_closing(closing_id)


@cash_closing_router.post(
    "",
    response_model=CashClosingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cash_closing(
    payload: CreateCashClosingRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return ClosingService(session).create_cash_closing(
        payload,
        int(claims["user_id"]),
    )


@cash_closing_router.get("", response_model=list[CashClosingResponse])
def list_cash_closings(
    session: SessionDep,
    claims: AdminClaims,
):
    return ClosingService(session).list_cash_closings()


@cash_closing_router.patch(
    "/{cash_closing_id}",
    response_model=CashClosingResponse,
)
def update_cash_closing(
    cash_closing_id: int,
    payload: UpdateCashClosingRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return ClosingService(session).update_cash_closing(
        cash_closing_id,
        payload,
        int(claims["user_id"]),
    )


@cash_closing_router.get(
    "/{cash_closing_id}/revisions",
    response_model=list[CashClosingRevisionResponse],
)
def list_cash_closing_revisions(
    cash_closing_id: int,
    session: SessionDep,
    claims: AdminClaims,
):
    return ClosingService(session).list_cash_closing_revisions(
        cash_closing_id
    )


@cash_closing_router.get(
    "/monthly",
    response_model=MonthlyClosingSummaryResponse,
)
def monthly_summary(
    session: SessionDep,
    claims: AdminClaims,
    year: int,
    month: int = Query(ge=1, le=12),
):
    return ClosingService(session).monthly_summary(year, month)
