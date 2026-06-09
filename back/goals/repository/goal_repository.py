from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.db_models import ClosingsModel, SalesGoalModel
from shared.shared_repository import BaseRepository


class GoalRepository(BaseRepository[SalesGoalModel]):
    def __init__(self, session: Session):
        super().__init__(model=SalesGoalModel, session=session)

    def get_all(self) -> list[SalesGoalModel]:
        statement = (
            select(SalesGoalModel)
            .where(SalesGoalModel.deleted_at.is_(None))
            .order_by(
                SalesGoalModel.start_date.desc(),
                SalesGoalModel.id.desc(),
            )
        )
        return list(self.session.scalars(statement).all())

    def get_by_id(self, goal_id: int) -> SalesGoalModel | None:
        return self.session.scalar(
            select(SalesGoalModel).where(
                SalesGoalModel.id == goal_id,
                SalesGoalModel.deleted_at.is_(None),
            )
        )

    def sales_total(self, start: datetime, end: datetime) -> int:
        statement = select(func.coalesce(func.sum(ClosingsModel.total), 0)).where(
            ClosingsModel.status == "cerrada",
            ClosingsModel.closing_time >= start,
            ClosingsModel.closing_time < end,
        )
        return int(self.session.scalar(statement) or 0)
