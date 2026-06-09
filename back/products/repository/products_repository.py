from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.db_models import (
    OpenTableItemModel,
    ProductInventorySettingsModel,
    ProductModel,
)
from shared.shared_repository import BaseRepository


class ProductsRepository(BaseRepository[ProductModel]):
    def __init__(self, session: Session):
        super().__init__(model=ProductModel, session=session)

    def get_all(self) -> list[ProductModel]:
        statement = (
            select(ProductModel)
            .outerjoin(ProductInventorySettingsModel)
            .where(
                (ProductInventorySettingsModel.deleted_at.is_(None))
                | (ProductInventorySettingsModel.product_id.is_(None))
            )
            .options(selectinload(ProductModel.inventory_settings))
            .order_by(ProductModel.id)
        )
        return list(self.session.scalars(statement).unique().all())

    def get_active_by_id(self, product_id: int) -> ProductModel | None:
        statement = (
            select(ProductModel)
            .outerjoin(ProductInventorySettingsModel)
            .where(
                ProductModel.id == product_id,
                (ProductInventorySettingsModel.deleted_at.is_(None))
                | (ProductInventorySettingsModel.product_id.is_(None)),
            )
            .options(selectinload(ProductModel.inventory_settings))
        )
        return self.session.scalar(statement)

    def is_used_by_open_table(self, product_id: int) -> bool:
        statement = (
            select(OpenTableItemModel.id)
            .where(OpenTableItemModel.product_id == product_id)
            .limit(1)
        )
        return self.session.scalar(statement) is not None
