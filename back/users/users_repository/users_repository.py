from sqlalchemy.orm import Session
from shared.shared_repository import BaseRepository
from db.db_models import UserModel
from sqlalchemy import func, select


class UsersRepository(BaseRepository[UserModel]):
    def __init__(self, session: Session):
        super().__init__(model=UserModel, session=session)

    def find_by_username(self, username: str):
        return self.session.scalar(
            select(UserModel).where(
                UserModel.username == username,
                UserModel.deleted_at.is_(None),
            )
        )

    def get_all(self):
        return list(
            self.session.scalars(
                select(UserModel)
                .where(UserModel.deleted_at.is_(None))
                .order_by(UserModel.username)
            ).all()
        )

    def get_user_by_id(self, user_id: int):
        return self.session.scalar(
            select(UserModel).where(
                UserModel.id == user_id,
                UserModel.deleted_at.is_(None),
            )
        )

    def find_by_username_except(self, username: str, user_id: int):
        return self.session.scalar(
            select(UserModel).where(
                UserModel.username == username,
                UserModel.id != user_id,
                UserModel.deleted_at.is_(None),
            )
        )

    def count_active_admins(self) -> int:
        return int(
            self.session.scalar(
                select(func.count(UserModel.id)).where(
                    UserModel.role == "admin",
                    UserModel.deleted_at.is_(None),
                )
            )
            or 0
        )
    
    def find_by_username_and_password(self, username: str, password: hash):
        statement = select(UserModel).where(
            UserModel.username == username,
            UserModel.password == password,
            UserModel.deleted_at.is_(None)
        )
        return self.session.scalar(statement)


    
