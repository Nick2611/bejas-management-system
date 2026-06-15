from http import HTTPStatus
from logging import getLogger
from os import getenv
from typing import Type, TypeVar

from pika.exceptions import AMQPError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import Depends

from rabbitmq.rabbit_client import (
    AFIP_QUEUE,
    AFIP_ROUTING_KEY,
    RabbitClient,
)


RABBIT_HOST = getenv("RABBIT_HOST", "localhost")
RABBIT_PORT = int(getenv("RABBIT_PORT", "5672"))
RABBIT_USER = getenv("RABBIT_USER", "bejas")
RABBIT_PASS = getenv("RABBIT_PASS", "admin")
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
logger = getLogger("rabbit_publisher")


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


def get_rabbit_client():
    return RabbitClient(
        rabbit_host=RABBIT_HOST,
        rabbit_port=RABBIT_PORT,
        rabbit_user=RABBIT_USER,
        rabbit_pass=RABBIT_PASS,
    )


def publish_afip_messages(payloads: list[dict]) -> int:
    if not payloads:
        return 0

    rabbit = None
    published = 0
    try:
        rabbit = get_rabbit_client()
        rabbit.confirm_exchanges_and_queues()
        for payload in payloads:
            rabbit.publish(
                payload=payload,
                queue=AFIP_QUEUE,
                routing_key=AFIP_ROUTING_KEY,
            )
            published += 1
    except (AMQPError, OSError):
        logger.exception(
            "No se pudieron publicar todos los mensajes de AFIP; "
            "los outboxes permanecen pendientes"
        )
    finally:
        if rabbit is not None:
            try:
                rabbit.close()
            except (AMQPError, OSError):
                logger.warning(
                    "No se pudo cerrar la conexión con RabbitMQ",
                    exc_info=True,
                )
    return published


RabbitDep = Depends(get_rabbit_client)
