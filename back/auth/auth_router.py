from fastapi import APIRouter
from http import HTTPStatus
from db.db_conn import SessionDep
from auth.utils.jwt_encode import jwt_encode_user
from auth.auth import is_admin, validate_token
from users.models.user_dto import CreateUserRequest, LoginRequest
from fastapi import HTTPException, Depends, Request

from typing import Annotated


from users.users_service.users_service import UserService
from auth.auth_models import Token

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)

auth_router = APIRouter(prefix="/auth")

@auth_router.post("")
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    session: SessionDep, 
    ):
    users_service = UserService(session)
    user = users_service.login(payload.username, payload.password)
    token = jwt_encode_user(user)
    return Token(access_token=token, token_type='bearer')


@auth_router.post("/register")
def register(
    payload: CreateUserRequest,
    session: SessionDep,
    claims: Annotated[dict, Depends(is_admin)],
):
    users_service = UserService(session)
    user = users_service.register(create_user=payload)

    if user is None:
        raise HTTPException(
            status_code=400,
            detail="User could not be created"
        )

    return user

@auth_router.get("/validate")
def validate(claims: Annotated[dict, Depends(validate_token)]):
    return claims
