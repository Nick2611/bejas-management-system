from json import JSONDecodeError, loads
from logging import getLogger
from socket import gethostname
from typing import Callable

from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from sqlalchemy.orm import Session

from db.db_conn import engine
from invoices.afip_client import (
    AfipClient,
    AfipTemporaryError,
    get_afip_client,
)
from invoices.service.invoice_service import (
    AFIP_DECLARATION_SOURCES,
    InvoiceService,
)
from rabbitmq.rabbit_client import (
    AFIP_MAX_DELIVERY_ATTEMPTS,
    AFIP_QUEUE,
    RabbitClient,
)
from shared.time_utils import local_now
from shared.utils import get_rabbit_client


class RabbitReader:
    def __init__(
        self,
        session_factory: Callable[[], Session] | None = None,
        afip_client: AfipClient | None = None,
        rabbit_factory: Callable[[], RabbitClient] | None = None,
    ):
        self.session_factory = session_factory or (lambda: Session(engine))
        self.afip = afip_client or get_afip_client()
        self.rabbit_factory = rabbit_factory or get_rabbit_client
        self.logger = getLogger("afip_worker")
        self.worker_id = gethostname()

    def consume_message(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ):
        try:
            payload = loads(body)
        except (JSONDecodeError, UnicodeDecodeError):
            self.logger.exception("Mensaje de AFIP inválido: no es JSON")
            channel.basic_reject(
                delivery_tag=method.delivery_tag,
                requeue=False,
            )
            return

        session = self.session_factory()
        try:
            service = InvoiceService(session, self.afip)
            service.process_outbox(
                payload,
                worker_id=self.worker_id,
            )
            session.commit()
        except AfipTemporaryError:
            delivery_count = (properties.headers or {}).get(
                "x-delivery-count",
                0,
            )
            attempt_number = delivery_count + 1
            try:
                if attempt_number >= AFIP_MAX_DELIVERY_ATTEMPTS:
                    service.mark_outbox_processed(payload)
                session.commit()
            except Exception:
                session.rollback()
                self.logger.exception(
                    "No se pudo persistir el intento fiscal fallido"
                )
                channel.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True,
                )
                return
            if attempt_number >= AFIP_MAX_DELIVERY_ATTEMPTS:
                self.logger.error(
                    "Error fiscal temporal; mensaje %s enviado a DLQ "
                    "tras %s intentos",
                    method.delivery_tag,
                    attempt_number,
                )
                channel.basic_reject(
                    delivery_tag=method.delivery_tag,
                    requeue=False,
                )
                return
            self.logger.warning(
                "Error fiscal temporal; mensaje %s reencolado (intento %s)",
                method.delivery_tag,
                attempt_number,
            )
            channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=True,
            )
            return
        except ValueError:
            session.rollback()
            self.logger.exception("Mensaje de AFIP no procesable")
            channel.basic_reject(
                delivery_tag=method.delivery_tag,
                requeue=False,
            )
            return
        except Exception:
            session.rollback()
            self.logger.exception("Error inesperado procesando mensaje de AFIP")
            channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=True,
            )
            return
        finally:
            session.close()

        channel.basic_ack(delivery_tag=method.delivery_tag)
        self.logger.info("Mensaje de AFIP procesado")

    def _republish_pending_outboxes(self, rabbit: RabbitClient):
        session = self.session_factory()
        try:
            outboxes = InvoiceService(
                session,
                self.afip,
            ).repository.get_unprocessed_outboxes()
            published_count = 0
            skipped_count = 0
            for outbox in outboxes:
                payload = outbox.payload or {}
                source = payload.get(
                    "message_source",
                    payload.get("declaration_source"),
                )
                if source not in AFIP_DECLARATION_SOURCES:
                    outbox.is_processed = True
                    skipped_count += 1
                    continue
                rabbit.publish(payload)
                outbox.published_at = outbox.published_at or local_now()
                published_count += 1
            session.commit()
            if published_count:
                self.logger.info(
                    "Se republicaron %s outboxes pendientes",
                    published_count,
                )
            if skipped_count:
                self.logger.warning(
                    "Se descartaron %s outboxes automáticos heredados",
                    skipped_count,
                )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def run_forever(self):
        rabbit = self.rabbit_factory()
        try:
            rabbit.confirm_exchanges_and_queues()
            self._republish_pending_outboxes(rabbit)
            self.logger.info("Worker de AFIP esperando mensajes")
            rabbit.consume(self.consume_message, queue=AFIP_QUEUE)
        finally:
            rabbit.close()


def main():
    RabbitReader().run_forever()


if __name__ == "__main__":
    main()
