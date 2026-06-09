from db.db_models import Base
from typing import Type, TypeVar, Generic, Sequence, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, delete



T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], session: Session):
        self.model = model
        self.session = session

    def add(self, entity: T):
        self.session.add(entity)
        return entity
    
    def read(self) -> Sequence[T]:
        return self.session.scalars(select(self.model)).all()

    def get_by_id(self, entity: T, id: int):
        stmt = select(entity).where(entity.id == id)

        return self.session.scalar(stmt)
    
    def delete_by_id(self, entity: T, id: int):
        stmt = delete(entity).where(entity.id == id)

        return self.session.delete(stmt)
    
    def update(self, entity: T, data: Dict[str, Any]) -> T:
        for k, v in data.items():
            setattr(entity, k, v)

        return entity
    

