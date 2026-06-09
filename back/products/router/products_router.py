from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from auth.auth import is_admin, validate_token
from db.db_conn import SessionDep
from products.models.products_dto import (
    CreateProductRequest,
    CreateProductResponse,
    ProductResponse,
    UpdateProductRequest,
    UpdateProductResponse,
)
from products.service.products_service import ProductsService


products_router = APIRouter(prefix="/products", tags=["products"])
AuthenticatedClaims = Annotated[dict, Depends(validate_token)]
AdminClaims = Annotated[dict, Depends(is_admin)]


@products_router.get("/all", response_model=list[ProductResponse])
def get_all_products(
    session: SessionDep,
    claims: AuthenticatedClaims,
):
    return ProductsService(session=session).get_all_products()


@products_router.post(
    "/create",
    response_model=CreateProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: CreateProductRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return ProductsService(session=session).add_product(payload=payload)


@products_router.patch(
    "/update/{id}",
    response_model=UpdateProductResponse,
)
def update_product(
    id: int,
    payload: UpdateProductRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return ProductsService(session=session).update_product(
        product_id=id,
        request=payload,
        user_id=int(claims["user_id"]),
    )


@products_router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_product(
    product_id: int,
    session: SessionDep,
    claims: AdminClaims,
):
    ProductsService(session=session).delete_product(product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
