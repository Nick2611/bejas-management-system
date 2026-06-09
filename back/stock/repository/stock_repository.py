from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.db_models import StockMovementModel
from shared.shared_repository import BaseRepository


class StockRepository(BaseRepository[StockMovementModel]):
    def __init__(self, session: Session):
        super().__init__(model=StockMovementModel, session=session)

    def get_movements(
        self,
        product_id: int | None = None,
        limit: int = 200,
    ) -> list[StockMovementModel]:
        statement = (
            select(StockMovementModel)
            .options(selectinload(StockMovementModel.product))
            .order_by(StockMovementModel.created_at.desc())
            .limit(limit)
        )
        if product_id is not None:
            statement = statement.where(
                StockMovementModel.product_id == product_id
            )
        return list(self.session.scalars(statement).all())
