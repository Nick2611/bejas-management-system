from http import HTTPStatus
from typing import Type, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


def commit_session(session: Session):
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise


def custom_response(response_class: Type[ResponseModel], **kwargs,) -> ResponseModel:
    return response_class(
        status=HTTPStatus.OK,
        **kwargs
    )
