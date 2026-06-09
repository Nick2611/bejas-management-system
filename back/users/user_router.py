from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth.auth import is_admin
from db.db_conn import SessionDep
from users.models.user_dto import GetUserResponse, UpdateUserRequest
from users.users_service.users_service import UserService


user_router = APIRouter(prefix="/users", tags=["users"])
AdminClaims = Annotated[dict, Depends(is_admin)]


@user_router.get("", response_model=list[GetUserResponse])
def list_users(session: SessionDep, claims: AdminClaims):
    return UserService(session).get_all_users()


@user_router.patch("/{user_id}", response_model=GetUserResponse)
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    session: SessionDep,
    claims: AdminClaims,
):
    if (
        user_id == int(claims["user_id"])
        and payload.role is not None
        and payload.role != claims["role"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puede modificar su propio rol durante la sesión",
        )
    return UserService(session).update_user(user_id, payload)


@user_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user(
    user_id: int,
    session: SessionDep,
    claims: AdminClaims,
):
    UserService(session).delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
