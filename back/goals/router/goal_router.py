from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from auth.auth import is_admin
from db.db_conn import SessionDep
from goals.models.goal_models import (
    CreateGoalRequest,
    GoalResponse,
    UpdateGoalRequest,
)
from goals.service.goal_service import GoalService


goal_router = APIRouter(prefix="/goals", tags=["goals"])
AdminClaims = Annotated[dict, Depends(is_admin)]


@goal_router.get("", response_model=list[GoalResponse])
def list_goals(session: SessionDep, claims: AdminClaims):
    return GoalService(session).get_all()


@goal_router.post(
    "",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    payload: CreateGoalRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return GoalService(session).create(payload, int(claims["user_id"]))


@goal_router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    payload: UpdateGoalRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    return GoalService(session).update(goal_id, payload)


@goal_router.delete(
    "/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_goal(
    goal_id: int,
    session: SessionDep,
    claims: AdminClaims,
):
    GoalService(session).delete(goal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
