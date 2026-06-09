from datetime import datetime, time, timedelta
from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db.db_models import SalesGoalModel
from goals.models.goal_models import (
    CreateGoalRequest,
    GoalResponse,
    UpdateGoalRequest,
)
from goals.repository.goal_repository import GoalRepository
from shared.time_utils import local_now, period_dates
from shared.utils import commit_session


class GoalService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = GoalRepository(session)

    def _response(self, goal: SalesGoalModel) -> GoalResponse:
        start = datetime.combine(goal.start_date, time.min)
        end = datetime.combine(goal.end_date + timedelta(days=1), time.min)
        current_sales = self.repository.sales_total(start, end)
        progress = min(
            (current_sales / goal.target_amount) * 100,
            100,
        )
        return GoalResponse(
            id=goal.id,
            period=goal.period,
            target_amount=goal.target_amount,
            description=goal.description,
            start_date=goal.start_date,
            end_date=goal.end_date,
            created_by_id=goal.created_by_id,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            current_sales=current_sales,
            progress=progress,
        )

    def get_all(self) -> list[GoalResponse]:
        return [self._response(goal) for goal in self.repository.get_all()]

    def create(
        self,
        payload: CreateGoalRequest,
        user_id: int,
    ) -> GoalResponse:
        start, end = period_dates(payload.period, payload.reference_date)
        now = local_now()
        goal = SalesGoalModel(
            period=payload.period,
            target_amount=payload.target_amount,
            description=payload.description,
            start_date=start,
            end_date=end,
            created_by_id=user_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.repository.add(goal)
        commit_session(self.session)
        self.session.refresh(goal)
        return self._response(goal)

    def update(
        self,
        goal_id: int,
        payload: UpdateGoalRequest,
    ) -> GoalResponse:
        goal = self.repository.get_by_id(goal_id)
        if goal is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Objetivo no encontrado",
            )
        changes = payload.model_dump(exclude_unset=True)
        reference_date = changes.pop("reference_date", None)
        period = changes.get("period", goal.period)
        if "period" in changes or reference_date is not None:
            goal.start_date, goal.end_date = period_dates(
                period,
                reference_date or goal.start_date,
            )
        for key, value in changes.items():
            setattr(goal, key, value)
        goal.updated_at = local_now()
        commit_session(self.session)
        return self._response(goal)

    def delete(self, goal_id: int) -> None:
        goal = self.repository.get_by_id(goal_id)
        if goal is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Objetivo no encontrado",
            )
        goal.deleted_at = local_now()
        commit_session(self.session)
