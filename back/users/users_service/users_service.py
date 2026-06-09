from sqlalchemy.orm import Session
from typing import Optional
from http import HTTPStatus
from users.users_repository.users_repository import UsersRepository
from shared.shared_repository import BaseRepository
from hashlib import sha256
from fastapi import HTTPException


from users.models.user_dto import *
from db.db_models import UserModel
from shared.utils import commit_session, custom_response
from shared.time_utils import local_now

class UserService():
    def __init__(self, session: Session):
        self.session = session
        self.repository = UsersRepository(session)
    
    def get_user_by_id(self, id: int) -> Optional[GetUserResponse]:
        user = self.repository.get_user_by_id(id)

        if user is None:
            return None

        return GetUserResponse(
            id=user.id,
            username=user.username,
            role=user.role
        )

    def register(self, create_user: CreateUserRequest):
        if self.repository.find_by_username(create_user.username):
            raise HTTPException(
                status_code=409,
                detail="El nombre de usuario ya existe",
            )
        create_user.password = sha256(create_user.password.encode('utf-8')).hexdigest()
        user = UserModel(**create_user.model_dump())


        created_user = self.repository.add(user)

        commit_session(self.session)

        return custom_response(
            response_class=CreateUserResponse,
            id=created_user.id,
            user=created_user.username,
            role=created_user.role,
        )
    
    def login(self, username: str, password: str):
        user = self.repository.find_by_username_and_password(username=username, password=sha256(password.encode('utf-8')).hexdigest())
        if not user:
            raise HTTPException(HTTPStatus.BAD_REQUEST, detail="El user o password son incorrectos")
        else:
            return user

    def get_all_users(self) -> list[GetUserResponse]:
        return [
            GetUserResponse(
                id=user.id,
                username=user.username,
                role=user.role,
            )
            for user in self.repository.get_all()
        ]

    def delete_user(self, user_id: int) -> None:
        user = self.repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Usuario no encontrado",
            )
        if user.role == "admin":
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="Los usuarios administradores no se pueden eliminar",
            )
        user.deleted_at = local_now()
        commit_session(self.session)

    def update_user(
        self,
        user_id: int,
        payload: UpdateUserRequest,
    ) -> GetUserResponse:
        user = self.repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Usuario no encontrado",
            )

        update_data = payload.model_dump(exclude_unset=True)
        if "username" in update_data:
            username = update_data["username"].strip()
            if not username:
                raise HTTPException(
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    detail="El nombre de usuario no puede estar vacío",
                )
            if self.repository.find_by_username_except(username, user_id):
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    detail="El nombre de usuario ya existe",
                )
            user.username = username

        if "password" in update_data:
            user.password = sha256(
                update_data["password"].encode("utf-8")
            ).hexdigest()

        new_role = update_data.get("role")
        if (
            user.role == "admin"
            and new_role == "empleado"
            and self.repository.count_active_admins() <= 1
        ):
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail="No se puede degradar al último administrador",
            )
        if new_role is not None:
            user.role = new_role

        commit_session(self.session)
        return GetUserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
        )
        



        
