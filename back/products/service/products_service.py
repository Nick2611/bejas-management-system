from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db.db_models import (
    ProductInventorySettingsModel,
    ProductModel,
    StockMovementModel,
)
from products.models.products_dto import (
    CreateProductRequest,
    CreateProductResponse,
    ProductResponse,
    UpdateProductRequest,
    UpdateProductResponse,
)
from products.repository.products_repository import ProductsRepository
from shared.time_utils import local_now
from shared.utils import commit_session


class ProductsService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ProductsRepository(session=session)

    @staticmethod
    def _response(product: ProductModel) -> ProductResponse:
        settings = product.inventory_settings
        return ProductResponse(
            id=product.id,
            name=product.name,
            type=product.type,
            price=product.price,
            qty=product.qty,
            unit=product.unit,
            minimum_qty=settings.minimum_qty if settings else 0,
            capacity_qty=settings.capacity_qty if settings else None,
            last_restocked_at=settings.last_restocked_at if settings else None,
        )

    def get_all_products(self) -> list[ProductResponse]:
        return [self._response(product) for product in self.repository.get_all()]

    def get_product_by_id(self, product_id: int) -> ProductModel:
        product = self.repository.get_active_by_id(product_id)
        if product is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Producto no encontrado",
            )
        return product

    def add_product(
        self,
        payload: CreateProductRequest,
    ) -> CreateProductResponse:
        product_data = payload.model_dump(
            exclude={"minimum_qty", "capacity_qty"}
        )
        product = ProductModel(**product_data)
        product.inventory_settings = ProductInventorySettingsModel(
            minimum_qty=payload.minimum_qty,
            capacity_qty=payload.capacity_qty,
            last_restocked_at=local_now() if payload.qty > 0 else None,
            deleted_at=None,
        )
        self.repository.add(product)
        commit_session(self.session)
        self.session.refresh(product)
        return CreateProductResponse(
            status=HTTPStatus.CREATED,
            id=product.id,
            name=product.name,
        )

    def update_product(
        self,
        product_id: int,
        request: UpdateProductRequest,
        user_id: int,
    ) -> UpdateProductResponse:
        product = self.get_product_by_id(product_id)
        update_data = request.model_dump(exclude_unset=True)
        capacity_was_provided = "capacity_qty" in request.model_fields_set
        minimum_qty = update_data.pop("minimum_qty", None)
        capacity_qty = update_data.pop("capacity_qty", None)
        new_qty = update_data.pop("qty", None)
        update_data = {
            key: value
            for key, value in update_data.items()
            if value is not None
        }

        self.repository.update(product, update_data)
        settings = product.inventory_settings
        if settings is None:
            settings = ProductInventorySettingsModel(
                product=product,
                minimum_qty=0,
                deleted_at=None,
            )
        if minimum_qty is not None:
            settings.minimum_qty = minimum_qty
        if capacity_was_provided:
            settings.capacity_qty = capacity_qty

        if new_qty is not None and new_qty != product.qty:
            previous_qty = product.qty
            delta = new_qty - previous_qty
            product.qty = new_qty
            self.session.add(
                StockMovementModel(
                    product=product,
                    created_by_id=user_id,
                    movement_type="correccion",
                    quantity_delta=delta,
                    stock_before=previous_qty,
                    stock_after=new_qty,
                    note="Actualización desde configuración",
                )
            )
            if delta > 0:
                settings.last_restocked_at = local_now()

        try:
            commit_session(self.session)
            self.session.refresh(product)
        except Exception:
            self.session.rollback()
            raise

        response = self._response(product)
        return UpdateProductResponse(
            status=HTTPStatus.OK,
            **response.model_dump(),
        )

    def delete_product(self, product_id: int) -> None:
        product = self.get_product_by_id(product_id)
        if self.repository.is_used_by_open_table(product_id):
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="El producto está siendo usado por una mesa abierta",
            )

        settings = product.inventory_settings
        if settings is None:
            settings = ProductInventorySettingsModel(
                product=product,
                minimum_qty=0,
            )
        settings.deleted_at = local_now()
        commit_session(self.session)
