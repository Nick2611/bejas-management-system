import os

from sqlalchemy import create_engine

from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import Depends


engine = create_engine(
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://bejas:admin@localhost:5432/bejas-db"
    )
)

def get_session():
    with Session(engine) as session:
        yield session




SessionDep = Annotated[Session, Depends(get_session)]
