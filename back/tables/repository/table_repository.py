from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.db_models import OpenTableItemModel, OpenTableModel
from shared.shared_repository import BaseRepository


class TableRepository(BaseRepository[OpenTableModel]):
    def __init__(self, session: Session):
        super().__init__(model=OpenTableModel, session=session)

    def get_all(self) -> list[OpenTableModel]:
        statement = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .options(
                selectinload(self.model.items).selectinload(
                    OpenTableItemModel.product
                )
            )
            .order_by(self.model.table_number))
        return list(self.session.scalars(statement).all())

    def get_by_number(self, number: int) -> OpenTableModel | None:
        statement = (
            select(self.model)
            .where(
                self.model.table_number == number,
                self.model.deleted_at.is_(None),
            )
            .options(
                selectinload(self.model.items).selectinload(
                    OpenTableItemModel.product
                )
            )
        )
        return self.session.scalar(statement)

    def get_any_by_number(self, number: int) -> OpenTableModel | None:
        statement = (
            select(self.model)
            .where(self.model.table_number == number)
            .options(
                selectinload(self.model.items).selectinload(
                    OpenTableItemModel.product
                )
            )
        )
        return self.session.scalar(statement)

    def get_item(self, table_id: int, item_id: int) -> OpenTableItemModel | None:
        statement = select(OpenTableItemModel).where(
            OpenTableItemModel.id == item_id,
            OpenTableItemModel.table_id == table_id,
        )
        return self.session.scalar(statement)
