from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.db_models import ClosingsModel, UserModel


class KpiRepository:
    def __init__(self, session: Session):
        self.session = session

    def period_summary(
        self,
        start: datetime,
        end: datetime,
    ) -> tuple[int, int]:
        statement = select(
            func.coalesce(func.sum(ClosingsModel.total), 0),
            func.count(ClosingsModel.id),
        ).where(
            ClosingsModel.status == "cerrada",
            ClosingsModel.closing_time >= start,
            ClosingsModel.closing_time < end,
        )
        total, count = self.session.execute(statement).one()
        return int(total or 0), int(count or 0)

    def employee_performance(
        self,
        start: datetime,
        end: datetime,
    ) -> list[tuple[int, str, int, int]]:
        statement = (
            select(
                UserModel.id,
                UserModel.username,
                func.count(ClosingsModel.id).label("closed_tables"),
                func.coalesce(func.sum(ClosingsModel.total), 0).label(
                    "total_sales"
                ),
            )
            .join(ClosingsModel, ClosingsModel.served_by == UserModel.id)
            .where(
                ClosingsModel.status == "cerrada",
                ClosingsModel.closing_time >= start,
                ClosingsModel.closing_time < end,
            )
            .group_by(UserModel.id, UserModel.username)
            .order_by(
                func.count(ClosingsModel.id).desc(),
                func.sum(ClosingsModel.total).desc(),
                UserModel.username,
            )
        )
        return [
            (int(user_id), username, int(closed_tables), int(total_sales))
            for user_id, username, closed_tables, total_sales
            in self.session.execute(statement).all()
        ]
