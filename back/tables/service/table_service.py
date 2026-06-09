from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db.db_models import (
    OpenTableItemModel,
    OpenTableModel,
    ProductModel,
    StockMovementModel,
)
from products.repository.products_repository import ProductsRepository
from shared.utils import commit_session
from tables.models.table_models import (
    AddProductRequest,
    AddProductResponse,
    CreateTableRequest,
    RemovePeopleRequest,
    RemovePeopleResponse,
    RemoveProductRequest,
    RemoveProductResponse,
    TableItemResponse,
    OccupyTableRequest,
    UpdateTableRequest,
)
from tables.repository.table_repository import TableRepository
from shared.time_utils import local_now


class TableService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = TableRepository(session=session)

    def get_all_tables(self) -> list[OpenTableModel]:
        return self.repository.get_all()

    def get_table(self, number: int) -> OpenTableModel:
        return self._get_table_or_404(number)

    def create_table(self, payload: CreateTableRequest) -> OpenTableModel:
        existing_table = self.repository.get_any_by_number(payload.table_number)
        if existing_table is not None and existing_table.deleted_at is None:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=f"La mesa {payload.table_number} ya existe",
            )

        if existing_table is not None:
            existing_table.table_name = payload.table_name
            existing_table.people = 0
            existing_table.opening_time = local_now()
            existing_table.deleted_at = None
            commit_session(self.session)
            return existing_table

        table = OpenTableModel(
            **payload.model_dump(),
            opening_time=local_now(),
            deleted_at=None,
        )
        self.repository.add(table)
        commit_session(self.session)
        return table

    def occupy_table(
        self,
        number: int,
        payload: OccupyTableRequest,
    ) -> OpenTableModel:
        table = self._get_table_or_404(number)
        if table.people > 0 or table.items:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=f"La mesa {number} ya está ocupada",
            )
        table.people = payload.people
        table.opening_time = local_now()
        commit_session(self.session)
        return table

    def delete_table(self, number: int) -> None:
        table = self._get_table_or_404(number)
        if table.people > 0 or table.items:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="No se puede eliminar una mesa ocupada o con consumos",
            )
        table.deleted_at = local_now()
        commit_session(self.session)

    def update_table(
        self,
        number: int,
        payload: UpdateTableRequest,
    ) -> OpenTableModel:
        table = self._get_table_or_404(number)
        update_data = payload.model_dump(exclude_unset=True)
        self.repository.update(entity=table, data=update_data)
        commit_session(self.session)
        return table

    def add_products(
        self,
        number: int,
        payload: list[AddProductRequest],
        user_id: int | None = None,
    ) -> AddProductResponse:
        if not payload:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail="Debe agregar al menos un producto",
            )

        table = self._get_table_or_404(number)
        product_repository = ProductsRepository(session=self.session)
        added_items: list[OpenTableItemModel] = []

        try:
            for request in payload:
                product = product_repository.get_active_by_id(
                    request.product_id
                )
                if product is None:
                    raise HTTPException(
                        status_code=HTTPStatus.NOT_FOUND,
                        detail=f"El producto {request.product_id} no existe",
                    )

                if product.qty < request.quantity:
                    raise HTTPException(
                        status_code=HTTPStatus.CONFLICT,
                        detail=(
                            f"Stock insuficiente para {product.name}. "
                            f"Disponible: {product.qty}, solicitado: {request.quantity}"
                        ),
                    )

                previous_qty = product.qty
                item = OpenTableItemModel(
                    product=product,
                    quantity=request.quantity,
                    curr_price=product.price,
                )
                product.qty -= request.quantity
                table.items.append(item)
                added_items.append(item)
                self.session.add(
                    StockMovementModel(
                        product=product,
                        created_by_id=user_id,
                        movement_type="venta",
                        quantity_delta=-request.quantity,
                        stock_before=previous_qty,
                        stock_after=product.qty,
                        note=f"Consumo agregado a mesa {number}",
                    )
                )

            commit_session(self.session)
        except Exception:
            self.session.rollback()
            raise

        return AddProductResponse(
            table_number=table.table_number,
            added_items=[
                TableItemResponse.model_validate(item) for item in added_items
            ],
        )

    def remove_product(
        self,
        number: int,
        item_id: int,
        payload: RemoveProductRequest,
        user_id: int | None = None,
    ) -> RemoveProductResponse:
        table = self._get_table_or_404(number)
        item = self.repository.get_item(table_id=table.id, item_id=item_id)
        if item is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"El consumo {item_id} no pertenece a la mesa {number}",
            )

        if payload.quantity_to_remove > item.quantity:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=(
                    f"No se pueden quitar {payload.quantity_to_remove} unidades. "
                    f"El consumo tiene {item.quantity}"
                ),
            )

        product_repository = ProductsRepository(session=self.session)
        product = product_repository.get_active_by_id(item.product_id)
        if product is None:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=f"El producto asociado al consumo {item_id} ya no existe",
            )

        removed_quantity = payload.quantity_to_remove
        remaining_quantity = item.quantity - removed_quantity
        removed_item_id = item.id
        product_id = item.product_id

        try:
            previous_qty = product.qty
            product.qty += removed_quantity
            if remaining_quantity == 0:
                self.session.delete(item)
            else:
                item.quantity = remaining_quantity

            self.session.add(
                StockMovementModel(
                    product=product,
                    created_by_id=user_id,
                    movement_type="devolucion_mesa",
                    quantity_delta=removed_quantity,
                    stock_before=previous_qty,
                    stock_after=product.qty,
                    note=f"Consumo retirado de mesa {number}",
                )
            )

            commit_session(self.session)
        except Exception:
            self.session.rollback()
            raise

        return RemoveProductResponse(
            table_number=table.table_number,
            item_id=removed_item_id,
            product_id=product_id,
            removed_quantity=removed_quantity,
            remaining_quantity=remaining_quantity,
        )

    def remove_people(
        self,
        number: int,
        payload: RemovePeopleRequest,
    ) -> RemovePeopleResponse:
        table = self._get_table_or_404(number)
        previous_people = table.people or 0

        if payload.quantity_to_remove > previous_people:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=(
                    f"No se pueden quitar {payload.quantity_to_remove} comensales. "
                    f"La mesa tiene {previous_people}"
                ),
            )

        table.people = previous_people - payload.quantity_to_remove
        commit_session(self.session)

        return RemovePeopleResponse(
            table_number=table.table_number,
            removed_people=payload.quantity_to_remove,
            previous_people=previous_people,
            current_people=table.people,
        )

    def _get_table_or_404(self, number: int) -> OpenTableModel:
        table = self.repository.get_by_number(number=number)
        if table is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"La mesa {number} no existe",
            )
        return table
