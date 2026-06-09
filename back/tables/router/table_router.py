from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from auth.auth import is_admin, validate_token
from closings.models.closing_models import CloseTableRequest, CloseTableResponse
from closings.service.closing_service import ClosingService
from db.db_conn import SessionDep
from tables.models.table_models import (
    AddProductRequest,
    AddProductResponse,
    CreateTableRequest,
    OccupyTableRequest,
    RemovePeopleRequest,
    RemovePeopleResponse,
    RemoveProductRequest,
    RemoveProductResponse,
    TableResponse,
    UpdateTableRequest,
)
from tables.service.table_service import TableService


table_router = APIRouter(prefix="/tables", tags=["tables"])
AuthenticatedClaims = Annotated[dict, Depends(validate_token)]
AdminClaims = Annotated[dict, Depends(is_admin)]


@table_router.get("", response_model=list[TableResponse])
def get_all_tables(session: SessionDep, claims: AuthenticatedClaims):
    return TableService(session=session).get_all_tables()


@table_router.get("/{table_number}", response_model=TableResponse)
def get_table(
    table_number: int,
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return TableService(session=session).get_table(number=table_number)


@table_router.post(
    "",
    response_model=TableResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_table(
    payload: CreateTableRequest,
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return TableService(session=session).create_table(payload)


@table_router.delete(
    "/{table_number}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_table(
    table_number: int,
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    TableService(session=session).delete_table(table_number)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@table_router.patch("/{table_number}", response_model=TableResponse)
def update_table(
    table_number: int,
    payload: UpdateTableRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return TableService(session=session).update_table(
        number=table_number,
        payload=payload,
    )


@table_router.patch(
    "/{table_number}/occupancy",
    response_model=TableResponse,
)
def occupy_table(
    table_number: int,
    payload: OccupyTableRequest,
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return TableService(session).occupy_table(table_number, payload)


@table_router.post(
    "/{table_number}/items",
    response_model=AddProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_products(
    table_number: int,
    payload: list[AddProductRequest],
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return TableService(session=session).add_products(
        number=table_number,
        payload=payload,
        user_id=int(claims["user_id"]),
    )


@table_router.patch(
    "/{table_number}/items/{item_id}",
    response_model=RemoveProductResponse,
)
def remove_product(
    table_number: int,
    item_id: int,
    payload: RemoveProductRequest,
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return TableService(session=session).remove_product(
        number=table_number,
        item_id=item_id,
        payload=payload,
        user_id=int(claims["user_id"]),
    )


@table_router.patch(
    "/{table_number}/people",
    response_model=RemovePeopleResponse,
)
def remove_people(
    table_number: int,
    payload: RemovePeopleRequest,
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return TableService(session=session).remove_people(
        number=table_number,
        payload=payload,
    )


@table_router.post(
    "/{table_number}/close",
    response_model=CloseTableResponse,
)
def close_table(
    table_number: int,
    payload: CloseTableRequest,
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return ClosingService(session).close_table(
        table_number,
        payload,
        int(claims["user_id"]),
    )
